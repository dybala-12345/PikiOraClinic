# Piki Ora Medical Centre – Clinic Appointment System

A Django web application that replaces Piki Ora Medical Centre's manual booking process.
Patients register, log in and book appointments with doctors. Clinic staff manage doctors,
schedules, appointment slots, bookings and patient accounts through a **custom administrator
dashboard**. The built-in Django Admin is **not** used as the admin interface.

---

## Features

### Patients
| Requirement | Where |
|---|---|
| Register and log in | `/accounts/register/`, `/accounts/login/` |
| View doctors and their weekly consultation schedules | `/doctors/` |
| View available slots and book for a specific date/time | `/doctors/<id>/` → `/book/<slot>/` |
| Receive a confirmation notification | Confirmation page, in-app notifications (bell icon) and e-mail |
| View upcoming appointments | `/appointments/` |
| Edit (move to another free time / change reason) or cancel | `/appointments/<id>/edit/`, `/appointments/<id>/cancel/` |
| Update own contact details | `/accounts/profile/` |

### Administrators (custom dashboard at `/dashboard/`)
| Requirement | Where |
|---|---|
| Secure dashboard (staff only, 403 for patients) | `core/permissions.py` → `AdminRequiredMixin` |
| Add, edit, delete doctor profiles | Dashboard → Doctors |
| Weekly consultation schedules per doctor | Dashboard → Doctors → doctor page |
| Create and manage slots (single, bulk-generate from schedules, open/close, edit, delete) | Dashboard → Appointment slots |
| View all bookings with search and filters | Dashboard → Appointments |
| Edit or cancel any appointment (patient is notified) | Dashboard → Appointments → Edit / Cancel |
| Manage patient accounts (add, edit, deactivate, set password, delete) | Dashboard → Patients |

### Double-booking prevention (3 layers)
1. Only free slots are ever shown or offered in forms.
2. Bookings run inside a database transaction that locks the slot row
   (`select_for_update`) and re-checks it before saving (`clinic/services.py`).
3. A partial unique constraint in the database, `one_active_booking_per_slot`, allows only
   **one** appointment with status `booked` per slot. Cancelled appointments stay in the
   history and the slot becomes available again.

Patients also cannot hold two appointments at the same time.

---

## Project structure

```
config/        Django settings, root URLs, WSGI (gunicorn)
core/          Shared code: role-based access control, Bootstrap form mixin, template context
accounts/      PatientProfile model, registration, profile, role-based redirect after login
clinic/        Doctor, DoctorSchedule, AppointmentSlot, Appointment, Notification models;
               booking service layer; patient pages; management commands; tests
dashboard/     Custom administrator dashboard (views, forms, URLs)
templates/     All HTML templates (Bootstrap 5, responsive)
static/css/    Custom styles
build.sh       Render build script
```

### Data model
```
User 1──1 PatientProfile
Doctor 1──* DoctorSchedule        (weekly sessions, e.g. Mon 09:00–12:00, 15-min slots)
Doctor 1──* AppointmentSlot       (real bookable times on specific dates)
AppointmentSlot 1──* Appointment  (max ONE with status "booked" – DB constraint)
User (patient) 1──* Appointment
User 1──* Notification ──0..1 Appointment
```

---

## Running it locally in PyCharm

1. **Open the project**: *File → Open…* and choose this folder.
2. **Create a virtual environment**: *Settings → Project → Python Interpreter → Add Interpreter →
   Add Local Interpreter → Virtualenv* (Python 3.12 or newer). PyCharm may also offer to do this
   automatically from `requirements.txt`. Click yes.
3. Open PyCharm's **Terminal** (bottom toolbar) and run:

   ```bash
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py seed_demo
   python manage.py createsuperuser
   python manage.py runserver
   ```

4. Open <http://127.0.0.1:8000>. Log in with your superuser to reach the custom dashboard at
   `/dashboard/`. While developing, Django Admin is also at `/admin/` for testing only (all
   models are registered in each app's `admin.py`). It is switched off when `DEBUG=False`.

Locally the app uses SQLite (`db.sqlite3`), so no database setup is needed. To use PostgreSQL,
copy `.env.example` to `.env` and set `DATABASE_URL`.

### Demo accounts (created by `seed_demo`)
| Role | Username | Password |
|---|---|---|
| Administrator | `clinicadmin` | `PikiOra@Admin2026` |
| Patient | `demopatient` | `PikiOra@Patient2026` |

Change these passwords (or delete the accounts) on a real deployment.

### Automated tests
```bash
python manage.py test
```
The tests cover double booking, the database constraint, cancellation and re-booking, patient
permissions, the patient booking/edit/cancel flow, registration, slot generation and dashboard
access control.

---

## Deploying to Render

1. Push the code to GitHub.
2. **Database**: in Render choose *New → PostgreSQL* (free plan) and copy its
   **Internal Database URL**. A Neon PostgreSQL URL also works.
3. **Web service**: *New → Web Service* → connect your GitHub repository, then set:
   - **Root Directory**: the folder that contains `manage.py` (for example `Assignment 1`)
   - **Runtime**: Python 3
   - **Build Command**: `bash build.sh`
   - **Start Command**: `gunicorn config.wsgi:application`
4. **Environment variables** (*Environment* tab):

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the database URL from step 2 |
   | `SECRET_KEY` | a long random string (click *Generate*) |
   | `DEBUG` | `False` |
   | `ADMIN_USERNAME` | your admin username |
   | `ADMIN_EMAIL` | your e-mail |
   | `ADMIN_PASSWORD` | a strong password |

5. Deploy. `build.sh` installs packages, collects static files, runs migrations, creates the
   administrator and loads demo doctors and slots the first time.

`RENDER_EXTERNAL_HOSTNAME` is added to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`
automatically.

Booking confirmation e-mails are printed to the Render logs by default. To send real
e-mails, set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` plus `EMAIL_HOST`,
`EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD`.

---

## Technology
Django 5.2 LTS · PostgreSQL (Render) / SQLite (local) · Django ORM · Bootstrap 5 ·
WhiteNoise · gunicorn · Render
