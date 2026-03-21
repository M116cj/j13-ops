#!/usr/bin/env bash
# gpu-coordinator.sh — VRAM guard for GPU training workloads
#
# Usage: ./gpu-coordinator.sh <training_command...>
#
# Decision 2026-03-21: dynamic model unload chosen over systemd-timer and
# nvidia-cuda-mps for solo-operator simplicity. No daemon, no Kubernetes,
# no extra infra. Pure signal-based coordination.
#
# Current state: zangetsu LightGBM training is CPU-only (no device_type=gpu).
# No VRAM conflict exists today. This script is a proactive guard for when
# GPU training is introduced (CatBoost, GPU-LightGBM, PyTorch fine-tune).
#
# How it works (when GPU training is needed):
#   1. Check free VRAM. If >= REQUIRED_VRAM_MB, train immediately.
#   2. If not, SIGTERM llama-server (runs as j13 — no sudo needed).
#   3. Poll until VRAM is free. Timeout = 120s.
#   4. Run training command.
#   5. systemd Restart=always brings Qwen back (RestartSec=15).
#
# Env vars:
#   REQUIRED_VRAM_MB   — minimum free VRAM before training (default: 3000)
#   GPU_COORD_DRY_RUN  — set to 1 to simulate without killing anything

set -euo pipefail

REQUIRED_VRAM_MB=${REQUIRED_VRAM_MB:-3000}
DRY_RUN=${GPU_COORD_DRY_RUN:-0}
POLL_INTERVAL=3
TIMEOUT=120

log() { echo "[gpu-coordinator] $(date -u +%H:%M:%S) $*"; }

free_vram_mb() {
    nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null \
        | awk '{print $1}'
}

llama_pid() {
    pgrep -x llama-server 2>/dev/null || true
}

yield_gpu() {
    local pid
    pid=$(llama_pid)
    if [[ -z "$pid" ]]; then
        log "llama-server not running, GPU should be free"
        return 0
    fi
    log "Sending SIGTERM to llama-server (pid=$pid)"
    if [[ "$DRY_RUN" == "1" ]]; then
        log "DRY_RUN: would kill pid=$pid"
    else
        kill -SIGTERM "$pid" 2>/dev/null || true
    fi

    local elapsed=0
    while true; do
        local free
        free=$(free_vram_mb)
        log "VRAM free: ${free} MiB (need ${REQUIRED_VRAM_MB} MiB) [${elapsed}s]"
        if (( free >= REQUIRED_VRAM_MB )); then
            log "VRAM sufficient — proceeding with training"
            return 0
        fi
        if (( elapsed >= TIMEOUT )); then
            log "ERROR: Timeout waiting for VRAM. Aborting."
            exit 1
        fi
        sleep "$POLL_INTERVAL"
        (( elapsed += POLL_INTERVAL ))
    done
}

main() {
    if [[ $# -eq 0 ]]; then
        echo "Usage: $0 <command> [args...]"
        exit 1
    fi

    local free
    free=$(free_vram_mb)
    log "Current free VRAM: ${free} MiB, required: ${REQUIRED_VRAM_MB} MiB"

    if (( free < REQUIRED_VRAM_MB )); then
        log "Insufficient VRAM — yielding GPU from llama-server"
        yield_gpu
    else
        log "VRAM sufficient — no yield needed"
    fi

    log "Running: $*"
    "$@"
    local exit_code=$?
    log "Training complete (exit=$exit_code). llama-server restarts via systemd."
    return $exit_code
}

main "$@"
