import os
import sys
import json
import time
import base64
import requests
import logging
from pathlib import Path
from dotenv import load_dotenv

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# Load Env
_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / ".env")

# Ensure imports work
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agents.studio_graph import process_chat_graph
from doodler_ir import DoodlerStudioSpec, SketchSequence, TimelineSequence, SketchBrief

RUNPOD_ENDPOINT_ID = "8j9wve4oi0mln9"
import os
RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY", "")

def run_e2e_test():
    test_story = "یک سگ بامزه که راه میره و بعد میپره بالا و خوشحالی میکنه"
    logger.info(f"=== E2E TEST STARTED ===")
    logger.info(f"Test Story: {test_story}")
    
    # ---------------------------------------------------------
    # PHASE 1: LangGraph Agent (Story to Data)
    # ---------------------------------------------------------
    logger.info("PHASE 1: Calling LangGraph (process_chat_graph)...")
    messages = [{"role": "user", "content": test_story}]
    try:
        state_out = process_chat_graph(messages, target_duration=10)
        sketch_draft = state_out.get("sketch_draft", {})
        timeline_draft = state_out.get("timeline_draft", {})
        
        logger.info(f"LangGraph Success! Sketch draft parts: {len(sketch_draft.get('parts', []))}")
        logger.info(f"LangGraph Success! Timeline scenes: {len(timeline_draft.get('scenes', []))}")
    except Exception as e:
        logger.error(f"GAP 1 (LangGraph Error): {str(e)}")
        sys.exit(1)

    # ---------------------------------------------------------
    # PHASE 2: Pydantic Validation & Spec Creation
    # ---------------------------------------------------------
    logger.info("PHASE 2: Validating with Pydantic (DoodlerStudioSpec)...")
    try:
        brief = SketchBrief(user_prompt=test_story)
        sketch = SketchSequence(**sketch_draft) if sketch_draft else SketchSequence(creature_name="TestDog", lore=test_story, parts=[])
        timeline = TimelineSequence(**timeline_draft) if timeline_draft else TimelineSequence(scenes=[])
        
        spec = DoodlerStudioSpec(brief=brief, sketch=sketch, timeline=timeline)
        spec.style_id = "symmetrical_pastel_cinema"  # Default style
        
        payload_json = spec.model_dump_json()
        logger.info("Pydantic Validation Success! Spec is ready.")
        # logger.debug(f"Payload: {payload_json}")
    except Exception as e:
        logger.error(f"GAP 2 (Pydantic Error): {str(e)}")
        sys.exit(1)

    # ---------------------------------------------------------
    # PHASE 3: RunPod Serverless Submission
    # ---------------------------------------------------------
    logger.info("PHASE 3: Submitting to RunPod API...")
    url = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/run"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {RUNPOD_API_KEY}"
    }
    
    payload = {
        "input": {
            "spec": json.loads(payload_json)
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result_json = response.json()
        job_id = result_json.get("id")
        
        if not job_id:
            logger.error(f"GAP 3 (RunPod Submission Error): No job ID returned. Response: {result_json}")
            sys.exit(1)
            
        logger.info(f"RunPod Submission Success! Job ID: {job_id}")
    except Exception as e:
        logger.error(f"GAP 3 (RunPod Network Error): {str(e)}")
        if 'response' in locals() and hasattr(response, 'text'):
            logger.error(f"Response body: {response.text}")
        sys.exit(1)

    # ---------------------------------------------------------
    # PHASE 4: Polling RunPod
    # ---------------------------------------------------------
    logger.info("PHASE 4: Polling for results...")
    completed = False
    start_time = time.time()
    
    out_dir = _ROOT / "out" / "e2e_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    while not completed:
        time.sleep(5)
        poll_url = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/status/{job_id}"
        
        try:
            poll_resp = requests.get(poll_url, headers=headers, timeout=30)
            status_data = poll_resp.json()
            status = status_data.get("status")
            elapsed = int(time.time() - start_time)
            
            logger.info(f"Polling [{elapsed}s]... Status: {status}")
            
            if status == "COMPLETED":
                completed = True
                output = status_data.get("output", {})
                if output.get("status") == "success":
                    video_b64 = output.get("video_base64")
                    if video_b64:
                        logger.info("GAP 4 PASS! Video received.")
                        video_bytes = base64.b64decode(video_b64)
                        video_path = out_dir / "e2e_final.mp4"
                        with open(video_path, "wb") as f:
                            f.write(video_bytes)
                        logger.info(f"=== E2E TEST SUCCESS! Video saved to {video_path} ===")
                    else:
                        logger.error("GAP 4 (Backend Logic Error): Status was success but video_base64 is empty.")
                        sys.exit(1)
                else:
                    logger.error(f"GAP 4 (Backend Pipeline Error): {output.get('message')}")
                    logger.error(f"Full output: {json.dumps(output, indent=2, ensure_ascii=False)}")
                    sys.exit(1)
                    
            elif status == "FAILED":
                completed = True
                logger.error(f"GAP 4 (RunPod Container Error): {status_data.get('error')}")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"Polling Network Error: {str(e)}")
            time.sleep(5) # retry

if __name__ == "__main__":
    run_e2e_test()
