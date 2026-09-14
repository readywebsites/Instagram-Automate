# Instagram 90-Day Auto Posting Website

Starter MVP for scheduling Instagram image posts for up to 90 days.

## Stack
- Django
- SQLite for local development
- Bootstrap 5
- Celery/Redis-ready architecture
- Instagram/Meta API integration placeholders

## Run locally

```bash
python -m venv env
# Windows:
env\Scripts\activate
# Linux/macOS:
source env/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/

## Important
Instagram publishing must use Meta's official API and an eligible Instagram Professional account. Add your Meta App credentials and OAuth flow before production use.
