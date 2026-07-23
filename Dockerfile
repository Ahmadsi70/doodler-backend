# Story Studio — Light path (FFmpeg + Python). Pro/Remotion needs a Node stage.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt pyproject.toml README.md ./
COPY agents agents
COPY tools tools
COPY runtime runtime
COPY libraries libraries
COPY prompts prompts
COPY llm llm
COPY scripts scripts
COPY scene_ir.py story_cli.py __main__.py app.py ./

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "pytest>=8.0.0"

ENV STORY_USE_LLM=0 \
    ANIMATION_DETERMINISTIC_SLIDES=1 \
    QUALITY_GATE_STRICT=0 \
    PYTHONUNBUFFERED=1

CMD ["python", "__main__.py", "ready"]
