# Taskautomation

Self-hosted project management and team collaboration platform built as a single deployable repository.

## Stack

- Django + Django REST Framework
- React + TypeScript + Vite
- PostgreSQL
- Docker Compose
- Gunicorn
- Caddy for automatic HTTPS in domain mode

## Installation

Clone the repository and run the installer:

```bash
git clone https://github.com/pushpinder6805/Taskautomation.git
cd Taskautomation
sudo bash install.sh
```

The installer is designed to handle the rest. It:

- Detects the Linux distribution
- Checks whether Docker is installed
- Installs Docker automatically when needed on supported Ubuntu/Debian systems
- Checks for Docker Compose v2 and installs it when missing
- Asks whether the application should run on a domain or via server IP/local port
- Validates that a supplied domain resolves to the current server before continuing
- Detects port 80/443 conflicts before domain deployment
- Can stop a conflicting host nginx/apache2/caddy service after explicit confirmation
- Collects administrator details
- Optionally collects SMTP configuration
- Generates Django and PostgreSQL secrets automatically
- Creates `.env` automatically with secure file permissions
- Builds the React frontend and Django backend
- Starts PostgreSQL and the application
- Runs migrations and creates the initial administrator
- Uses Caddy to request and renew HTTPS certificates automatically in domain mode
- Performs an application health check before reporting success

## Domain mode

Domain mode requires DNS to already point at the VPS. For example:

```text
tasks.example.com -> YOUR_SERVER_PUBLIC_IP
```

The installer checks this before deployment. Ports 80 and 443 must be available for automatic HTTPS.

## Local/server-IP mode

If a domain is not required, choose local/server-IP mode. The installer finds an available port starting from 8080 and exposes the application there.

## Updating

```bash
cd Taskautomation
git pull
sudo bash install.sh
```

When an existing `.env` is found, the installer asks whether to keep it or reconfigure the installation.

## Health check

```text
GET /api/health/
```

## Repository layout

```text
Taskautomation/
├── backend/
├── frontend/
├── Caddyfile
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── install.sh
└── .env.example
```
