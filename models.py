from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, LargeBinary, Date, Time, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, default="masyarakat")
    status = Column(String, default="pending")

    kk_id = Column(Integer, ForeignKey("kks.id"), nullable=True)
    kk = relationship("KK", back_populates="user")
    
    pengajuan_surat = relationship("PengajuanSurat", back_populates="user", cascade="all, delete")
    profil = relationship("Profil", back_populates="user", uselist=False)
    keluarga = relationship("AnggotaKeluarga", back_populates="user")
    pembayaran_iuran = relationship("PembayaranIuran", back_populates="user")

class KK(Base):
    __tablename__ = "kks"

    id = Column(Integer, primary_key=True, index=True)
    no_kk = Column(String, unique=True, index=True, nullable=False)
    alamat = Column(String, nullable=True)

    user = relationship("User", back_populates="kk", uselist=False)
    anggota = relationship("Penduduk", back_populates="kk", cascade="all, delete")

class Penduduk(Base):
    __tablename__ = "penduduk"

    id = Column(Integer, primary_key=True, index=True)
    nik = Column(String, unique=True, index=True, nullable=False)
    nama = Column(String, nullable=False)
    alamat = Column(String, nullable=True)
    username = Column(String, ForeignKey("users.username"))
    hubungan = Column(String, nullable=True)

    kk_id = Column(Integer, ForeignKey("kks.id"))
    kk = relationship("KK", back_populates="anggota")

class PengajuanSurat(Base):
    __tablename__ = "pengajuan_surat"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False)
    jenis_surat = Column(String, nullable=False)
    keterangan = Column(String, nullable=True)
    status = Column(String, default="pending")

    surat_hasil = relationship("Surat", back_populates="pengajuan", uselist=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="pengajuan_surat")
    
class Profil(Base):
    __tablename__ = "profil"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nama_lengkap = Column(String(100), nullable=False)
    nik = Column(String(16), unique=True)
    no_kk = Column(String(16))
    alamat = Column(Text)
    no_telepon = Column(String(15))
    foto_profil = Column(Text)
    
    user = relationship("User", back_populates="profil")

class AnggotaKeluarga(Base):
    __tablename__ = "anggota_keluarga"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nama = Column(String(100), nullable=False)
    nik = Column(String(16))
    hubungan = Column(String(50))
    alamat = Column(Text)
    
    user = relationship("User", back_populates="keluarga")

class SuratUpload(Base):
    __tablename__ = "surat_upload"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    uploader = Column(String, nullable=False)
    file_url = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

class Surat(Base):
    __tablename__ = "surat"
    
    id = Column(Integer, primary_key=True, index=True)
    nama_file = Column(String(255), nullable=False)  
    tipe_file = Column(String(50))                    
    ukuran_file = Column(Integer)                     
    file_data = Column(LargeBinary)                   
    uploaded_by = Column(String(50))                  
    tanggal_upload = Column(DateTime, default=datetime.utcnow)
    deskripsi = Column(Text)

    pengajuan_id = Column(Integer, ForeignKey("pengajuan_surat.id"), nullable=False)
    pengajuan = relationship("PengajuanSurat", back_populates="surat_hasil")


class Informasi(Base):
    __tablename__ = "informasi"

    id = Column(Integer, primary_key=True, index=True)
    judul = Column(String, nullable=False)
    deskripsi = Column(Text, nullable=True)
    tanggal = Column(Date, nullable=False)
    jam = Column(Time, nullable=True)
    status = Column(String, default="active")
    tanggal_dibuat = Column(DateTime, default=datetime.utcnow)

class PembayaranIuran(Base):
    __tablename__ = "pembayaran_iuran"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, ForeignKey("users.username"), nullable=False)
    bulan = Column(String, nullable=False)  
    jumlah = Column(Float, nullable=False)
    metode = Column(String, default="Tunai / Transfer")
    bukti_pembayaran = Column(String, nullable=True)
    status = Column(String, default="Lunas")
    tanggal_bayar = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="pembayaran_iuran")

class Kontak(Base):
    __tablename__ = "kontak"
    
    id = Column(Integer, primary_key=True, index=True)
    nama = Column(String(100), nullable=False)
    jabatan = Column(String(50))  
    no_telepon = Column(String(15))
    email = Column(String(100))
    alamat = Column(Text)