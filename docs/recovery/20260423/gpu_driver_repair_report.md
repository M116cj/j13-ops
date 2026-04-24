# GPU Driver Repair Report

**Order**: `/home/j13/claude-inbox/0-1` Phase C action 1
**Produced**: 2026-04-23T01:25Z
**Lead**: Claude
**Status**: **DIAGNOSED — repair NOT EXECUTED (requires j13 presence per §4)**
**Scope**: parallel infra work. Not the current root bottleneck per 0-1.

---

## 1. Observable symptom (VERIFIED)

```
$ nvidia-smi
NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver.
Make sure that the latest NVIDIA driver is installed and running.
```

## 2. Root cause (VERIFIED)

The **NVIDIA kernel-mode driver is not loaded**. CUDA user-space runtime libraries are present; kernel side is empty.

### 2.1 Evidence

| Probe | Output | Interpretation |
|---|---|---|
| `lsmod \| grep nvidia` | **empty** | nvidia.ko not loaded into running kernel |
| `lsmod \| grep nouveau` | **empty** | neither nouveau (open) loaded |
| `lspci \| grep -i nvidia` | `01:00.0 GA102 [GeForce RTX 3080 12GB] (rev a1)` + audio codec | hardware present and enumerated |
| `ls /proc/driver/nvidia` | `No such file or directory` | no `/proc` entry — driver never initialized |
| `dpkg -l \| grep nvidia` | only CUDA *user-space* libs (`libcublas`, `libcudart`, `libcupti`, `libcurand`, `libcusolver`, `libcusparse`, `libaccinj64`, `libcufft`) — **NO kernel driver package** | `nvidia-driver-*` / `nvidia-dkms-*` is not installed |
| `ls /var/lib/dkms/nvidia` | not present | DKMS has no nvidia module registered |
| `ls /usr/lib/modules/$(uname -r)/kernel/drivers/video/` | `backlight  fbdev  vgastate.ko.zst` | no nvidia.ko.zst for running kernel |
| `systemctl is-active nvidia-persistenced` | `inactive` (dead) | persistence daemon exists but can't run without driver |
| `uname -r` | `6.8.0-110-generic` (kernel 2026-03-19) | running kernel is current Ubuntu generic — needs matching driver |

### 2.2 Interpretation

**Classification**: VERIFIED.

This is *not* a driver-crash or runtime-failure. The driver is **not installed at all on the currently-running kernel**. Given `dpkg -l` shows NO `nvidia-driver-*` entry (not even stale), this is: **kernel driver was never installed** — server was set up with CUDA user-space libs (for PyTorch/LightGBM at `libcublas`/`libcudart` linker level) via a meta-package that did not include the kernel driver.

## 3. Impact assessment (VERIFIED / PROBABLE)

| Consumer | Impact | Evidence |
|---|---|---|
| Zangetsu arena GP loop | **None today** | arena CPU-only; engine.jsonl shows no CUDA references |
| Zangetsu LGBM (`lightgbm 4.6.0` venv) | degraded but functional | CPU backend works; GPU would be faster |
| **Katen Week 2 LGBM training** | **HIGH impact — blocking** | AKASHA commit `4c8c23b feat(katen): Week 2 — LightGBM training scaffold (3-horizon direction predictor)` — GPU acceleration planned |
| **Calcifer (Gemma4 E4B via Ollama)** | **blocking for LLM features** | Gemma on CPU-only Ollama is ~20× slower and may time out tool calls |
| Markl (Gemma3 12B, Mac-side Ollama) | **no Alaya impact** | Markl is on Mac |
| Ascension Phase 3+ modular engine | future | TBD |

**Priority per Charter + 0-1 Phase C**: fix in parallel; NOT a recovery blocker, IS a Katen/Calcifer blocker.

## 4. Repair protocol (NOT EXECUTED — documented for j13 to authorize)

### 4.1 Pre-flight checks (read-only — safe to run anytime)

```bash
ssh j13@100.123.49.102
# 1. No GPU-using process to interrupt
ps -ef | grep -iE 'python.*cuda|ollama' | grep -v grep

# 2. Kernel headers for 6.8.0-110
dpkg -l | grep -E "linux-headers-$(uname -r)" | head

# 3. Disk space for driver install (~500 MB) — currently 798 GB free
df -h /

# 4. Ubuntu release
lsb_release -a
```

### 4.2 Install (requires sudo — j13 present)

**Option A — Ubuntu `ubuntu-drivers`** (recommended, automatic kernel matching):

```bash
sudo apt update
sudo ubuntu-drivers devices            # lists recommended driver
sudo ubuntu-drivers install            # installs "recommended"
# OR pin a specific version:
# sudo apt install nvidia-driver-570 nvidia-dkms-570
```

**Option B — NVIDIA `.run` installer**: NOT recommended (fights Ubuntu packaging).

### 4.3 Load + verify

```bash
sudo modprobe nvidia
lsmod | grep nvidia                    # expect 6+ nvidia_* modules
nvidia-smi                             # expect GPU reported with temp/mem
sudo systemctl enable --now nvidia-persistenced
systemctl is-active nvidia-persistenced   # expect "active"
```

### 4.4 Reboot decision

- If DKMS rebuilt cleanly and `nvidia-smi` works without reboot → NO REBOOT.
- If DKMS fails kernel-header mismatch OR `modprobe nvidia` fails → reboot required.

**If reboot required — confirm j13 present** (§4). Will interrupt:
- console-api (:9900) — stateless, recovers on boot
- dashboard-api (:9901) — stateless, recovers
- calcifer-supervisor — stateful in-memory lost, resumes from checkpoints
- calcifer-miniapp — stateless, recovers
- d-mail-miniapp — Redis-persisted job state (TTL 24h), recovers
- Docker containers (`akasha-*`, `deploy-postgres-1`) — `restart: unless-stopped`, recover
- AKASHA — Postgres-backed, recovers

Downtime: 3–5 minutes.

### 4.5 Post-install smoke

```bash
# LightGBM GPU test
python3 -c "import lightgbm as lgb; import numpy as np; d = lgb.Dataset(np.random.rand(100,5), label=np.random.rand(100)); lgb.train({'device_type':'cuda','verbose':-1}, d, num_boost_round=5); print('ok')"

# Ollama Gemma test (fast iff GPU active)
curl -s http://localhost:11434/api/tags | head
time curl -s http://localhost:11434/api/generate -d '{"model":"gemma4:e4b","prompt":"ok","stream":false}' | head -c 200
```

## 5. Rollback

If install breaks the system:

```bash
sudo apt purge 'nvidia-*'
sudo apt autoremove
sudo update-initramfs -u
sudo reboot    # back to pre-install state
```

CUDA user-space libs remain (the original state).

## 6. Q1 adversarial

| Dim | Assertion | Verdict |
|---|---|---|
| Input boundary | return code + lsmod + dpkg triangulate root cause | PASS |
| Silent failure | Impact matrix §3 distinguishes per-consumer effect | PASS |
| External dep | All probes local read-only | PASS |
| Concurrency | §4.1 checks for GPU-consuming processes | PASS |
| Scope creep | Limited to GPU driver; no kernel/firmware/BIOS | PASS |

## 7. Recommendation

**Authorize Option A (`ubuntu-drivers install`) when j13 is present.** Expected 10-min window if no reboot; 15 if reboot. Can run opportunistically parallel to any j13 in-room session. Do NOT execute during Zangetsu arena restart window.
