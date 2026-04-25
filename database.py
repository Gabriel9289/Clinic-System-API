from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text, Time
from sqlalchemy.orm import DeclarativeBase, Session, relationship
from dotenv import load_dotenv
from datetime import datetime, timezone
import os
import enum

load_dotenv()

DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"

engine = create_engine(DATABASE_URL)


class Base(DeclarativeBase):
    pass


# ── Enums ─────────────────────────────────────────────────────────────────────

class RoleEnum(str, enum.Enum):
    patient = "patient"
    doctor = "doctor"
    receptionist = "receptionist"
    admin = "admin"


class SlotTypeEnum(str, enum.Enum):
    working = "working"
    break_ = "break"
    free = "free"


class SlotStatusEnum(str, enum.Enum):
    available = "available"
    booked = "booked"
    blocked = "blocked"


class AppointmentStatusEnum(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    adjusted_auto = "adjusted_auto"
    adjusted_manual = "adjusted_manual"
    confirmed = "confirmed"
    declined = "declined"
    cancelled = "cancelled"
    completed = "completed"


# ── Models ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(RoleEnum), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(20), nullable=False)
    phone = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    appointments = relationship("Appointment", back_populates="patient")
    files = relationship("PatientFile", back_populates="patient")


class DoctorSchedule(Base):
    __tablename__ = "doctor_schedules"
    id = Column(Integer, primary_key=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    slots_per_day = Column(Integer, nullable=False)
    slot_duration_minutes = Column(Integer, nullable=False)
    work_start_time = Column(Time, nullable=False)
    work_end_time = Column(Time, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    doctor = relationship("Doctor", back_populates="schedule")


class Doctor(Base):
    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    specialization = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    slots = relationship("TimeSlot", back_populates="doctor")
    appointments = relationship("Appointment", back_populates="doctor")
    schedule = relationship("DoctorSchedule", back_populates="doctor",
                            uselist=False)


class TimeSlot(Base):
    __tablename__ = "time_slots"
    id = Column(Integer, primary_key=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    slot_type = Column(Enum(SlotTypeEnum), default=SlotTypeEnum.working)
    status = Column(Enum(SlotStatusEnum), default=SlotStatusEnum.available)
    doctor = relationship("Doctor", back_populates="slots")
    appointments = relationship("Appointment", back_populates="slot",
                                foreign_keys="Appointment.slot_id")


class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    slot_id = Column(Integer, ForeignKey("time_slots.id"), nullable=False)
    status = Column(Enum(AppointmentStatusEnum),
                    default=AppointmentStatusEnum.pending)
    reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    decline_reason = Column(Text, nullable=True)
    adjusted_slot_id = Column(Integer, ForeignKey("time_slots.id"),
                               nullable=True)
    notification_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    slot = relationship("TimeSlot", back_populates="appointments",
                        foreign_keys=[slot_id])
    adjusted_slot = relationship("TimeSlot", foreign_keys=[adjusted_slot_id])
    files = relationship("PatientFile", back_populates="appointment")


class PatientFile(Base):
    __tablename__ = "patient_files"
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    appointment_id = Column(Integer, ForeignKey("appointments.id"),
                            nullable=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    patient = relationship("Patient", back_populates="files")
    appointment = relationship("Appointment", back_populates="files")


def get_db():
    db = Session(engine)
    try:
        yield db
    finally:
        db.close()
