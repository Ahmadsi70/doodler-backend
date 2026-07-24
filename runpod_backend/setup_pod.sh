#!/bin/bash
echo "Setting up Doodler Backend on RunPod Pod..."

# Update apt and install xvfb
apt-get update
apt-get install -y ffmpeg git wget libgl1-mesa-glx libglib2.0-0 xvfb

# Create workspace and clone AnimatedDrawings if it doesn't exist
cd /workspace
if [ ! -d "AnimatedDrawings" ]; then
    git clone https://github.com/facebookresearch/AnimatedDrawings.git
fi

# Download server code
wget -O server.py https://raw.githubusercontent.com/ahmadsi70/doodler-backend/main/runpod_backend/server.py

# Install python dependencies
pip install --ignore-installed cryptography runpod diffusers transformers accelerate moviepy==1.0.3 opencv-python scipy soundfile numpy pillow rembg onnxruntime-gpu pyyaml matplotlib imageio shapely fastapi uvicorn pydantic

echo "Setup complete! Starting the server..."
# Run the server
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
