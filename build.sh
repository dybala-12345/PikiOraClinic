#!/usr/bin/env bash
# Render build script. Render runs this on every deploy:
#   Build Command:  bash build.sh
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate --no-input

# Create/update the administrator from ADMIN_USERNAME / ADMIN_PASSWORD env vars.
python manage.py ensure_admin
# Load demo doctors, schedules and slots the first time only.
python manage.py seed_demo --if-empty
