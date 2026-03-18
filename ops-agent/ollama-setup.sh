#!/bin/bash
# Run on the server AFTER main server-setup.sh
# Installs Ollama and pulls qwen2.5:7b

set -euo pipefail

echo "[ollama-setup] Installing Ollama..."
curl -fsSL https://ollama.ai/install.sh | sh

echo "[ollama-setup] Enabling and starting ollama service..."
systemctl enable ollama
systemctl start ollama

echo "[ollama-setup] Waiting for Ollama to be ready..."
sleep 5

echo "[ollama-setup] Pulling model qwen2.5:7b..."
ollama pull qwen2.5:7b

echo "[ollama-setup] Done. Model list:"
ollama list

echo "Ollama ready. Model: qwen2.5:7b"
