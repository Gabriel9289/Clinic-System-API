# Clinic Booking API

A REST API for managing a clinic — built with FastAPI, SQLAlchemy, and PostgreSQL.

## Live URL

deploying on Railway: web-production-38fae.up.railway.app/docs

---

## What It Does

A fully role-based clinic management system where admins, doctors, patients, and receptionists each get access to only what they need.

**Admin**

* Manage doctors and users
* View all appointments
* Access system-wide dashboard with stats

**Doctor**

* Set availability schedule
* Generate appointment slots
* Approve, decline, or adjust bookings
* Add notes and complete appointments

**Patient**

* View available doctor slots
* Book appointments
* Confirm or cancel appointments
* View personal appointment history

**Receptionist**

* Assist with bookings
* Manage appointments on behalf of patients

---

## Features

* JWT authentication — login returns a token, token protects every route
* Role-based access control — 403 returned automatically for unauthorized roles
* Smart scheduling — doctors define availability, slots generated automatically
* Appointment lifecycle — booking → approval → confirmation → completion
* Adjustment system — doctors can reschedule appointments (manual or auto)
* Notes system — doctors can attach notes to appointments
* Admin dashboard — live system overview

---

## Tech Stack

* **Python** — core language
* **FastAPI** — web framework and automatic API docs
* **SQLAlchemy** — ORM for database access
* **PostgreSQL** — database
* **JWT (python-jose)** — authentication tokens
* **bcrypt (passlib)** — password hashing
* **Railway** — deployment and hosted database

---

## Running Locally

**1. Clone the repository**

```
git clone https://github.com/your-username/clinic-api.git
cd clinic_api
```

**2. Create a virtual environment and install dependencies**

```
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
```

**3. Create a `.env` file in the project root**

```
DATABASE_URL=postgresql://user:password@localhost/clinic_db
SECRET_KEY=your_secret_key_here
```

**4. Create the database tables**

```
python create_tables.py
```

**5. Start the server**

```
uvicorn main:app --reload
```

**6. Open the docs**

```
http://localhost:8000/docs
```

---

## API Overview

| Method | Endpoint                    | Role    | Description                   |
| ------ | --------------------------- | ------- | ----------------------------- |
| POST   | /register                   | Public  | Register a new user           |
| POST   | /login                      | Public  | Login and receive a JWT token |
| POST   | /doctors                    | Admin   | Create a doctor               |
| GET    | /doctors                    | Public  | List all doctors              |
| POST   | /my-schedule                | Doctor  | Set availability              |
| POST   | /my-schedule/generate-slots | Doctor  | Generate time slots           |
| GET    | /slots/{doctor_id}          | Public  | View available slots          |
| POST   | /appointments               | Patient | Book an appointment           |
| GET    | /my-appointments            | Patient | View own appointments         |
| POST   | /appointments/{id}/approve  | Doctor  | Approve appointment           |
| POST   | /appointments/{id}/decline  | Doctor  | Decline appointment           |
| POST   | /appointments/{id}/adjust   | Doctor  | Adjust appointment time       |
| POST   | /appointments/{id}/confirm  | Patient | Confirm adjusted appointment  |
| POST   | /appointments/{id}/complete | Doctor  | Mark as completed             |
| POST   | /appointments/{id}/cancel   | Patient | Cancel appointment            |
| GET    | /appointments               | Admin   | View all appointments         |
| GET    | /admin/dashboard            | Admin   | System summary                |

---

## Project Structure

```
clinic_api/
├── main.py          — routes and endpoints
├── database.py      — SQLAlchemy models and database connection
├── schemas.py       — Pydantic request and response models
├── services.py      — database query logic
├── auth.py          — JWT tokens, password hashing, role checking
├── create_tables.py — run once to create all database tables
├── requirements.txt — Python dependencies
└── Procfile         — Railway startup command
```

---

## Author

Gabriel — https://github.com/your-username

Backend developer focused on Python, FastAPI, PostgreSQL, and systems that actually work.
