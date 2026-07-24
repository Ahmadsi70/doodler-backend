import os
import requests
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
RUNPOD_ENDPOINT_ID = os.environ.get("RUNPOD_ENDPOINT_ID")
RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY")

url = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/run"
headers = {"Content-Type": "application/json", "Authorization": f"Bearer {RUNPOD_API_KEY}"}

def run_test(test_name, sfx_prompt):
    print(f"\n--- Starting {test_name} ---")
    payload = {
        "input": {
            "spec": {
                "brief": {"user_prompt": "Test", "num_parts_budget": 5},
                "sketch": {"creature_name": "Dog", "lore": "Dog lore", "parts": []},
                "timeline": {
                    "scenes": [
                        {"start_time": 0.0, "end_time": 5.0, "motion_type": "jump", "sfx_prompt": sfx_prompt}
                    ]
                },
                "style_id": "test"
            }
        }
    }

    try:
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        job_id = resp.json()["id"]
        print(f"Request sent. Job ID: {job_id}")

        while True:
            time.sleep(3)
            poll_resp = requests.get(f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/status/{job_id}", headers=headers)
            status_data = poll_resp.json()
            status = status_data.get("status")
            
            if status == "COMPLETED":
                output = status_data.get("output", {})
                if output.get("status") == "success":
                    print(f"SUCCESS: {test_name} completed without errors!")
                else:
                    print(f"ERROR: {test_name} failed in output: {output}")
                break
            elif status == "FAILED":
                print(f"FAILED: {test_name} stopped with an error!")
                print(f"Error text: {status_data.get('error')[:200]}...")
                break
            elif status in ["IN_QUEUE", "IN_PROGRESS"]:
                pass
            else:
                print(f"Unknown status: {status}")
                break
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    print("Testing RunPod server to isolate CUDA error...")
    print("Test 1: NO AUDIO (AudioLDM bypassed)")
    run_test("No Audio Test", "")
    
    print("\nTest 2: WITH AUDIO (AudioLDM active)")
    run_test("With Audio Test", "a loud bark")
