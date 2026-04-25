from sqlalchemy.orm import Session
from database import (User, Patient, Doctor, DoctorSchedule, TimeSlot,
                      Appointment, PatientFile, SlotStatusEnum, SlotTypeEnum,
                      AppointmentStatusEnum)
from schemas import (PatientCreate, DoctorCreate, ScheduleCreate,
                     AppointmentCreate, AppointmentAdjustManual,
                     AppointmentDecline, AppointmentNotes)
from auth import hash_password
from typing import Optional
from datetime import datetime, timezone, timedelta


# ── Auth ──────────────────────────────────────────────────────────────────────

def create_user(db: Session, email: str, password: str, role: str):
    hashed = hash_password(password)
    user = User(email=email, hashed_password=hashed, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


# ── Doctor ────────────────────────────────────────────────────────────────────

def create_doctor(db: Session, data: DoctorCreate, user_id: int = None):
    doctor = Doctor(
        first_name=data.first_name,
        last_name=data.last_name,
        specialization=data.specialization,
        phone=data.phone,
        user_id=user_id
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


def set_doctor_schedule(db: Session, doctor_id: int, data: ScheduleCreate):
    # Check if schedule already exists — if so update it, if not create it
    existing = db.query(DoctorSchedule).filter(
        DoctorSchedule.doctor_id == doctor_id
    ).first()

    if existing:
        existing.slots_per_day = data.slots_per_day
        existing.slot_duration_minutes = data.slot_duration_minutes
        existing.work_start_time = data.work_start_time
        existing.work_end_time = data.work_end_time
        db.commit()
        db.refresh(existing)
        return existing

    schedule = DoctorSchedule(
        doctor_id=doctor_id,
        slots_per_day=data.slots_per_day,
        slot_duration_minutes=data.slot_duration_minutes,
        work_start_time=data.work_start_time,
        work_end_time=data.work_end_time
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


def generate_slots_for_date(db: Session, doctor_id: int, date: datetime):
    schedule = db.query(DoctorSchedule).filter(
        DoctorSchedule.doctor_id == doctor_id
    ).first()

    if not schedule:
        return None, "Doctor has no schedule set"

    # Clear existing slots for this date to avoid duplicates
    existing = db.query(TimeSlot).filter(
        TimeSlot.doctor_id == doctor_id,
        TimeSlot.date == date.date()
    ).all()
    for slot in existing:
        db.delete(slot)
    db.commit()

    # Build new slots starting from work_start_time
    slots = []
    current_time = datetime.combine(date.date(), schedule.work_start_time)
    duration = timedelta(minutes=schedule.slot_duration_minutes)

    for i in range(schedule.slots_per_day):
        end_time = current_time + duration
        slot = TimeSlot(
            doctor_id=doctor_id,
            date=date.date(),
            start_time=current_time,
            end_time=end_time,
            slot_type=SlotTypeEnum.working,
            status=SlotStatusEnum.available
        )
        db.add(slot)
        slots.append(slot)
        current_time = end_time

    db.commit()
    return slots, "Slots generated"


def get_next_available_slot(db: Session, doctor_id: int):
    return db.query(TimeSlot).filter(
        TimeSlot.doctor_id == doctor_id,
        TimeSlot.status == SlotStatusEnum.available,
        TimeSlot.slot_type == SlotTypeEnum.working,
        TimeSlot.start_time > datetime.now(timezone.utc)
    ).order_by(TimeSlot.start_time).first()


# ── Patient ───────────────────────────────────────────────────────────────────

def create_patient(db: Session, data: PatientCreate, user_id: int = None):
    patient = Patient(
        first_name=data.first_name,
        last_name=data.last_name,
        age=data.age,
        gender=data.gender,
        phone=data.phone,
        user_id=user_id
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def get_available_slots(db: Session, doctor_id: int, date: datetime = None):
    query = db.query(TimeSlot).filter(
        TimeSlot.doctor_id == doctor_id,
        TimeSlot.status == SlotStatusEnum.available,
        TimeSlot.slot_type == SlotTypeEnum.working
    )
    if date:
        query = query.filter(TimeSlot.date == date.date())
    return query.order_by(TimeSlot.start_time).all()


def book_appointment(db: Session, patient_id: int, data: AppointmentCreate):
    slot = db.get(TimeSlot, data.slot_id)
    if not slot:
        return None, "Slot not found"
    if slot.status != SlotStatusEnum.available:
        return None, "Slot is not available"
    if slot.slot_type != SlotTypeEnum.working:
        return None, "Cannot book a break or free slot"

    slot.status = SlotStatusEnum.booked
    appointment = Appointment(
        patient_id=patient_id,
        doctor_id=data.doctor_id,
        slot_id=data.slot_id,
        reason=data.reason
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment, "Appointment booked"


# ── Doctor Actions ────────────────────────────────────────────────────────────

def approve_appointment(db: Session, appointment_id: int, doctor_id: int):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        return None, "Appointment not found"
    if appointment.doctor_id != doctor_id:
        return None, "This appointment does not belong to you"
    if appointment.status != AppointmentStatusEnum.pending:
        return None, f"Cannot approve an appointment with status: {appointment.status.value}"

    appointment.status = AppointmentStatusEnum.approved
    appointment.notification_sent = True
    db.commit()
    db.refresh(appointment)
    return appointment, "Appointment approved"


def decline_appointment(db: Session, appointment_id: int,
                         doctor_id: int, reason: str):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        return None, "Appointment not found"
    if appointment.doctor_id != doctor_id:
        return None, "This appointment does not belong to you"
    if appointment.status != AppointmentStatusEnum.pending:
        return None, f"Cannot decline an appointment with status: {appointment.status.value}"
    if not reason or not reason.strip():
        return None, "A reason is required when declining"

    # Free the original slot back to available
    slot = db.get(TimeSlot, appointment.slot_id)
    if slot:
        slot.status = SlotStatusEnum.available

    appointment.status = AppointmentStatusEnum.declined
    appointment.decline_reason = reason
    appointment.notification_sent = True
    db.commit()
    db.refresh(appointment)
    return appointment, "Appointment declined"


def adjust_appointment_auto(db: Session, appointment_id: int, doctor_id: int):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        return None, "Appointment not found"
    if appointment.doctor_id != doctor_id:
        return None, "This appointment does not belong to you"
    if appointment.status != AppointmentStatusEnum.pending:
        return None, f"Cannot adjust an appointment with status: {appointment.status.value}"

    next_slot = get_next_available_slot(db, doctor_id)
    if not next_slot:
        return None, "No available slots to reschedule to"

    # Free the original slot
    original_slot = db.get(TimeSlot, appointment.slot_id)
    if original_slot:
        original_slot.status = SlotStatusEnum.available

    # Reserve the new slot
    next_slot.status = SlotStatusEnum.booked

    appointment.status = AppointmentStatusEnum.adjusted_auto
    appointment.adjusted_slot_id = next_slot.id
    appointment.notification_sent = True
    db.commit()
    db.refresh(appointment)
    return appointment, f"Appointment moved to {next_slot.start_time}"


def adjust_appointment_manual(db: Session, appointment_id: int,
                               doctor_id: int, new_slot_id: int):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        return None, "Appointment not found"
    if appointment.doctor_id != doctor_id:
        return None, "This appointment does not belong to you"
    if appointment.status != AppointmentStatusEnum.pending:
        return None, f"Cannot adjust an appointment with status: {appointment.status.value}"

    new_slot = db.get(TimeSlot, new_slot_id)
    if not new_slot:
        return None, "New slot not found"
    if new_slot.status != SlotStatusEnum.available:
        return None, "That slot is not available"
    if new_slot.slot_type != SlotTypeEnum.working:
        return None, "Cannot schedule into a break or free slot"

    # Free the original slot
    original_slot = db.get(TimeSlot, appointment.slot_id)
    if original_slot:
        original_slot.status = SlotStatusEnum.available

    # Reserve the new slot
    new_slot.status = SlotStatusEnum.booked

    appointment.status = AppointmentStatusEnum.adjusted_manual
    appointment.adjusted_slot_id = new_slot_id
    appointment.notification_sent = True
    db.commit()
    db.refresh(appointment)
    return appointment, "Appointment rescheduled"


def add_notes(db: Session, appointment_id: int, doctor_id: int, notes: str):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        return None, "Appointment not found"
    if appointment.doctor_id != doctor_id:
        return None, "This appointment does not belong to you"
    if appointment.status != AppointmentStatusEnum.completed:
        return None, "Notes can only be added to completed appointments"

    appointment.notes = notes
    db.commit()
    db.refresh(appointment)
    return appointment, "Notes added"


def complete_appointment(db: Session, appointment_id: int, doctor_id: int):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        return None, "Appointment not found"
    if appointment.doctor_id != doctor_id:
        return None, "This appointment does not belong to you"
    if appointment.status not in [
        AppointmentStatusEnum.approved,
        AppointmentStatusEnum.confirmed
    ]:
        return None, f"Cannot complete an appointment with status: {appointment.status.value}"

    appointment.status = AppointmentStatusEnum.completed
    db.commit()
    db.refresh(appointment)
    return appointment, "Appointment completed"


# ── Patient Actions ───────────────────────────────────────────────────────────

def confirm_adjustment(db: Session, appointment_id: int, patient_id: int):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        return None, "Appointment not found"
    if appointment.patient_id != patient_id:
        return None, "This appointment does not belong to you"
    if appointment.status not in [
        AppointmentStatusEnum.adjusted_auto,
        AppointmentStatusEnum.adjusted_manual
    ]:
        return None, f"Nothing to confirm for status: {appointment.status.value}"

    appointment.status = AppointmentStatusEnum.confirmed
    db.commit()
    db.refresh(appointment)
    return appointment, "Appointment confirmed"


def cancel_appointment(db: Session, appointment_id: int, user_id: int,
                        role: str):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        return None, "Appointment not found"

    # Patients can only cancel their own appointments
    if role == "patient":
        patient = db.query(Patient).filter(
            Patient.user_id == user_id
        ).first()
        if not patient or appointment.patient_id != patient.id:
            return None, "This appointment does not belong to you"

    # These are the only statuses that can be cancelled
    cancellable = [
        AppointmentStatusEnum.approved,
        AppointmentStatusEnum.confirmed,
        AppointmentStatusEnum.adjusted_auto,
        AppointmentStatusEnum.adjusted_manual
    ]
    if appointment.status not in cancellable:
        return None, f"Cannot cancel an appointment with status: {appointment.status.value}"

    # Figure out which slot is currently active and free it
    active_slot_id = appointment.adjusted_slot_id or appointment.slot_id
    slot = db.get(TimeSlot, active_slot_id)
    if slot:
        slot.status = SlotStatusEnum.available

    appointment.status = AppointmentStatusEnum.cancelled
    db.commit()
    db.refresh(appointment)
    return appointment, "Appointment cancelled"


# ── Queries ───────────────────────────────────────────────────────────────────

def get_doctor_appointments(db: Session, doctor_id: int, status: str = None):
    query = db.query(Appointment).filter(Appointment.doctor_id == doctor_id)
    if status:
        query = query.filter(Appointment.status == status)
    return query.order_by(Appointment.created_at.desc()).all()


def get_clinic_summary(db: Session):
    from sqlalchemy import func
    total = db.query(func.count(Appointment.id)).scalar()
    pending = db.query(func.count(Appointment.id)).filter(
        Appointment.status == AppointmentStatusEnum.pending).scalar()
    approved = db.query(func.count(Appointment.id)).filter(
        Appointment.status == AppointmentStatusEnum.approved).scalar()
    completed = db.query(func.count(Appointment.id)).filter(
        Appointment.status == AppointmentStatusEnum.completed).scalar()
    cancelled = db.query(func.count(Appointment.id)).filter(
        Appointment.status == AppointmentStatusEnum.cancelled).scalar()
    declined = db.query(func.count(Appointment.id)).filter(
        Appointment.status == AppointmentStatusEnum.declined).scalar()

    return {
        "total_appointments": total,
        "pending": pending,
        "approved": approved,
        "completed": completed,
        "cancelled": cancelled,
        "declined": declined
    }
