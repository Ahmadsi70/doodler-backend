import os
import requests
import time
import base64
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

RUNPOD_ENDPOINT_ID = os.environ.get("RUNPOD_ENDPOINT_ID")
RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY")

payload = {
  "input": {
    "spec": {
      "brief": {"user_prompt": "A cute jumping dog", "num_parts_budget": 5},
      "sketch": {
        "creature_name": "Bouncy Paws",
        "lore": "A lively little dog who dreams of flying.",
        "parts": [
          {"id": "part_0", "part_type": "body", "order": 0, "prompt": "a stretched, curved dog body"},
          {"id": "part_1", "part_type": "head", "order": 1, "prompt": "a cute, smiling dog head"}
        ]
      },
      "timeline": {
        "scenes": [
          {"start_time": 0.0, "end_time": 10.0, "motion_type": "jump", "sfx_prompt": ""}
        ]
      },
      "style_id": "symmetrical_pastel_cinema"
    }
  }
}

print(f"Submitting to RunPod {RUNPOD_ENDPOINT_ID}...")
url = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/run"
headers = {"Content-Type": "application/json", "Authorization": f"Bearer {RUNPOD_API_KEY}"}

resp = requests.post(url, headers=headers, json=payload)
resp.raise_for_status()
job_id = resp.json()["id"]
print(f"Job ID: {job_id}. Waiting for completion...")

completed = False
while not completed:
    time.sleep(5)
    poll_resp = requests.get(f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/status/{job_id}", headers=headers)
    status_data = poll_resp.json()
    status = status_data.get("status")
    print(f"Status: {status}")
    
    if status == "COMPLETED":
        output = status_data.get("output", {})
        if output.get("status") == "success":
            video_b64 = output.get("video_base64")
            video_bytes = base64.b64decode(video_b64)
            video_path = Path("out/final_test_video.mp4")
            video_path.parent.mkdir(parents=True, exist_ok=True)
            with open(video_path, "wb") as f:
                f.write(video_bytes)
            print(f"SUCCESS: Video saved to {video_path.absolute()}")
        else:
            print("ERROR IN PIPELINE:", output)
        completed = True
    elif status == "FAILED":
        print("RUNPOD FAILED:", status_data)
        completed = True
