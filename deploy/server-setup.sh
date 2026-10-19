#!/usr/bin/env bash
# 운영 서버(Ubuntu 24.04) 첫 세팅. 여러 번 실행해도 안전합니다.
# 사용: 서버에 SSH로 접속한 뒤
#   curl -fsSL https://raw.githubusercontent.com/dole-guide-ai/dole-guide-ai/main/deploy/server-setup.sh | bash
set -euo pipefail

REPO_URL="https://github.com/dole-guide-ai/dole-guide-ai.git"
APP_DIR="/opt/dole-guide-ai"
SWAP_SIZE="2G"

step() { printf '\n\033[1m▶ %s\033[0m\n' "$1"; }

if [ "$(id -u)" -eq 0 ]; then
  echo "root가 아닌 기본 사용자(ubuntu)로 실행하세요. 필요한 곳에서 sudo를 씁니다." >&2
  exit 1
fi

step "패키지 업데이트"
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
sudo apt-get install -y ca-certificates curl git unattended-upgrades fail2ban

step "Docker 설치"
if ! command -v docker >/dev/null 2>&1; then
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  # shellcheck source=/dev/null
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" |
    sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
sudo usermod -aG docker "$USER"
sudo systemctl enable --now docker

step "스왑 ${SWAP_SIZE} (메모리가 순간적으로 부족할 때 대비)"
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l "$SWAP_SIZE" /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

step "보안 업데이트 자동 적용"
sudo dpkg-reconfigure -f noninteractive unattended-upgrades

step "SSH 보안 (키 로그인만, root 로그인 금지)"
sudo tee /etc/ssh/sshd_config.d/99-dole-guide.conf >/dev/null <<'CONF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
CONF
sudo systemctl reload ssh

step "fail2ban (SSH 로그인 실패가 반복되는 IP 차단)"
sudo tee /etc/fail2ban/jail.d/sshd.local >/dev/null <<'CONF'
[sshd]
enabled = true
maxretry = 5
bantime = 1h
CONF
sudo systemctl enable --now fail2ban
sudo systemctl restart fail2ban

step "레포 내려받기 (${APP_DIR})"
sudo mkdir -p "$APP_DIR"
sudo chown "$USER":"$USER" "$APP_DIR"
if [ ! -d "$APP_DIR/.git" ]; then
  git clone --branch main "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" pull --ff-only
fi

step "운영 설정 파일 (.env)"
if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/deploy/.env.example" "$APP_DIR/.env"
  echo "  $APP_DIR/.env 를 만들었습니다. 값을 채워 주세요: nano $APP_DIR/.env"
else
  echo "  $APP_DIR/.env 가 이미 있어 그대로 둡니다."
fi
chmod 600 "$APP_DIR/.env"

cat <<DONE

✔ 서버 세팅 완료

다음 순서:
  1. 한 번 로그아웃했다가 다시 접속하세요 (docker 그룹 권한 적용): exit
  2. 설정 파일 채우기: nano $APP_DIR/.env
  3. 첫 배포:
     cd $APP_DIR
     docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile full up -d --build
     docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend alembic upgrade head
DONE
