from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from database import get_db, User, Patient, Doctor, Appointment
from schemas import (UserCreate, TokenResponse, PatientCreate, PatientResponse,
                     DoctorCreate, DoctorResponse, ScheduleCreate,
                     ScheduleResponse, SlotResponse, AppointmentCreate,
                     AppointmentResponse, AppointmentAdjustManual,
                     AppointmentDecline, AppointmentNotes)
from auth import (verify_password, create_access_token, get_current_user,
                  require_roles)
from services import (
    create_user, get_user_by_email, create_doctor, set_doctor_schedule,
    generate_slots_for_date, create_patient, get_available_slots,
    book_appointment, approve_appointment, decline_appointment,
    adjust_appointment_auto, adjust_appointment_manual, add_notes,
    complete_appointment, confirm_adjustment, cancel_appointment,
    get_doctor_appointments, get_clinic_summary
)

app = FastAPI(title="Clinic Booking API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health(db: Session = Depends(get_db)):
    return {"status": "ok", "database": "connected"}


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/register", status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db)):
    existing = get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = create_user(db, data.email, data.password, data.role)
    return {"message": f"User {user.email} created"}


@app.post("/login", response_model=TokenResponse)
def login(data: UserCreate, db: Session = Depends(get_db)):
    user = get_user_by_email(db, data.email)
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.email, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}


# ── Admin: Doctors ────────────────────────────────────────────────────────────

@app.post("/doctors", response_model=DoctorResponse, status_code=201)
def add_doctor(
    data: DoctorCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["admin"]))
):
    return create_doctor(db, data)


@app.get("/doctors", response_model=List[DoctorResponse])
def list_doctors(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["admin", "receptionist"]))
):
    return db.query(Doctor).filter(Doctor.is_active == True).all()


# ── Doctor: Schedule and Slots ────────────────────────────────────────────────

@app.post("/my-schedule", response_model=ScheduleResponse)
def update_schedule(
    data: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["doctor"]))
):
    user = get_user_by_email(db, current_user["sub"])
    doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    return set_doctor_schedule(db, doctor.id, data)


@app.post("/my-schedule/generate-slots")
def generate_slots(
    date: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["doctor"]))
):
    user = get_user_by_email(db, current_user["sub"])
    doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    target_date = datetime.strptime(date, "%Y-%m-%d")
    slots, message = generate_slots_for_date(db, doctor.id, target_date)
    if not slots:
        raise HTTPException(status_code=400, detail=message)
    return {"message": message, "slots_created": len(slots)}


# ── Public: Available Slots ───────────────────────────────────────────────────

@app.get("/slots/{doctor_id}", response_model=List[SlotResponse])
def available_slots(
    doctor_id: int,
    date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    target_date = datetime.strptime(date, "%Y-%m-%d") if date else None
    return get_available_slots(db, doctor_id, target_date)


# ── Patient: Book and View ────────────────────────────────────────────────────

@app.post("/appointments", response_model=AppointmentResponse, status_code=201)
def book(
    data: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["patient", "receptionist"]))
):
    user = get_user_by_email(db, current_user["sub"])
    patient = db.query(Patient).filter(Patient.user_id == user.id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    appointment, message = book_appointment(db, patient.id, data)
    if not appointment:
        raise HTTPException(status_code=400, detail=message)
    return appointment


@app.get("/my-appointments", response_model=List[AppointmentResponse])
def my_appointments(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["patient"]))
):
    user = get_user_by_email(db, current_user["sub"])
    patient = db.query(Patient).filter(Patient.user_id == user.id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return patient.appointments


# ── Doctor: Appointment Actions ───────────────────────────────────────────────

@app.get("/doctor/appointments", response_model=List[AppointmentResponse])
def doctor_appointments(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["doctor"]))
):
    user = get_user_by_email(db, current_user["sub"])
    doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    return get_doctor_appointments(db, doctor.id, status)


@app.patch("/appointments/{appointment_id}/approve",
           response_model=AppointmentResponse)
def approve(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["doctor"]))
):
    user = get_user_by_email(db, current_user["sub"])
    doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    result, message = approve_appointment(db, appointment_id, doctor.id)
    if not result:
        raise HTTPException(status_code=400, detail=message)
    return result


@app.patch("/appointments/{appointment_id}/decline",
           response_model=AppointmentResponse)
def decline(
    appointment_id: int,
    data: AppointmentDecline,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["doctor"]))
):
    user = get_user_by_email(db, current_user["sub"])
    doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    result, message = decline_appointment(
        db, appointment_id, doctor.id, data.decline_reason
    )
    if not result:
        raise HTTPException(status_code=400, detail=message)
    return result


@app.patch("/appointments/{appointment_id}/adjust-auto",
           response_model=AppointmentResponse)
def adjust_auto(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["doctor"]))
):
    user = get_user_by_email(db, current_user["sub"])
    doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    result, message = adjust_appointment_auto(db, appointment_id, doctor.id)
    if not result:
        raise HTTPException(status_code=400, detail=message)
    return result


@app.patch("/appointments/{appointment_id}/adjust-manual",
           response_model=AppointmentResponse)
def adjust_manual(
    appointment_id: int,
    data: AppointmentAdjustManual,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["doctor"]))
):
    user = get_user_by_email(db, current_user["sub"])
    doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    result, message = adjust_appointment_manual(
        db, appointment_id, doctor.id, data.new_slot_id
    )
    if not result:
        raise HTTPException(status_code=400, detail=message)
    return result


@app.patch("/appointments/{appointment_id}/complete",
           response_model=AppointmentResponse)
def complete(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["doctor"]))
):
    user = get_user_by_email(db, current_user["sub"])
    doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    result, message = complete_appointment(db, appointment_id, doctor.id)
    if not result:
        raise HTTPException(status_code=400, detail=message)
    return result


@app.patch("/appointments/{appointment_id}/notes",
           response_model=AppointmentResponse)
def appointment_notes(
    appointment_id: int,
    data: AppointmentNotes,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["doctor"]))
):
    user = get_user_by_email(db, current_user["sub"])
    doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    result, message = add_notes(db, appointment_id, doctor.id, data.notes)
    if not result:
        raise HTTPException(status_code=400, detail=message)
    return result


# ── Patient: Confirm or Cancel ────────────────────────────────────────────────

@app.patch("/appointments/{appointment_id}/confirm",
           response_model=AppointmentResponse)
def confirm(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["patient"]))
):
    user = get_user_by_email(db, current_user["sub"])
    patient = db.query(Patient).filter(Patient.user_id == user.id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    result, message = confirm_adjustment(db, appointment_id, patient.id)
    if not result:
        raise HTTPException(status_code=400, detail=message)
    return result


@app.patch("/appointments/{appointment_id}/cancel",
           response_model=AppointmentResponse)
def cancel(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["patient", "receptionist"]))
):
    user = get_user_by_email(db, current_user["sub"])
    result, message = cancel_appointment(
        db, appointment_id, user.id, current_user["role"]
    )
    if not result:
        raise HTTPException(status_code=400, detail=message)
    return result


# ── Receptionist: All Appointments ───────────────────────────────────────────

@app.get("/appointments", response_model=List[AppointmentResponse])
def all_appointments(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["receptionist", "admin"]))
):
    query = db.query(Appointment)
    if status:
        query = query.filter(Appointment.status == status)
    return query.order_by(Appointment.created_at.desc()).all()


# ── Admin: Dashboard ──────────────────────────────────────────────────────────

@app.get("/admin/dashboard")
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["admin"]))
):
    return get_clinic_summary(db)
