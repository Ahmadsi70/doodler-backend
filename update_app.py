import re

def update():
    with open("app.py", "r", encoding="utf-8") as f:
        content = f.read()
        
    start_marker = '    try:\n        status_text.text("مرحله ۱: ارسال سناریو به سرور پردازشی ابری...")'
    end_marker = '        st.divider()'
    
    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker, start_idx)
    
    if start_idx == -1 or end_idx == -1:
        print("Markers not found!")
        return
        
    new_block = """    try:
        status_text.text("در حال اتصال به سرور مستقیم...")
        import requests
        import base64
        import json
        import time

        RUNPOD_ENDPOINT_ID = os.environ.get("RUNPOD_ENDPOINT_ID", "")
        
        # We use the Pod proxy endpoint
        url = f"https://{RUNPOD_ENDPOINT_ID}-8000.proxy.runpod.net/generate"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "spec": json.loads(spec.model_dump_json())
        }
        
        progress_bar.progress(30)
        status_text.text("کارت گرافیک روشن شد! در حال رندر و ساخت انیمیشن (ممکن است چند دقیقه طول بکشد)...")
        
        # Blocking request to the FastAPI server
        response = requests.post(url, headers=headers, json=payload, timeout=300)
        
        if response.status_code != 200:
            st.error(f"خطای سرور: {response.status_code} - {response.text}")
            st.stop()
            
        result_json = response.json()
        
        progress_bar.progress(75)
        
        if result_json.get("status") == "success":
            video_b64 = result_json.get("video_base64")
            if video_b64:
                video_bytes = base64.b64decode(video_b64)
                video_path = out_dir / "final_animation.mp4"
                with open(video_path, "wb") as f:
                    f.write(video_bytes)
                
                progress_bar.progress(100)
                status_text.text("انیمیشن با موفقیت پردازش شد!")
                st.success("ویدیوی هوش مصنوعی شما با موفقیت ساخته شد.")
                
                st.video(str(video_path))
                st.balloons()
            else:
                st.error("سرور پیام موفقیت فرستاد اما ویدیویی وجود ندارد.")
        else:
            st.error(f"خطا در پردازش سرور: {result_json.get('error')}")
            
"""
    new_content = content[:start_idx] + new_block + content[end_idx:]
    
    with open("app.py", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("app.py updated successfully!")

if __name__ == "__main__":
    update()
