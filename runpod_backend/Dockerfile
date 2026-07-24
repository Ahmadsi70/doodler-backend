# Base image provided by RunPod with PyTorch and CUDA pre-installed
FROM runpod/pytorch:2.2.1-py3.10-cuda12.1.1-devel-ubuntu22.04

# Set working directory
WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    wget \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Clone AnimatedDrawings
RUN git clone https://github.com/facebookresearch/AnimatedDrawings.git /workspace/AnimatedDrawings

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy handler code
COPY handler.py .

# Start the RunPod serverless handler
CMD ["python", "-u", "handler.py"]
