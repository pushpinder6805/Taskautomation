#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="Taskautomation"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$REPO_DIR/.env"

red='\033[0;31m'; green='\033[0;32m'; yellow='\033[1;33m'; blue='\033[0;34m'; reset='\033[0m'
info(){ printf "${blue}==>${reset} %s\n" "$*"; }
ok(){ printf "${green}✓${reset} %s\n" "$*"; }
warn(){ printf "${yellow}!${reset} %s\n" "$*"; }
die(){ printf "${red}ERROR:${reset} %s\n" "$*" >&2; exit 1; }

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  if command -v sudo >/dev/null 2>&1; then
    exec sudo -E bash "$0" "$@"
  fi
  die "Run this installer as root (or install sudo)."
fi

cd "$REPO_DIR"

printf '\n%s installer\n' "$APP_NAME"
printf '%s\n\n' '----------------------------------------'

# ---------- OS / package helpers ----------
[[ -r /etc/os-release ]] || die "Cannot detect Linux distribution."
# shellcheck disable=SC1091
source /etc/os-release
OS_ID="${ID:-unknown}"
OS_LIKE="${ID_LIKE:-}"

apt_install(){
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y "$@"
}

ensure_base_tools(){
  local missing=()
  for cmd in curl openssl ss getent; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done
  [[ ${#missing[@]} -eq 0 ]] && return

  if [[ "$OS_ID" == "ubuntu" || "$OS_ID" == "debian" || "$OS_LIKE" == *debian* ]]; then
    info "Installing required system tools..."
    apt_install curl openssl iproute2 libc-bin ca-certificates
  else
    die "Automatic dependency installation currently supports Ubuntu/Debian. Detected: $OS_ID"
  fi
}

ensure_docker(){
  if command -v docker >/dev/null 2>&1; then
    ok "Docker found: $(docker --version)"
  else
    info "Docker is not installed. Installing it automatically..."
    if [[ "$OS_ID" == "ubuntu" || "$OS_ID" == "debian" || "$OS_LIKE" == *debian* ]]; then
      apt_install docker.io
      systemctl enable --now docker 2>/dev/null || true
    else
      die "Automatic Docker installation currently supports Ubuntu/Debian."
    fi
  fi

  if docker compose version >/dev/null 2>&1; then
    ok "Docker Compose found: $(docker compose version --short 2>/dev/null || docker compose version)"
    return
  fi

  info "Docker Compose is missing. Installing it automatically..."
  if [[ "$OS_ID" == "ubuntu" || "$OS_ID" == "debian" || "$OS_LIKE" == *debian* ]]; then
    apt-get update -y
    if apt-cache show docker-compose-v2 >/dev/null 2>&1; then
      apt-get install -y docker-compose-v2
    elif apt-cache show docker-compose-plugin >/dev/null 2>&1; then
      apt-get install -y docker-compose-plugin
    else
      die "Docker Compose package was not found in this server's configured repositories."
    fi
  else
    die "Automatic Docker Compose installation currently supports Ubuntu/Debian."
  fi

  docker compose version >/dev/null 2>&1 || die "Docker Compose installation did not complete successfully."
  ok "Docker Compose installed."
}

ensure_base_tools
ensure_docker

# ---------- helpers ----------
valid_email(){ [[ "$1" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]]; }
port_busy(){ ss -H -ltn "sport = :$1" 2>/dev/null | grep -q .; }
port_details(){ ss -ltnp "sport = :$1" 2>/dev/null || true; }

find_free_port(){
  local p="$1"
  while port_busy "$p"; do p=$((p+1)); done
  printf '%s' "$p"
}

public_ipv4(){
  curl -4fsS --max-time 8 https://api.ipify.org 2>/dev/null || \
  curl -4fsS --max-time 8 https://ifconfig.me/ip 2>/dev/null || true
}

domain_ipv4s(){
  getent ahostsv4 "$1" 2>/dev/null | awk '{print $1}' | sort -u
}

validate_domain(){
  local domain="$1" server_ip dns_ips
  server_ip="$(public_ipv4)"
  [[ -n "$server_ip" ]] || die "Could not determine this server's public IPv4 address. Check outbound internet access and retry."
  dns_ips="$(domain_ipv4s "$domain")"
  [[ -n "$dns_ips" ]] || die "Domain '$domain' does not currently resolve to an IPv4 address. Create its DNS A record first."

  info "Server public IP: $server_ip"
  info "Domain resolves to: $(echo "$dns_ips" | tr '\n' ' ')"
  if ! grep -Fxq "$server_ip" <<<"$dns_ips"; then
    die "DNS is not pointing '$domain' to this server ($server_ip). Update the domain's A record, wait for DNS propagation, then run ./install.sh again."
  fi
  ok "DNS validation passed."
}

handle_web_ports(){
  local busy=0
  for p in 80 443; do
    if port_busy "$p"; then
      busy=1
      warn "Port $p is already in use:"
      port_details "$p"
    fi
  done
  [[ $busy -eq 0 ]] && return

  printf '\nDomain mode needs ports 80 and 443 for automatic HTTPS.\n'
  read -r -p "May the installer stop and disable a detected nginx/apache2/caddy service? [y/N]: " answer
  [[ "$answer" =~ ^[Yy]$ ]] || die "Free ports 80 and 443, then run the installer again."

  local stopped=0
  for svc in nginx apache2 caddy; do
    if systemctl is-active --quiet "$svc" 2>/dev/null || systemctl is-enabled --quiet "$svc" 2>/dev/null; then
      info "Stopping $svc..."
      systemctl disable --now "$svc" || true
      stopped=1
    fi
  done

  sleep 1
  for p in 80 443; do
    if port_busy "$p"; then
      port_details "$p"
      die "Port $p is still occupied (possibly by another Docker container or service). Stop that service and retry."
    fi
  done
  [[ $stopped -eq 1 ]] && ok "Conflicting host web service disabled."
}

# ---------- interactive configuration ----------
if [[ -f "$ENV_FILE" ]]; then
  read -r -p "An existing .env configuration was found. Reconfigure it? [y/N]: " reconfigure
  if [[ ! "$reconfigure" =~ ^[Yy]$ ]]; then
    info "Using existing configuration."
    set -a; source "$ENV_FILE"; set +a
    docker compose up -d --build
    ok "Deployment command completed."
    exit 0
  fi
fi

printf '\nHow should this installation be accessed?\n'
printf '  1) Domain with automatic HTTPS (recommended)\n'
printf '  2) Local/server IP with a port\n'
while true; do
  read -r -p "Choose [1/2]: " mode
  case "$mode" in 1|2) break;; *) warn "Enter 1 or 2.";; esac
done

DOMAIN=""
COMPOSE_PROFILES=""
if [[ "$mode" == "1" ]]; then
  while true; do
    read -r -p "Domain (example: tasks.example.com): " DOMAIN
    DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN%%/*}"
    [[ "$DOMAIN" =~ ^([A-Za-z0-9-]+\.)+[A-Za-z]{2,}$ ]] && break
    warn "Enter a valid hostname only, without https:// or a path."
  done
  validate_domain "$DOMAIN"
  handle_web_ports
  COMPOSE_PROFILES="domain"
  INTERNAL_PORT="$(find_free_port 18080)"
  APP_BIND="127.0.0.1:${INTERNAL_PORT}"
  ALLOWED_HOSTS="$DOMAIN,localhost,127.0.0.1"
  SITE_URL="https://$DOMAIN"
else
  default_port="$(find_free_port 8080)"
  read -r -p "Local HTTP port [$default_port]: " LOCAL_PORT
  LOCAL_PORT="${LOCAL_PORT:-$default_port}"
  [[ "$LOCAL_PORT" =~ ^[0-9]+$ ]] || die "Port must be a number."
  (( LOCAL_PORT >= 1 && LOCAL_PORT <= 65535 )) || die "Port must be between 1 and 65535."
  port_busy "$LOCAL_PORT" && die "Port $LOCAL_PORT is already in use. Run the installer again and choose another port."
  APP_BIND="0.0.0.0:${LOCAL_PORT}"
  ALLOWED_HOSTS="*"
  SERVER_IP="$(public_ipv4)"
  SITE_URL="http://${SERVER_IP:-SERVER_IP}:$LOCAL_PORT"
fi

while true; do
  read -r -p "Administrator email: " ADMIN_EMAIL
  valid_email "$ADMIN_EMAIL" && break
  warn "Enter a valid email address."
done

read -r -p "Administrator name [Administrator]: " ADMIN_NAME
ADMIN_NAME="${ADMIN_NAME:-Administrator}"

while true; do
  read -r -s -p "Administrator password (minimum 10 characters): " ADMIN_PASSWORD; printf '\n'
  [[ ${#ADMIN_PASSWORD} -ge 10 ]] || { warn "Password must be at least 10 characters."; continue; }
  read -r -s -p "Confirm administrator password: " ADMIN_PASSWORD_CONFIRM; printf '\n'
  [[ "$ADMIN_PASSWORD" == "$ADMIN_PASSWORD_CONFIRM" ]] && break
  warn "Passwords do not match."
done

SMTP_HOST=""; SMTP_PORT="587"; SMTP_USER=""; SMTP_PASSWORD=""; SMTP_USE_TLS="true"; DEFAULT_FROM_EMAIL="$ADMIN_EMAIL"
read -r -p "Configure SMTP email now? [Y/n]: " smtp_now
if [[ ! "$smtp_now" =~ ^[Nn]$ ]]; then
  read -r -p "SMTP host: " SMTP_HOST
  [[ -n "$SMTP_HOST" ]] || die "SMTP host cannot be empty when SMTP is enabled."
  read -r -p "SMTP port [587]: " SMTP_PORT; SMTP_PORT="${SMTP_PORT:-587}"
  read -r -p "SMTP username: " SMTP_USER
  read -r -s -p "SMTP password: " SMTP_PASSWORD; printf '\n'
  read -r -p "Use TLS? [Y/n]: " smtp_tls
  [[ "$smtp_tls" =~ ^[Nn]$ ]] && SMTP_USE_TLS="false"
  read -r -p "From email [$ADMIN_EMAIL]: " DEFAULT_FROM_EMAIL
  DEFAULT_FROM_EMAIL="${DEFAULT_FROM_EMAIL:-$ADMIN_EMAIL}"
fi

SECRET_KEY="$(openssl rand -hex 48)"
POSTGRES_PASSWORD="$(openssl rand -hex 24)"

cat > "$ENV_FILE" <<EOF
APP_NAME=$APP_NAME
DEBUG=false
SECRET_KEY=$SECRET_KEY
ALLOWED_HOSTS=$ALLOWED_HOSTS
DOMAIN=$DOMAIN
SITE_URL=$SITE_URL
COMPOSE_PROFILES=$COMPOSE_PROFILES
APP_BIND=$APP_BIND

POSTGRES_DB=taskautomation
POSTGRES_USER=taskautomation
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_HOST=db
POSTGRES_PORT=5432

ADMIN_EMAIL=$ADMIN_EMAIL
ADMIN_PASSWORD=$ADMIN_PASSWORD
ADMIN_NAME=$ADMIN_NAME
RESET_ADMIN_PASSWORD=false

SMTP_HOST=$SMTP_HOST
SMTP_PORT=$SMTP_PORT
SMTP_USER=$SMTP_USER
SMTP_PASSWORD=$SMTP_PASSWORD
SMTP_USE_TLS=$SMTP_USE_TLS
DEFAULT_FROM_EMAIL=$DEFAULT_FROM_EMAIL
EOF
chmod 600 "$ENV_FILE"
ok "Configuration written securely to .env"

info "Building and starting $APP_NAME..."
docker compose up -d --build

info "Waiting for the application to become healthy..."
healthy=0
for _ in $(seq 1 40); do
  if curl -fsS --max-time 3 "http://${APP_BIND}/api/health/" 2>/dev/null | grep -q '"status"'; then
    healthy=1
    break
  fi
  sleep 2
done

if [[ $healthy -ne 1 ]]; then
  docker compose ps || true
  docker compose logs --tail=80 app || true
  die "The containers started, but the application health check failed. Review the log output above."
fi

ok "Application health check passed."
if [[ "$mode" == "1" ]]; then
  info "Waiting for HTTPS to become available..."
  https_ready=0
  for _ in $(seq 1 45); do
    if curl -fsS --max-time 5 "https://$DOMAIN/api/health/" 2>/dev/null | grep -q '"status"'; then
      https_ready=1
      break
    fi
    sleep 2
  done
  if [[ $https_ready -eq 1 ]]; then
    ok "HTTPS is working."
  else
    warn "The app is healthy internally, but HTTPS is not ready yet. Check: docker compose logs caddy"
  fi
fi

printf '\n${green}Installation complete.${reset}\n'
printf 'Open: %s\n' "$SITE_URL"
printf 'Admin: %s/admin/\n' "$SITE_URL"
printf '\nUseful commands:\n'
printf '  docker compose ps\n'
printf '  docker compose logs -f\n'
printf '  docker compose pull && docker compose up -d --build\n\n'
