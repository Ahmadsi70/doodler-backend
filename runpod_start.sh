#!/usr/bin/env bash
set -euo pipefail

# ── RunPod Entrypoint ──────────────────────────────────────────────
# Starts backend (FastAPI) + frontend (Next.js) via supervisord.
# Exports the session data directory for persistence.

echo "============================================"
echo "  Story Studio — RunPod"
echo "============================================"

# Ensure session data dir
mkdir -p /app/.story/sessions

# Print versions
echo "Python: $(python3.11 --version)"
echo "Node:   $(node --version)"
echo "NPM:    $(npm --version)"

# Check GPU
if command -v nvidia-smi &> /dev/null; then
    echo "GPU:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo "  nvidia-smi unavailable"
fi

# Print API key status
if [ -n "${OPENAI_API_KEY:-}" ]; then
    echo "OpenAI:   configured (${#OPENAI_API_KEY} chars)"
elif [ -n "${DEEPSEEK_API_KEY:-}" ]; then
    echo "DeepSeek: configured"
else
    echo "⚠ No LLM API key set! Agents will not use LLM."
fi

# Start supervisord
echo "Starting services..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/studio.conf
