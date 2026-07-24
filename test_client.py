import requests
import json
import base64
import time

url = "https://p7q35voyphx937-8000.proxy.runpod.net/generate"
status_url = "https://p7q35voyphx937-8000.proxy.runpod.net/status/{}"

payload = {
    "spec": {
        "sketch": {
            "parts": [
                {"prompt": "A cute magical blue fox with big ears and a fluffy tail"}
            ]
        },
        "timeline": {
            "scenes": [
                {
                    "motion_type": "walk",
                    "sfx_prompt": "footsteps on grass, sunny day nature sounds"
                },
                {
                    "motion_type": "jump",
                    "sfx_prompt": "cartoon boing spring sound"
                },
                {
                    "motion_type": "dance",
                    "sfx_prompt": "upbeat electronic dance music, cheerful"
                },
                {
                    "motion_type": "wave",
                    "sfx_prompt": "happy cheerful magical chime sound"
                }
            ]
        }
    }
}

print("Sending request to Doodler Backend...")
start_time = time.time()

try:
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("status") == "success":
            job_id = data.get("job_id")
            print("Success! Backend queued the job. Job ID:", job_id)
            
            while True:
                time.sleep(5)
                status_res = requests.get(status_url.format(job_id))
                if status_res.status_code == 200:
                    status_data = status_res.json()
                    status = status_data.get("status")
                    print(f"Status: {status} (Elapsed: {time.time() - start_time:.1f}s)")
                    
                    if status == "completed":
                        video_b64 = status_data.get("video_base64")
                        if video_b64:
                            with open("output_test.mp4", "wb") as f:
                                f.write(base64.b64decode(video_b64))
                            print("Video saved to output_test.mp4")
                        break
                    elif status == "failed":
                        print("Backend returned an error:", status_data.get("error"))
                        break
                else:
                    print("Status endpoint error:", status_res.status_code, status_res.text)
        else:
            print("Backend returned an error:", data)
    else:
        print(f"HTTP Error {response.status_code}:", response.text)
except Exception as e:
    print("Failed to connect or send request:", e)
