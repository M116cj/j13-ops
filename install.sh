#!/bin/bash
# ============================================================
# j13 Server Installer v1.0
# 封裝安裝程式 — 互動式 TUI
# Usage: sudo bash install.sh
# ============================================================
set -euo pipefail

# ── Colors & helpers ─────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
log()     { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
die()     { echo -e "${RED}[✗]${NC} $*"; exit 1; }
step()    { echo -e "\n${CYAN}${BOLD}▶ $*${NC}"; }
progress(){ echo -e "  ${GREEN}→${NC} $*"; }

[[ $EUID -ne 0 ]] && die "請用 root 執行：sudo bash install.sh"
apt-get install -y -qq whiptail 2>/dev/null || true

# ── Screen dimensions ────────────────────────────────────────
H=24; W=72

# ── Screen 0: Welcome ────────────────────────────────────────
whiptail --title "j13 Server Installer v1.0" \
  --msgbox "\
歡迎使用 j13 伺服器一鍵安裝程式

這台閑置電腦安裝完成後將具備：

  ✦  SSH 安全強化 + UFW 防火牆 + Fail2Ban
  ✦  NVIDIA CUDA 12.1 (RTX 3080)
  ✦  Docker + Portainer 容器管理介面
  ✦  Tailscale VPN        ← 保護層 1（私有網路）
  ✦  Cloudflare Tunnel    ← 保護層 2（公開 HTTP）
  ✦  Ollama + Qwen2.5-7B  ← 本地 AI 模型
  ✦  ops-agent            ← 自動監控 + 修復 + Telegram 通報
  ✦  JupyterLab           ← 遠端訓練介面

按 Enter 繼續" $H $W

# ── Screen 1: Prerequisites check ───────────────────────────
whiptail --title "環境檢查" --infobox "正在檢查系統環境..." 8 $W
sleep 1

UBUNTU_VER=$(lsb_release -rs 2>/dev/null || echo "unknown")
ARCH=$(uname -m)
RAM_GB=$(free -g | awk '/Mem:/{print $2}')
HAS_GPU=$(lspci 2>/dev/null | grep -i nvidia | head -1 | cut -c1-50 || echo "未偵測到")
DISK_GB=$(df -BG / | awk 'NR==2{print $4}' | tr -d 'G')

whiptail --title "系統環境" \
  --msgbox "\
偵測結果：

  作業系統  :  Ubuntu $UBUNTU_VER ($ARCH)
  記憶體    :  ${RAM_GB}GB RAM
  GPU       :  $HAS_GPU
  可用磁碟  :  ${DISK_GB}GB

${RAM_GB} GB RAM $([ "$RAM_GB" -ge 16 ] && echo '✓ 符合需求' || echo '⚠ 建議 ≥ 16GB')
${DISK_GB} GB 磁碟 $([ "$DISK_GB" -ge 100 ] && echo '✓ 符合需求' || echo '⚠ 建議 ≥ 100GB')

按 Enter 繼續" $H $W

# ── Screen 2: Collect settings ───────────────────────────────
# Server hostname
HOSTNAME_INPUT=$(whiptail --title "基本設定" \
  --inputbox "伺服器名稱（Tailscale hostname，建議用英文）\n預設：j13-server" \
  10 $W "j13-server" 3>&1 1>&2 2>&3) || die "已取消"

# Tailscale
TAILSCALE_KEY=$(whiptail --title "保護層 1 — Tailscale" \
  --inputbox "Tailscale Auth Key\n\n取得方式：https://login.tailscale.com/admin/settings/keys\n→ 點 Generate auth key → 勾 Reusable → 複製" \
  12 $W "" 3>&1 1>&2 2>&3) || die "已取消"
[[ -z "$TAILSCALE_KEY" ]] && die "Tailscale Auth Key 不可為空"

# Cloudflare
CF_TOKEN=$(whiptail --title "保護層 2 — Cloudflare Tunnel" \
  --inputbox "Cloudflare Tunnel Token\n\n取得方式：Cloudflare Dashboard → Zero Trust\n→ Networks → Tunnels → Create a tunnel\n→ 選 cloudflared → 複製 token" \
  13 $W "" 3>&1 1>&2 2>&3) || die "已取消"
[[ -z "$CF_TOKEN" ]] && die "Cloudflare Token 不可為空"

# Telegram
TG_TOKEN=$(whiptail --title "Telegram 通知設定 (1/2)" \
  --inputbox "Telegram Bot Token\n\n取得方式：Telegram → 搜尋 @BotFather\n→ /newbot → 複製 token" \
  12 $W "" 3>&1 1>&2 2>&3) || die "已取消"
[[ -z "$TG_TOKEN" ]] && die "Telegram Bot Token 不可為空"

TG_CHAT=$(whiptail --title "Telegram 通知設定 (2/2)" \
  --inputbox "Telegram Chat ID\n\n取得方式：Telegram → 搜尋 @userinfobot\n→ 發送任意訊息 → 複製 id 數字" \
  12 $W "" 3>&1 1>&2 2>&3) || die "已取消"
[[ -z "$TG_CHAT" ]] && die "Telegram Chat ID 不可為空"

# ── Screen 3: Confirm ────────────────────────────────────────
USERNAME="${SUDO_USER:-$(logname 2>/dev/null || echo ubuntu)}"

whiptail --title "確認安裝設定" --yesno "\
以下設定確認無誤後將開始安裝：

  伺服器名稱   :  $HOSTNAME_INPUT
  執行用戶     :  $USERNAME
  Tailscale    :  ${TAILSCALE_KEY:0:20}...
  Cloudflare   :  ${CF_TOKEN:0:20}...
  Telegram Bot :  ${TG_TOKEN:0:20}...
  Telegram ID  :  $TG_CHAT

安裝時間約 15–30 分鐘
安裝過程中請勿關閉視窗

確認開始安裝？" $H $W || die "已取消安裝"

# ── Installation ─────────────────────────────────────────────
clear
echo -e "${BOLD}${CYAN}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║         j13 Server Installer v1.0            ║"
echo "  ║         安裝進行中，請勿關閉視窗             ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${NC}"

STEPS=12
CURRENT=0
show_progress() {
  CURRENT=$((CURRENT + 1))
  PCT=$((CURRENT * 100 / STEPS))
  echo -e "\n${CYAN}[${CURRENT}/${STEPS}]${NC} ${BOLD}$1${NC}"
}

# 1. System update
show_progress "系統更新"
apt-get update -qq && apt-get upgrade -y -qq
apt-get install -y -qq curl wget git htop unzip python3-pip \
  ufw fail2ban unattended-upgrades software-properties-common \
  build-essential ca-certificates gnupg lsb-release
log "系統更新完成"

# 2. SSH hardening
show_progress "SSH 安全強化"
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak 2>/dev/null || true
cat > /etc/ssh/sshd_config.d/j13-hardened.conf << 'EOF'
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
X11Forwarding no
EOF
systemctl restart ssh
log "SSH 強化完成（密碼登入已關閉，僅允許金鑰）"

# 3. UFW
show_progress "防火牆設定 (UFW)"
ufw --force reset && ufw default deny incoming && ufw default allow outgoing
ufw allow ssh && ufw allow 9000/tcp && ufw allow 8888/tcp
ufw allow 80/tcp && ufw allow 443/tcp
ufw --force enable
log "UFW 防火牆啟用完成"

# 4. Fail2Ban
show_progress "Fail2Ban 入侵防護"
cat > /etc/fail2ban/jail.local << 'EOF'
[sshd]
enabled  = true
maxretry = 5
bantime  = 3600
findtime = 600
EOF
systemctl enable fail2ban && systemctl restart fail2ban
log "Fail2Ban 啟用完成"

# 5. Auto updates
show_progress "自動安全更新"
cat > /etc/apt/apt.conf.d/20auto-upgrades << 'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
systemctl enable unattended-upgrades
log "自動安全更新啟用完成"

# 6. NVIDIA + CUDA
show_progress "NVIDIA 驅動 + CUDA 12.1（需要時間）"
apt-get install -y -qq ubuntu-drivers-common
ubuntu-drivers autoinstall
wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
dpkg -i cuda-keyring_1.1-1_all.deb && rm cuda-keyring_1.1-1_all.deb
apt-get update -qq && apt-get install -y -qq cuda-12-1 libcudnn8
echo 'export PATH=/usr/local/cuda/bin:$PATH' >> /home/$USERNAME/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> /home/$USERNAME/.bashrc
log "CUDA 12.1 安裝完成（重啟後生效）"

# 7. Docker
show_progress "Docker + NVIDIA Container Toolkit"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
usermod -aG docker $USERNAME && systemctl enable docker
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
apt-get update -qq && apt-get install -y -qq nvidia-container-toolkit
nvidia-ctk runtime configure --runtime=docker && systemctl restart docker
log "Docker + GPU passthrough 安裝完成"

# 8. Portainer
show_progress "Portainer 容器管理介面"
mkdir -p /opt/portainer
cat > /opt/portainer/docker-compose.yml << 'EOF'
services:
  portainer:
    image: portainer/portainer-ce:latest
    container_name: portainer
    restart: always
    ports:
      - "127.0.0.1:9000:9000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - portainer_data:/data
volumes:
  portainer_data:
EOF
docker compose -f /opt/portainer/docker-compose.yml up -d
log "Portainer 啟動完成（:9000）"

# 9. Python ML + JupyterLab
show_progress "Python ML 環境 + JupyterLab（下載中）"
pip3 install -q jupyterlab torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cu121
pip3 install -q lightgbm pandas numpy scikit-learn \
  transformers peft accelerate bitsandbytes
JUPYTER_TOKEN=$(openssl rand -hex 24)
cat > /etc/systemd/system/jupyterlab.service << EOF
[Unit]
Description=JupyterLab
After=network.target
[Service]
User=$USERNAME
WorkingDirectory=/home/$USERNAME
ExecStart=/usr/local/bin/jupyter lab \
  --ip=127.0.0.1 --port=8888 --no-browser \
  --NotebookApp.token='$JUPYTER_TOKEN' \
  --NotebookApp.allow_origin='*'
Restart=on-failure
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable jupyterlab && systemctl start jupyterlab
log "JupyterLab 啟動完成（token 已儲存）"

# 10. Tailscale (Layer 1)
show_progress "保護層 1 — Tailscale VPN"
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --authkey="$TAILSCALE_KEY" --hostname="$HOSTNAME_INPUT" --advertise-tags=tag:server
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "pending-reboot")
log "Tailscale 連線完成：$TAILSCALE_IP"

# 11. Cloudflare Tunnel (Layer 2)
show_progress "保護層 2 — Cloudflare Tunnel"
docker run -d --name cloudflared --restart always \
  cloudflare/cloudflared:latest \
  tunnel --no-autoupdate run --token "$CF_TOKEN"
log "Cloudflare Tunnel 啟動完成"

# 12. Ollama + ops-agent
show_progress "Ollama + Qwen2.5-7B + ops-agent（下載最久）"
curl -fsSL https://ollama.ai/install.sh | sh
systemctl enable ollama && systemctl start ollama
sleep 5
ollama pull qwen2.5:7b
log "Ollama + Qwen2.5-7B 下載完成"

# ops-agent
mkdir -p /opt/ops-agent
cat > /opt/ops-agent/docker-compose.yml << EOF
services:
  ops-agent:
    image: python:3.12-slim
    container_name: ops-agent
    restart: always
    environment:
      - TELEGRAM_BOT_TOKEN=$TG_TOKEN
      - TELEGRAM_CHAT_ID=$TG_CHAT
      - OLLAMA_URL=http://host.docker.internal:11434
      - OPS_MODEL=qwen2.5:7b
      - CHECK_INTERVAL_MIN=5
      - GPU_TEMP_THRESHOLD=85
      - DISK_THRESHOLD_PCT=90
      - RAM_THRESHOLD_PCT=90
      - MAX_RESTART_ATTEMPTS=3
      - RESTART_WINDOW_MIN=30
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /opt/ops-agent/app:/app
      - ops_data:/app/data
    working_dir: /app
    command: >
      bash -c "pip install -q requests psutil schedule &&
               python -u agent.py"
    extra_hosts:
      - host.docker.internal:host-gateway
volumes:
  ops_data:
EOF

# Download ops-agent source
mkdir -p /opt/ops-agent/app
gh_raw() {
  curl -sfL "https://raw.githubusercontent.com/M116cj/j13-ops/main/ops-agent/$1" -o "/opt/ops-agent/app/$1"
}
gh_raw agent.py && gh_raw telegram.py && gh_raw ollama_client.py || \
  warn "ops-agent 源碼下載失敗，請手動執行：cd /opt/ops-agent && docker compose up -d"

if [[ -f /opt/ops-agent/app/agent.py ]]; then
  docker compose -f /opt/ops-agent/docker-compose.yml up -d
  log "ops-agent 啟動完成"
fi

# 13. Watchtower
docker run -d --name watchtower --restart always \
  -v /var/run/docker.sock:/var/run/docker.sock \
  containrrr/watchtower --schedule "0 0 4 * * *" --cleanup
log "Watchtower（自動更新容器）啟動完成"

# ── Save info ─────────────────────────────────────────────────
cat > /home/$USERNAME/.server-info << EOF
# j13 Server Info — $(date)
TAILSCALE_IP=$TAILSCALE_IP
HOSTNAME=$HOSTNAME_INPUT
PORTAINER=http://$HOSTNAME_INPUT:9000
JUPYTERLAB=http://$HOSTNAME_INPUT:8888
JUPYTER_TOKEN=$JUPYTER_TOKEN
EOF
chown $USERNAME:$USERNAME /home/$USERNAME/.server-info

# ── Screen 4: Done ───────────────────────────────────────────
clear
echo -e "${GREEN}${BOLD}"
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║                                                  ║"
echo "  ║         ✓  安裝完成！                            ║"
echo "  ║                                                  ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "
${BOLD}連線資訊${NC}
  Tailscale IP   : ${YELLOW}$TAILSCALE_IP${NC}
  Portainer      : ${YELLOW}http://$HOSTNAME_INPUT:9000${NC}
  JupyterLab     : ${YELLOW}http://$HOSTNAME_INPUT:8888${NC}
  Jupyter Token  : ${YELLOW}$JUPYTER_TOKEN${NC}

${BOLD}已安裝的服務${NC}
  $(docker ps --format '  ✓ {{.Names}}' 2>/dev/null)

${BOLD}下一步${NC}
  1. ${YELLOW}sudo reboot${NC}  — 重啟以啟用 NVIDIA 驅動
  2. 重啟後驗證 GPU：${YELLOW}nvidia-smi${NC}
  3. Mac 安裝 Tailscale App 並登入相同帳號
  4. 從 Mac SSH：${YELLOW}ssh $USERNAME@$HOSTNAME_INPUT${NC}

${BOLD}注意${NC}
  連線資訊已儲存至：${YELLOW}~/.server-info${NC}
"

whiptail --title "安裝完成！" --yesno \
"所有服務安裝完成！

Tailscale IP  : $TAILSCALE_IP
Portainer     : http://$HOSTNAME_INPUT:9000
JupyterLab    : http://$HOSTNAME_INPUT:8888

需要立即重啟以啟用 NVIDIA 驅動。

現在重啟嗎？" 16 $W && reboot || echo -e "\n${YELLOW}請記得手動執行：sudo reboot${NC}\n"
