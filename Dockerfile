# ── Stage 1: Build frontend ──────────────────────────────────────────
FROM node:20-bookworm AS frontend-builder

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build

# ── Stage 2: Main image ──────────────────────────────────────────────
FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# ── System deps ──────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    curl ca-certificates gnupg git \
    ffmpeg supervisor xvfb \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libegl1 libgles2 mesa-utils \
    && rm -rf /var/lib/apt/lists/*

# ── Python 3.11 via deadsnakes ──────────────────────────────────────
RUN add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.11 python3.11-dev python3.11-venv \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://bootstrap.pypa.io/get-pip.py | python3.11 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# ── Google Chrome (for Remotion) ─────────────────────────────────────
RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | \
    gpg --dearmor -o /usr/share/keyrings/google-chrome-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
        > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/apt/sources.list.d/google-chrome.list

# ── Node.js 20 ───────────────────────────────────────────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# ── Application ──────────────────────────────────────────────────────
WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Audio catalog (small - bundled in image)
COPY libraries/ libraries/

# Remotion project
COPY remotion/ remotion/
RUN cd remotion && npm ci && cd ..

# Pre-built frontend
COPY --from=frontend-builder /app/.next frontend/.next
COPY --from=frontend-builder /app/package.json frontend/
COPY --from=frontend-builder /app/node_modules frontend/node_modules/
COPY --from=frontend-builder /app/public frontend/public/
COPY --from=frontend-builder /app/next.config.js frontend/ 2>/dev/null || true
COPY --from=frontend-builder /app/tsconfig.json frontend/ 2>/dev/null || true

# Backend + agents
COPY backend/ backend/
COPY chat/ chat/
COPY agents/ agents/
COPY tools/ tools/
COPY llm/ llm/
COPY tests/ tests/
COPY start_server.py .

# ── Supervisor config ────────────────────────────────────────────────
RUN mkdir -p /var/log/supervisor

COPY runpod_supervisord.conf /etc/supervisor/conf.d/studio.conf

# ── Entrypoint ──────────────────────────────────────────────────────
COPY runpod_start.sh .
RUN chmod +x runpod_start.sh

EXPOSE 8000 3000

CMD ["./runpod_start.sh"]
