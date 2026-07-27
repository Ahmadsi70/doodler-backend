# ── RunPod Serverless — Story Animation Pipeline ─────────────────────
# Minimal image: CUDA + AnimateDiff + handler

FROM runpod/base:0.4.0-cuda12.1.0

ENV PYTHONUNBUFFERED=1
ENV MOCK_MODE=0

WORKDIR /story

# ── System deps ──────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl git \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ─────────────────────────────────────────────
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# ── Animation pipeline code (exclude frontend/remotion) ─────────────
COPY libraries/ libraries/
COPY animatediff/ animatediff/
COPY configs/ configs/
COPY llm/ llm/
COPY backend/ backend/
COPY runpod_handler.py .

# ── Models will be downloaded on first run ──────────────────────────
RUN mkdir -p /story/models

# ── RunPod entrypoint ───────────────────────────────────────────────
CMD ["python3", "-u", "-m", "runpod", "--handler", "runpod_handler:runpod_handler"]
