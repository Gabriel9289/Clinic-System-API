from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, time


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: str
    password: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


# ── Patient ───────────────────────────────────────────────────────────────────

class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    age: int
    gender: str
    phone: Optional[str] = None


class PatientResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    age: int
    gender: str
    phone: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


# ── Doctor ────────────────────────────────────────────────────────────────────

class DoctorCreate(BaseModel):
    first_name: str
    last_name: str
    specialization: str
    phone: Optional[str] = None


class DoctorResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    specialization: str
    phone: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


# ── Doctor Schedule ───────────────────────────────────────────────────────────

class ScheduleCreate(BaseModel):
    slots_per_day: int
    slot_duration_minutes: int
    work_start_time: time
    work_end_time: time


class ScheduleResponse(BaseModel):
    id: int
    doctor_id: int
    slots_per_day: int
    slot_duration_minutes: int
    work_start_time: time
    work_end_time: time

    class Config:
        from_attributes = True


# ── Time Slot ─────────────────────────────────────────────────────────────────

class SlotResponse(BaseModel):
    id: int
    doctor_id: int
    date: datetime
    start_time: datetime
    end_time: datetime
    slot_type: str
    status: str

    class Config:
        from_attributes = True


# ── Appointment ───────────────────────────────────────────────────────────────

class AppointmentCreate(BaseModel):
    doctor_id: int
    slot_id: int
    reason: Optional[str] = None


class AppointmentResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    slot_id: int
    status: str
    reason: Optional[str] = None
    notes: Optional[str] = None
    decline_reason: Optional[str] = None
    adjusted_slot_id: Optional[int] = None
    notification_sent: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AppointmentAdjustManual(BaseModel):
    new_slot_id: int


class AppointmentDecline(BaseModel):
    decline_reason: str


class AppointmentNotes(BaseModel):
    notes: str
