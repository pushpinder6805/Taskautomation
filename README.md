# Taskautomation

Self-hosted project management and team collaboration platform built as a single deployable repository.

## Stack

- Django + Django REST Framework
- React + TypeScript + Vite
- PostgreSQL
- Docker Compose
- Gunicorn
- WhiteNoise

## Deployment

```bash
git clone https://github.com/pushpinder6805/Taskautomation.git
cd Taskautomation
cp .env.example .env
# edit production values in .env
docker compose up -d --build
```

The Docker image builds the React frontend, installs the Django backend, runs database migrations, collects static files, creates the initial administrator from environment variables, and starts Gunicorn automatically.

## Required configuration

Set at minimum:

```env
SECRET_KEY=replace-with-a-long-random-secret
POSTGRES_PASSWORD=replace-with-a-strong-password
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=replace-with-a-strong-password
ALLOWED_HOSTS=your-domain.com
```

SMTP is optional and can be configured in `.env`.

## Health check

`GET /api/health/`

## Repository layout

```text
Taskautomation/
├── backend/
├── frontend/
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
└── .env.example
```
