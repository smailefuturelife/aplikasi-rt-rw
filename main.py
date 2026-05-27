from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import User, KK, Penduduk, PengajuanSurat, Base, Surat, PembayaranIuran, Informasi, SuratUpload
from passlib.context import CryptContext
from typing import List, Optional
from sqlalchemy import func
from datetime import datetime
import base64, os, shutil

UPLOAD_FOLDER = "uploads/surat"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

BUKTI_FOLDER = "bukti_pembayaran"
os.makedirs(BUKTI_FOLDER, exist_ok=True)

app = FastAPI()
app.mount("/bukti_pembayaran", StaticFiles(directory=BUKTI_FOLDER), name="bukti_pembayaran")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

Base.metadata.create_all(bind=engine)
def buat_admin_default():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()

        if not admin:
            admin_baru = User(
                username="admin",
                password=hash_password("admin123"),
                role="pengurus",
                status="active"
            )
            db.add(admin_baru)
            db.commit()
            print("Admin default berhasil dibuat")
    finally:
        db.close()

buat_admin_default()

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str   

class PendudukInput(BaseModel):
    nik: str
    nama: str
    alamat: str
    hubungan: str   

class KKInput(BaseModel):
    no_kk: str
    alamat: str
    anggota: List[PendudukInput]

class PengajuanSuratRequest(BaseModel):
    username: str
    jenis_surat: str
    keterangan: Optional[str] = None

class LengkapiDataRequest(BaseModel):
    no_kk: str
    alamat: str
    nik: str
    nama: str

class SuratInput(BaseModel):
    username: str
    jenis_surat: str
    keterangan: str | None = None

class InfoCreate(BaseModel):
    judul: str
    tanggal: str

# ----------- FRONTEND ROUTES ----------
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/", response_class=FileResponse)
def serve_index():
    return FileResponse("frontend/index.html")

@app.get("/loginpage", response_class=FileResponse)
def serve_login():
    return FileResponse("frontend/login.html")

@app.get("/dashboard", response_class=FileResponse)
def serve_dashboard():
    return FileResponse("frontend/dashboard.html")

@app.get("/dashboard_masyarakat.html", response_class=FileResponse)
def serve_dashboard_masyarakat():
    return FileResponse("frontend/dashboard_masyarakat.html")

@app.get("/dashboard_pengurus.html", response_class=FileResponse)
def serve_dashboard_pengurus():
    return FileResponse("frontend/dashboard_pengurus.html")

@app.get("/registerpage", response_class=FileResponse)
def serve_register():
    return FileResponse("frontend/register.html")

# ----------- BACKEND ROUTES -----------
@app.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Username atau password salah")

    # Verifikasi password
    if user.password.startswith("$2b$"):
        password_valid = verify_password(request.password, user.password)
    else:
        password_valid = (user.password == request.password)

    if not password_valid:
        raise HTTPException(status_code=401, detail="Username atau password salah")

    # 🚫 Cek status verifikasi akun
    if user.status != "active":
        raise HTTPException(status_code=403, detail="Akun belum diverifikasi oleh pengurus")

    # Cek apakah perlu melengkapi data KK
    need_data = (
        user.role == "masyarakat" and 
        (user.kk is None or len(user.kk.anggota) == 0)
    )

    return {
        "message": "Login berhasil",
        "username": user.username,
        "role": user.role,
        "status": user.status,
        "need_data": need_data
    }

# ----------- FITUR SURAT -----------
@app.post("/ajukan-surat/{username}")
def ajukan_surat(username: str, req: SuratInput, db: Session = Depends(get_db)):
    print("📩 Data masuk:", req.dict())   # ✅ debug

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    surat = PengajuanSurat(
        username=user.username,
        jenis_surat=req.jenis_surat,
        keterangan=req.keterangan,
        status="pending",
        user=user
    )
    db.add(surat)
    db.commit()
    db.refresh(surat)
    return {"message": "Surat berhasil diajukan", "data": surat}

@app.get("/surat-uploads")
def get_all_surat(db: Session = Depends(get_db)):  # ✅ Benar
    files = db.query(SuratUpload).all()
    return files

from fastapi.responses import FileResponse

# Perbaiki endpoint delete-surat di main.py
@app.delete("/delete-surat/{surat_id}")
def delete_surat(surat_id: int, db: Session = Depends(get_db)):
    try:
        # Cari surat berdasarkan ID
        surat = db.query(Surat).filter(Surat.id == surat_id).first()
        if not surat:
            raise HTTPException(status_code=404, detail=f"File surat dengan ID {surat_id} tidak ditemukan")

        # Simpan nama file & cari file fisik
        file_path = os.path.join(UPLOAD_FOLDER, surat.nama_file)

        # Coba hapus file fisik di folder
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"✅ File fisik '{surat.nama_file}' berhasil dihapus")
            except Exception as e:
                print(f"⚠️ Tidak bisa hapus file fisik: {e}")
        else:
            print(f"⚠️ File fisik tidak ditemukan: {file_path}")

        # Hapus juga pengajuan surat terkait (jika ada)
        if surat.pengajuan_id:
            pengajuan = db.query(PengajuanSurat).filter(
                PengajuanSurat.id == surat.pengajuan_id
            ).first()
            if pengajuan:
                db.delete(pengajuan)
                print(f"✅ Pengajuan surat terkait juga dihapus")

        # Hapus surat dari tabel Surat
        db.delete(surat)
        db.commit()

        return {
            "message": f"🗑️ File '{surat.nama_file}' berhasil dihapus dari server & database.",
            "success": True
        }
    
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error saat menghapus surat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan: {str(e)}")

# 📥 Unduh surat
@app.get("/download-surat/{filename}")
async def download_surat(filename: str):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename)
    else:
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")

# ✅ Endpoint untuk download file
@app.get("/files/{filename}")
def get_file(filename: str):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    return FileResponse(file_path, media_type="application/octet-stream", filename=filename)

@app.get("/pengajuan-surat")
def get_pengajuan(db: Session = Depends(get_db)):
    pengajuan = db.query(PengajuanSurat).all()
    return [
        {
            "id": s.id,
            "username": s.username,
            "jenis": s.jenis_surat,
            "keterangan": s.keterangan,
            "status": s.status
        }
        for s in pengajuan
    ]

@app.post("/approve-surat/{pengajuan_id}")
def approve_surat(pengajuan_id: int, db: Session = Depends(get_db)):
    # Cari pengajuan surat
    pengajuan = db.query(PengajuanSurat).filter(PengajuanSurat.id == pengajuan_id).first()
    if not pengajuan:
        raise HTTPException(status_code=404, detail="Pengajuan surat tidak ditemukan")

    # Ubah status menjadi approved
    pengajuan.status = "approved"
    db.commit()

    # Cari file surat (template surat resmi)
    surat_template = db.query(Surat).filter(Surat.pengajuan_id == None).first()  # ambil surat umum
    if not surat_template:
        return {"message": "✅ Surat disetujui, tapi belum ada file PDF template untuk dikirim."}

    # Duplikat file surat (dari template) ke user pemohon
    new_surat = Surat(
        pengajuan_id=pengajuan.id,
        nama_file=surat_template.nama_file,
        tipe_file=surat_template.tipe_file,
        ukuran_file=surat_template.ukuran_file,
        file_data=surat_template.file_data,
        uploaded_by=pengajuan.username,
        deskripsi=f"Surat {pengajuan.jenis_surat} untuk {pengajuan.username}",
    )
    db.add(new_surat)
    db.commit()

    print(f"📤 Surat {new_surat.nama_file} dikirim ke {pengajuan.username}")

    return {
        "message": f"✅ Surat untuk {pengajuan.username} telah di-ACC dan dikirim ke menu Ajukan Surat.",
        "status": "approved",
        "surat_dikirim": new_surat.nama_file
    }

# ==================== SURAT & FILE UPLOAD ENDPOINTS ====================

# ✅ Upload surat (fungsi tunggal)
@app.post("/upload-surat")
async def upload_surat(
    username: str = Form(...),
    jenis_surat: str = Form(...),
    keterangan: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Validasi ekstensi file
    allowed_ext = ["pdf", "doc", "docx", "jpg", "jpeg", "png"]
    ext = file.filename.split(".")[-1].lower()
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail="Format file tidak didukung.")

    # Simpan file fisik ke folder
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Simpan pengajuan surat ke DB
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    pengajuan = PengajuanSurat(
        username=username,
        jenis_surat=jenis_surat,
        keterangan=keterangan,
        status="pending",
        user_id=user.id
    )
    db.add(pengajuan)
    db.commit()
    db.refresh(pengajuan)

    # Simpan file surat ke tabel Surat
    surat = Surat(
        pengajuan_id=pengajuan.id,
        nama_file=file.filename,
        tipe_file=file.content_type,
        ukuran_file=os.path.getsize(file_path),
        file_data=None,  # kalau mau hemat, bisa None
        uploaded_by=username,
        deskripsi=keterangan
    )
    db.add(surat)
    db.commit()

    return {
        "message": "✅ Surat berhasil diupload dan diajukan!",
        "filename": file.filename,
        "pengajuan_id": pengajuan.id
    }

    
@app.get("/surat")
def get_all_surat(db: Session = Depends(get_db)):
    surat_list = db.query(Surat).all()
    return [
        {
            "id": s.id,
            "nama_file": s.nama_file,
            "tipe_file": s.tipe_file,
            "ukuran_file": s.ukuran_file,
            "uploaded_by": s.uploaded_by,
            "tanggal_upload": s.tanggal_upload,
            "deskripsi": s.deskripsi,
            "pengajuan_id": s.pengajuan_id
        }
        for s in surat_list
    ]

@app.get("/download-surat/{surat_id}")
def download_surat(surat_id: int, db: Session = Depends(get_db)):
    surat = db.query(Surat).filter(Surat.id == surat_id).first()
    if not surat:
        raise HTTPException(status_code=404, detail="File surat tidak ditemukan")
    
    # Return file data (dalam implementasi nyata, gunakan FileResponse)
    return {
        "nama_file": surat.nama_file,
        "tipe_file": surat.tipe_file,
        "file_data": base64.b64encode(surat.file_data).decode('utf-8'),
        "ukuran": surat.ukuran_file
    }

@app.delete("/delete-surat/{surat_id}")
def delete_surat(surat_id: int, db: Session = Depends(get_db)):
    surat = db.query(Surat).filter(Surat.id == surat_id).first()
    if not surat:
        raise HTTPException(status_code=404, detail="File surat tidak ditemukan")
    
    db.delete(surat)
    db.commit()
    
    return {"message": "File surat berhasil dihapus"}

# ----------- REGISTER & DATA KK -----------
@app.post("/register")
def register_user(req: RegisterRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.username == req.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username sudah terdaftar")

    new_user = User(
        username=req.username,
        password=hash_password(req.password),
        role=req.role,
        status="pending"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": f"Akun {req.username} berhasil dibuat", "role": req.role}

@app.post("/isi-data-kk/{username}")
def isi_data_kk(username: str, req: KKInput, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    kk = KK(no_kk=req.no_kk, alamat=req.alamat, user=user)
    db.add(kk)
    db.commit()
    db.refresh(kk)

    for anggota in req.anggota:
        penduduk = Penduduk(
            nik=anggota.nik,
            nama=anggota.nama,
            alamat=anggota.alamat,
            hubungan=anggota.hubungan,
            kk=kk
        )
        db.add(penduduk)

    db.commit()
    return {"message": "Data KK dan anggota berhasil disimpan"}

@app.get("/formulir_penduduk.html", response_class=FileResponse)
def serve_formulir_penduduk():
    return FileResponse("frontend/formulir_penduduk.html")

@app.get("/isi-data-kk/{username}")
def get_data_kk(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    if not user.kk:
        return {
            "username": user.username,
            "no_kk": None,
            "alamat": None,
            "anggota": []
        }

    return {
        "username": user.username,
        "no_kk": user.kk.no_kk,
        "alamat": user.kk.alamat,
        "anggota": [
            {
                "nik": p.nik,
                "nama": p.nama,
                "alamat": p.alamat
            }
            for p in user.kk.anggota
        ]
    }

@app.get("/profil/{username}")
def get_profil(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    if not user.kk:
        return {
            "username": user.username,
            "role": user.role,
            "kk": None,
            "alamat": None,
            "anggota": []
        }

    return {
        "username": user.username,
        "role": user.role,
        "kk": user.kk.no_kk,
        "alamat": user.kk.alamat,
        "anggota": [
            {
                "nik": p.nik,
                "nama": p.nama,
                "alamat": p.alamat,
                "hubungan": p.hubungan
            } for p in user.kk.anggota
        ]
    }

@app.get("/penduduk")
def get_penduduk(db: Session = Depends(get_db)):
    penduduk_list = db.query(Penduduk).all()
    return [
        {
            "id": p.id,
            "nik": p.nik,
            "nama": p.nama,
            "alamat": p.alamat,
            "kk": p.kk.no_kk if p.kk else None
        }
        for p in penduduk_list
    ]

@app.get("/penduduk/count")
def get_penduduk_count(db: Session = Depends(get_db)):
    total = db.query(Penduduk).count()
    return {"total": total}

@app.post("/api/upload_surat")
async def upload_surat(
    username: str = Form(...),
    jenis_surat: str = Form(...),
    keterangan: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # 1. Simpan pengajuan surat
    pengajuan = PengajuanSurat(
        username=username,
        jenis_surat=jenis_surat,
        keterangan=keterangan,
        status="pending",
        user_id=1   # sementara, bisa ambil dari session login
    )
    db.add(pengajuan)
    db.commit()
    db.refresh(pengajuan)

    # 2. Simpan file surat ke tabel Surat
    file_bytes = await file.read()
    surat = Surat(
        pengajuan_id=pengajuan.id,
        nama_file=file.filename,
        tipe_file=file.content_type,
        ukuran_file=len(file_bytes),
        file_data=file_bytes,
        uploaded_by=username,
        deskripsi=keterangan
    )
    db.add(surat)
    db.commit()
    db.refresh(surat)

    return {
        "status": "success",
        "pengajuan_id": pengajuan.id,
        "surat_id": surat.id,
        "message": "Surat berhasil diunggah!"
    }

@app.post("/bayar-iuran/{username}")
async def bayar_iuran(
    username: str,
    metode: str = Form(...),
    bulan: str = Form(...),
    bukti: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    bukti_filename = None
    if bukti:
        # Gunakan folder bukti_pembayaran
        bukti_filename = f"{username}_{bukti.filename}"
        bukti_path = os.path.join("bukti_pembayaran", bukti_filename)
        with open(bukti_path, "wb") as f:
            f.write(await bukti.read())

    pembayaran = PembayaranIuran(
        username=username,
        bulan=bulan,
        jumlah=50000,
        metode=metode,
        status="Menunggu Verifikasi" if metode == "transfer" else "Lunas",
        tanggal_bayar=datetime.utcnow(),
        bukti_pembayaran=bukti_filename
    )
    db.add(pembayaran)
    db.commit()
    db.refresh(pembayaran)

    return {"message": "Pembayaran berhasil dikirim", "data": pembayaran}

@app.get("/pembayaran_form.html", response_class=FileResponse)
def serve_pembayaran_form():
    return FileResponse("frontend/pembayaran_form.html")

# ✅ Riwayat pembayaran user
@app.get("/riwayat-iuran/{username}")
def riwayat_iuran(username: str, db: Session = Depends(get_db)):
    riwayat = db.query(PembayaranIuran).filter(PembayaranIuran.username == username).order_by(PembayaranIuran.id.desc()).all()
    return riwayat

# ✅ Ambil daftar pembayaran pending
@app.get("/pembayaran/pending")
def get_pending_pembayaran(db: Session = Depends(get_db)):
    data = db.query(PembayaranIuran).filter(PembayaranIuran.status == "pending").all()
    return data

# 📋 Ambil semua pembayaran (untuk dashboard pengurus)
@app.get("/pembayaran")
def get_semua_pembayaran(db: Session = Depends(get_db)):
    data = db.query(PembayaranIuran).all()
    return [
        {
            "id": p.id,
            "username": p.username,
            "bulan": p.bulan,
            "jumlah": p.jumlah,
            "metode": p.metode,
            "bukti_pembayaran": p.bukti_pembayaran,
            "status": p.status,
            "tanggal_bayar": p.tanggal_bayar.strftime("%Y-%m-%d %H:%M:%S")
        }
        for p in data
    ]

@app.put("/pembayaran/verifikasi/{pembayaran_id}")
def verifikasi_pembayaran(pembayaran_id: int, db: Session = Depends(get_db)):
    pembayaran = db.query(PembayaranIuran).filter(PembayaranIuran.id == pembayaran_id).first()
    if not pembayaran:
        raise HTTPException(status_code=404, detail="Pembayaran tidak ditemukan")
    
    pembayaran.status = "verified"  # ✅ Ubah jadi Lunas agar konsisten di frontend 
    db.commit()
    db.refresh(pembayaran)

    return {"message": f"Pembayaran {pembayaran.username} bulan {pembayaran.bulan} sudah diverifikasi ✅"}

@app.get("/buku-kas")
def get_buku_kas(db: Session = Depends(get_db)):
    hasil = (
        db.query(
            User.username,
            KK.no_kk,
            KK.alamat,
            func.sum(PembayaranIuran.jumlah).label("total_iuran"),
            func.max(PembayaranIuran.tanggal_bayar).label("terakhir_bayar")
        )
        .join(PembayaranIuran, PembayaranIuran.username == User.username, isouter=True)
        .join(KK, KK.id == User.kk_id, isouter=True)  # ✅ join benar sesuai model kamu
        .filter(PembayaranIuran.status == "verified")
        .group_by(User.username, KK.no_kk, KK.alamat)
        .all()
    )

    return [
        {
            "username": h.username,
            "no_kk": h.no_kk or "-",
            "alamat": h.alamat or "-",
            "total_iuran": h.total_iuran or 0,
            "terakhir_bayar": h.terakhir_bayar.strftime("%Y-%m-%d") if h.terakhir_bayar else "-"
        }
        for h in hasil
    ]

# ✅ Buku Kas berdasarkan username
@app.get("/buku-kas/{username}")
def get_buku_kas_user(username: str, db: Session = Depends(get_db)):
    data = (
        db.query(PembayaranIuran)
        .filter(PembayaranIuran.username == username)
        .order_by(PembayaranIuran.id.desc())
        .all()
    )
    
    return [
        {
            "bulan": d.bulan,
            "jumlah": d.jumlah,
            "metode": d.metode,
            "status": d.status,
            "bukti": d.bukti_pembayaran
        }
        for d in data
    ]

@app.post("/informasi")
def tambah_informasi(info: InfoCreate, db: Session = Depends(get_db)):
    new_info = Informasi(
        judul=info.judul,
        tanggal=info.tanggal,
        status="active"
    )
    db.add(new_info)
    db.commit()
    db.refresh(new_info)
    return {"message": "Informasi berhasil ditambahkan!", "data": new_info}

@app.get("/informasi")
def get_informasi(db: Session = Depends(get_db)):
    return db.query(Informasi).filter(Informasi.status == "active").order_by(Informasi.id.desc()).all()

@app.delete("/informasi/{id}")
def hapus_informasi(id: int, db: Session = Depends(get_db)):
    info = db.query(Informasi).filter(Informasi.id == id).first()
    if not info:
        raise HTTPException(status_code=404, detail="Informasi tidak ditemukan")
    db.delete(info)
    db.commit()
    return {"message": "Informasi berhasil dihapus"}

@app.get("/surat/{username}")
def get_surat_user(username: str, db: Session = Depends(get_db)):
    return db.query(Surat).all()

@app.get("/frontend/buku_kas_tahunan_user.html", response_class=FileResponse)
def serve_buku_kas_tahunan_user_frontend():
    return FileResponse("frontend/buku_kas_tahunan_user.html")

# ✅ Ambil status iuran bulan ini untuk dashboard
@app.get("/status-iuran/{username}")
def get_status_iuran_bulan_ini(username: str, db: Session = Depends(get_db)):
    from datetime import datetime

    bulan_sekarang = datetime.now().strftime("%B %Y")  # Contoh: "Oktober 2025"

    pembayaran = (
        db.query(PembayaranIuran)
        .filter(PembayaranIuran.username == username)
        .filter(PembayaranIuran.bulan.ilike(f"%{bulan_sekarang}%"))
        .order_by(PembayaranIuran.id.desc())
        .first()
    )

    if not pembayaran:
        return {"bulan": bulan_sekarang, "status": "belum bayar", "jumlah": 50000}

    return {
        "bulan": pembayaran.bulan,
        "status": pembayaran.status,
        "jumlah": pembayaran.jumlah,
    }

@app.get("/pending_users")
def get_pending_users(db: Session = Depends(get_db)):
    users = db.query(User).filter(User.status == "pending").all()
    return users

# PUT verifikasi user
@app.put("/verify_user/{user_id}")
def verify_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    user.status = "active"
    db.commit()
    db.refresh(user)
    return {"message": f"Akun {user.username} berhasil diverifikasi!"}

@app.get("/all_users")
def get_all_users(db: Session = Depends(get_db)):
    return db.query(User).all()