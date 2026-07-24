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
# Clean up pre-installed packages that might cause uninstall errors or version conflicts
rm -rf /usr/local/lib/python3.*/dist-packages/cryptography*
rm -rf /usr/lib/python3/dist-packages/cryptography*
rm -rf /usr/local/lib/python3.*/dist-packages/tokenizers*
rm -rf /usr/lib/python3/dist-packages/tokenizers*
rm -rf /usr/local/lib/python3.*/dist-packages/transformers*
rm -rf /usr/local/lib/python3.*/dist-packages/diffusers*
rm -rf /usr/local/lib/python3.*/dist-packages/huggingface_hub*

# Install python dependencies safely
pip install cryptography runpod diffusers==0.27.2 transformers==4.38.2 accelerate==0.28.0 "huggingface-hub<=0.23.0" moviepy==1.0.3 opencv-python scipy soundfile numpy pillow rembg onnxruntime-gpu pyyaml matplotlib imageio shapely fastapi uvicorn pydantic

echo "Setup complete! Starting the server..."
# Kill any existing server processes to avoid 'Address already in use' error
pkill -f "server.py" || true
pkill -f "uvicorn" || true
sleep 1

# Run the server
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
