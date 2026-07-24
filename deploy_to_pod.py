import os
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

def main():
    print("🚀 Preparing to send code to RunPod...")
    
    # Load .env
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)
    
    pod_id = os.environ.get("RUNPOD_ENDPOINT_ID")
    if not pod_id:
        print("❌ Error: RUNPOD_ENDPOINT_ID is not set in .env")
        return
        
    print(f"📡 Target Pod ID: {pod_id}")
    
    # Read server.py
    server_py_path = Path(__file__).parent / "runpod_backend" / "server.py"
    if not server_py_path.exists():
        print(f"❌ Error: Cannot find {server_py_path}")
        return
        
    with open(server_py_path, "r", encoding="utf-8") as f:
        code_content = f.read()
        
    # Send to RunPod Proxy
    url = f"https://{pod_id}-8000.proxy.runpod.net/update_code"
    
    print(f"📤 Uploading server.py ({len(code_content)} bytes) to {url} ...")
    try:
        resp = requests.post(url, json={"code": code_content}, timeout=10)
        resp.raise_for_status()
        
        result = resp.json()
        print("✅ SUCCESS!")
        print(f"Server response: {result.get('message', 'Updated.')}")
        print("The server will automatically restart and apply the new code in 1-2 seconds.")
    except Exception as e:
        print(f"❌ Failed to update code: {e}")
        print("Make sure the Pod is running and the FastAPI server is active on port 8000.")

if __name__ == "__main__":
    main()
