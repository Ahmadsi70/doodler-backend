import re

with open("runpod_backend/server.py", "r", encoding="utf-8") as f:
    code = f.read()

# Add BackgroundTasks and uuid
code = code.replace("from fastapi import FastAPI, Request", "from fastapi import FastAPI, Request, BackgroundTasks\nimport uuid")

# Add JOBS
code = code.replace("sd_pipe = None\n", "sd_pipe = None\n\nJOBS = {}\n")

# Replace generate endpoint
generate_old = '''@app.post("/generate")
async def generate_video(request: Request):
    """
    Main generation endpoint.
    Expects JSON payload with "spec"
    """
    from rembg import remove
    from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
    
    payload = await request.json()
    spec = payload.get("spec")
    if not spec:
        return JSONResponse(status_code=400, content={"error": "Missing 'spec' in input payload."})'''

generate_new = '''@app.post("/generate")
async def generate_video(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    spec = payload.get("spec")
    if not spec:
        return JSONResponse(status_code=400, content={"error": "Missing 'spec' in input payload."})
        
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "processing", "video_base64": None, "error": None}
    
    background_tasks.add_task(process_video_job, job_id, spec)
    
    return {"status": "success", "job_id": job_id, "message": "Job added to queue"}

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in JOBS:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    return JOBS[job_id]

def process_video_job(job_id: str, spec: dict):
    from rembg import remove
    from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
    
    try:'''

code = code.replace(generate_old, generate_new)

# Indent all lines from '    print("Received Spec")' to the end by 4 spaces
# Wait, let's just find the index of '    print("Received Spec")' and indent everything
idx = code.find('    print("Received Spec")')
if idx != -1:
    lines = code[idx:].split('\\n')
    new_lines = []
    for line in lines:
        if line == '':
            new_lines.append('')
        else:
            new_lines.append('    ' + line)
    
    # We also need to add the except block at the end
    end_except = '''
    except Exception as e:
        print(f"Job {job_id} failed: {str(e)}")
        JOBS[job_id] = {"status": "failed", "error": str(e)}
'''
    code = code[:idx] + '\\n'.join(new_lines) + end_except

# Fix the Return in process_video_job
return_old = '''        return {
            "status": "success",
            "video_base64": b64_vid,
            "message": "Rendered successfully."
        }'''
return_new = '''        JOBS[job_id] = {
            "status": "completed",
            "video_base64": b64_vid,
            "message": "Rendered successfully."
        }'''
code = code.replace(return_old, return_new)

# Also fix the inner try/except for AnimatedDrawings
ad_old = '''        except subprocess.CalledProcessError as e:
                print(f"Render failed with error code {e.returncode}")
                return JSONResponse(status_code=500, content={"error": f"AnimatedDrawings failed: stderr={e.stderr}, stdout={e.stdout}"})
            except Exception as e:
                print(f"Render exception: {e}")
                return JSONResponse(status_code=500, content={"error": f"AnimatedDrawings exception: {str(e)}"})'''

ad_new = '''        except subprocess.CalledProcessError as e:
                print(f"Render failed with error code {e.returncode}")
                JOBS[job_id] = {"status": "failed", "error": f"AnimatedDrawings failed: stderr={e.stderr}, stdout={e.stdout}"}
                return
            except Exception as e:
                print(f"Render exception: {e}")
                JOBS[job_id] = {"status": "failed", "error": f"AnimatedDrawings exception: {str(e)}"}
                return'''
code = code.replace(ad_old, ad_new)

with open("runpod_backend/server.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Done")
