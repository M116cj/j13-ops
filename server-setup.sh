#!/bin/bash
# ============================================================
# j13 Server Bootstrap — Ubuntu 22.04
# Hardware: RTX 3080 12GB / i7-12700K / 32GB RAM
# Installs: Tailscale + SSH hardening + CUDA 12.1 +
#           Docker + Portainer + JupyterLab
# Run as: sudo bash server-setup.sh <TAILSCALE_AUTH_KEY>
# ============================================================
set -euo pipefail
TAILSCALE_AUTH_KEY="${1:-}"
USERNAME="${SUDO_USER:-$(logname 2>/dev/null || echo ubuntu)}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
die()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }

[[ $EUID -ne 0 ]] && die "Run as root: sudo bash $0 <tailscale-auth-key>"
[[ -z "$TAILSCALE_AUTH_KEY" ]] && die "Usage: sudo bash $0 <tailscale-auth-key>"

log "=== j13 Server Bootstrap Starting ==="
log "User: $USERNAME | $(nproc) cores | $(free -g | awk '/Mem:/{print $2}')GB RAM"

# ── 1. System update ─────────────────────────────────────────
log "System update..."
apt-get update -qq && apt-get upgrade -y -qq
apt-get install -y -qq curl wget git htop unzip python3-pip \
  ufw fail2ban unattended-upgrades software-properties-common \
  build-essential ca-certificates gnupg lsb-release

# ── 2. SSH hardening ─────────────────────────────────────────
log "SSH hardening..."
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak
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
log "SSH: password auth disabled, key-only"

# ── 3. UFW firewall ──────────────────────────────────────────
log "Firewall (UFW)..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 9000/tcp comment "Portainer"
ufw allow 8888/tcp comment "JupyterLab"
ufw allow 80/tcp comment "Traefik HTTP"
ufw allow 443/tcp comment "Traefik HTTPS"
ufw --force enable

# ── 4. Fail2Ban ──────────────────────────────────────────────
log "Fail2Ban..."
cat > /etc/fail2ban/jail.local << 'EOF'
[sshd]
enabled  = true
maxretry = 5
bantime  = 3600
findtime = 600
EOF
systemctl enable fail2ban && systemctl restart fail2ban

# ── 5. Auto security updates ─────────────────────────────────
cat > /etc/apt/apt.conf.d/20auto-upgrades << 'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF

# ── 6. NVIDIA drivers + CUDA 12.1 ────────────────────────────
log "NVIDIA drivers..."
apt-get install -y -qq ubuntu-drivers-common
ubuntu-drivers autoinstall
log "CUDA 12.1 keyring..."
wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
dpkg -i cuda-keyring_1.1-1_all.deb && rm cuda-keyring_1.1-1_all.deb
apt-get update -qq
apt-get install -y -qq cuda-12-1 libcudnn8
echo 'export PATH=/usr/local/cuda/bin:$PATH' >> /home/$USERNAME/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> /home/$USERNAME/.bashrc
log "CUDA 12.1 installed (reboot required)"

# ── 7. Docker ────────────────────────────────────────────────
log "Docker..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
usermod -aG docker $USERNAME
systemctl enable docker

# NVIDIA Container Toolkit
log "NVIDIA Container Toolkit..."
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
apt-get update -qq
apt-get install -y -qq nvidia-container-toolkit
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker
log "GPU passthrough to Docker enabled"

# ── 8. Portainer ─────────────────────────────────────────────
log "Portainer (Web UI)..."
mkdir -p /opt/portainer
cat > /opt/portainer/docker-compose.yml << 'EOF'
services:
  portainer:
    image: portainer/portainer-ce:latest
    container_name: portainer
    restart: always
    ports:
      - "9000:9000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - portainer_data:/data
volumes:
  portainer_data:
EOF
docker compose -f /opt/portainer/docker-compose.yml up -d
log "Portainer running on :9000"

# ── 9. Python ML stack ───────────────────────────────────────
log "Python ML stack (PyTorch + LightGBM)..."
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
ExecStart=/usr/local/bin/jupyter lab --ip=0.0.0.0 --port=8888 \
  --no-browser --NotebookApp.token='$JUPYTER_TOKEN' \
  --NotebookApp.allow_origin='*'
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable jupyterlab
systemctl start jupyterlab

# ── 10. Tailscale ────────────────────────────────────────────
log "Tailscale..."
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --authkey="$TAILSCALE_AUTH_KEY" --hostname="j13-server"
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "pending-reboot")

# ── 11. Watchtower ───────────────────────────────────────────
log "Watchtower (auto-update containers)..."
docker run -d \
  --name watchtower \
  --restart always \
  -v /var/run/docker.sock:/var/run/docker.sock \
  containrrr/watchtower \
  --schedule "0 0 4 * * *" \
  --cleanup

# ── 12. Save connection info ─────────────────────────────────
cat > /home/$USERNAME/.server-info << EOF
TAILSCALE_IP=$TAILSCALE_IP
PORTAINER=http://$TAILSCALE_IP:9000
JUPYTERLAB=http://$TAILSCALE_IP:8888
JUPYTER_TOKEN=$JUPYTER_TOKEN
EOF
chown $USERNAME:$USERNAME /home/$USERNAME/.server-info

echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   j13 Server Bootstrap Complete!     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
echo -e "Tailscale IP : ${YELLOW}$TAILSCALE_IP${NC}"
echo -e "Portainer    : ${YELLOW}http://$TAILSCALE_IP:9000${NC}"
echo -e "JupyterLab   : ${YELLOW}http://$TAILSCALE_IP:8888?token=$JUPYTER_TOKEN${NC}"
echo ""
warn "⚠️  REBOOT NOW:  sudo reboot"
warn "⚠️  After reboot verify:  nvidia-smi"
warn "⚠️  Info saved to ~/.server-info"
warn "⚠️  First: copy your SSH public key BEFORE disabling password auth"
warn "   From Mac: ssh-copy-id $USERNAME@<current-local-ip>"
