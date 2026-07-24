"""DoodlerGAN & Animated Drawings Studio UI - Interactive Flow"""

import streamlit as st
import sys
import os
import subprocess
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

from doodler_pipeline import run_doodle_pipeline
from doodler_ir import PartNode
from agents.storywriter_agent import chat_with_storywriter, summarize_story

st.set_page_config(page_title="AI Sketch & Animation Studio", page_icon="🎨", layout="centered")

# -- Session State Initialization --
if "phase" not in st.session_state:
    st.session_state.phase = "input"  # input -> review -> render
if "spec" not in st.session_state:
    st.session_state.spec = None
if "target_duration" not in st.session_state:
    st.session_state.target_duration = 15
if "out_dir" not in st.session_state:
    st.session_state.out_dir = "out/doodle_test"
if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("🎨 AI Sketch & Animation Studio")
st.markdown("**(Powered by DoodlerGAN & Animated Drawings)**")

# ==========================================
# PHASE 1: INPUT
# ==========================================
if st.session_state.phase == "input":
    st.write("با نماینده تیم (کارگردان، طراح نقاشی و کارگردان صدا) صحبت کنید تا ایده شما را به یک سناریوی جذاب تبدیل کنند!")
    
    st.divider()
    st.subheader("تنظیمات اولیه انیمیشن")
    target_duration = st.slider("مدت زمان کل انیمیشن (ثانیه):", min_value=5, max_value=60, value=st.session_state.target_duration, step=5)
    st.session_state.target_duration = target_duration
    out_dir_input = st.text_input("پوشه خروجی (Output Directory):", st.session_state.out_dir)
    st.session_state.out_dir = out_dir_input
    st.divider()
    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("ایده خود را بنویسید (مثلاً: یک قورباغه که پیانو می‌زند)"):
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        # Add to state
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Get response from LangGraph Studio
        with st.chat_message("assistant"):
            with st.spinner("تیم استودیو در حال همفکری (LangGraph)..."):
                from agents.studio_graph import process_chat_graph
                # Exclude the assistant reply since process_chat_graph appends it
                state_out = process_chat_graph(st.session_state.messages, st.session_state.target_duration)
                response = state_out["messages"][-1]["content"]
                st.markdown(response)
                
                # Store the drafts in session state for later use
                st.session_state.sketch_draft = state_out.get("sketch_draft", {})
                st.session_state.timeline_draft = state_out.get("timeline_draft", {})
        st.session_state.messages.append({"role": "assistant", "content": response})


    if st.button("✨ داستان کامل شد ➔ طراحی سناریو", type="primary"):
        if not st.session_state.messages:
            st.error("لطفاً ابتدا حداقل یک ایده در چت بنویسید.")
        else:
            st.session_state.out_dir = out_dir_input
            with st.spinner("در حال جمع‌بندی داستان و طراحی سناریو..."):
                try:
                    from doodler_ir import DoodlerStudioSpec, SketchSequence, TimelineSequence, SketchBrief
                    
                    final_brief_text = "\\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
                    brief = SketchBrief(user_prompt=final_brief_text)
                    
                    sketch_data = st.session_state.get("sketch_draft", {})
                    timeline_data = st.session_state.get("timeline_draft", {})
                    
                    sketch = SketchSequence(**sketch_data) if sketch_data else SketchSequence(creature_name="Unknown", lore=final_brief_text, parts=[])
                    timeline = TimelineSequence(**timeline_data) if timeline_data else TimelineSequence(scenes=[])
                    
                    spec = DoodlerStudioSpec(brief=brief, sketch=sketch, timeline=timeline)
                    
                    st.session_state.target_duration = target_duration
                    st.session_state.spec = spec
                    st.session_state.phase = "review"
                    st.rerun()
                except Exception as e:
                    st.error(f"خطا در ارتباط با هوش مصنوعی: {str(e)}")

# ==========================================
# PHASE 2: REVIEW & EDIT (Human-in-the-Loop)
# ==========================================
elif st.session_state.phase == "review":
    st.success("سناریو با موفقیت توسط هوش مصنوعی طراحی شد!")
    st.write("شما می‌توانید قبل از مرحله ساخت نهایی، اجزای نقاشی و نوع حرکت را ویرایش کنید.")
    
    spec = st.session_state.spec
    
    # 1. Edit Creature Metadata
    st.subheader("مشخصات کاراکتر")
    new_name = st.text_input("نام کاراکتر", spec.sketch.creature_name)
    new_lore = st.text_area("داستان (Lore)", spec.sketch.lore)
    
    # 2. Edit Parts (DoodlerGAN)
    st.subheader("اجزای نقاشی (DoodlerGAN Sequence)")
    
    # Convert parts to a list of dicts for data_editor
    parts_data = [{"order": p.order, "part_type": p.part_type, "prompt": p.prompt} for p in spec.sketch.parts]
    
    edited_parts_data = st.data_editor(
        parts_data,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "order": st.column_config.NumberColumn("ترتیب", step=1),
            "part_type": st.column_config.SelectboxColumn("نوع عضو", options=["body", "head", "eye", "mouth", "wing", "leg", "arm", "tail", "horn", "other"]),
            "prompt": st.column_config.TextColumn("توضیحات تکمیلی"),
        }
    )
    
    # 3. Advanced Settings (Art Style)
    st.subheader("تنظیمات پیشرفته رندر")
    
    import json
    styles_list = []
    style_ids = []
    try:
        with open("libraries/styles/starter_pack.json", "r", encoding="utf-8") as f:
            styles_db = json.load(f)
            for style_item in styles_db.get("styles", []):
                styles_list.append(f"{style_item['name']} ({style_item['style_id']})")
                style_ids.append(style_item["style_id"])
    except:
        styles_list = ["Symmetrical Pastel Cinema (symmetrical_pastel_cinema)"]
        style_ids = ["symmetrical_pastel_cinema"]
        
    current_style_idx = 0
    if getattr(spec, "style_id", "") in style_ids:
        current_style_idx = style_ids.index(spec.style_id)
        
    selected_style_name = st.selectbox("سبک هنری (Art Style)", options=styles_list, index=current_style_idx)
    selected_style_id = style_ids[styles_list.index(selected_style_name)]
    
    st.divider()
    
    # 4. Edit Timeline (Animated Drawings)
    st.subheader("تایم‌لاین انیمیشن (Timeline)")
    motions = ["walk", "run", "jump", "dance", "wave", "idle"]
    
    timeline_data = [{"start_time": s.start_time, "end_time": s.end_time, "motion_type": s.motion_type, "sfx_prompt": s.sfx_prompt} for s in spec.timeline.scenes]
    
    edited_timeline_data = st.data_editor(
        timeline_data,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "start_time": st.column_config.NumberColumn("شروع (ثانیه)", step=0.1, min_value=0.0),
            "end_time": st.column_config.NumberColumn("پایان (ثانیه)", step=0.1, min_value=0.0),
            "motion_type": st.column_config.SelectboxColumn("نوع حرکت", options=motions),
            "sfx_prompt": st.column_config.TextColumn("افکت صوتی (SFX)"),
        }
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ تایید و رندر نهایی", type="primary"):
            # Update spec in state
            spec.sketch.creature_name = new_name
            spec.sketch.lore = new_lore
            
            new_parts = []
            for i, p_dict in enumerate(edited_parts_data):
                new_parts.append(PartNode(
                    id=f"part_{i}",
                    part_type=p_dict.get("part_type", "other"),
                    order=p_dict.get("order", i),
                    prompt=p_dict.get("prompt", "")
                ))
            spec.sketch.parts = new_parts
            
            from doodler_ir import AnimationScene
            new_scenes = []
            for s_dict in edited_timeline_data:
                new_scenes.append(AnimationScene(
                    start_time=s_dict.get("start_time", 0.0),
                    end_time=s_dict.get("end_time", 1.0),
                    motion_type=s_dict.get("motion_type", "idle"),
                    sfx_prompt=s_dict.get("sfx_prompt", "")
                ))
            spec.timeline.scenes = new_scenes
            spec.style_id = selected_style_id
            
            st.session_state.spec = spec
            st.session_state.phase = "render"
            st.rerun()
            
    with col2:
        if st.button("بازگشت و ایده‌پردازی مجدد"):
            st.session_state.phase = "input"
            st.rerun()

# ==========================================
# PHASE 3: EXECUTION / RENDER
# ==========================================
elif st.session_state.phase == "render":
    st.info("در حال برقراری ارتباط با سرور ابری RunPod...")
    spec = st.session_state.spec
    out_dir = Path(st.session_state.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    progress_bar = st.progress(10)
    status_text = st.empty()
    
    try:
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
        
        # 1. Send the job to the queue
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            st.error(f"خطای سرور: {response.status_code} - {response.text}")
            st.stop()
            
        result_json = response.json()
        job_id = result_json.get("job_id")
        
        if not job_id:
            st.error("سرور Job ID برنگرداند.")
            st.stop()
            
        status_text.text("درخواست با موفقیت در صف سرور قرار گرفت! کارت گرافیک روشن شد...")
        progress_bar.progress(20)
        
        # 2. Polling for status
        status_url = f"https://{RUNPOD_ENDPOINT_ID}-8000.proxy.runpod.net/status/{job_id}"
        
        while True:
            time.sleep(5)
            status_res = requests.get(status_url, timeout=10)
            if status_res.status_code != 200:
                st.warning("خطا در ارتباط با سرور، در حال تلاش مجدد...")
                continue
                
            status_data = status_res.json()
            status = status_data.get("status")
            
            if status == "processing":
                # Create a moving progress bar effect
                import random
                current_prog = random.randint(30, 85)
                progress_bar.progress(current_prog)
                status_text.text("در حال رندر و ساخت انیمیشن (ممکن است چند دقیقه طول بکشد)...")
            elif status == "completed":
                break
            elif status == "failed":
                st.error(f"خطا در پردازش سرور: {status_data.get('error')}")
                st.stop()
        
        progress_bar.progress(95)
        
        if status == "completed":
            video_b64 = status_data.get("video_base64")
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
            
        st.divider()
        if st.button("شروع ساخت انیمیشن جدید"):
            st.session_state.phase = "input"
            st.rerun()
            
    except Exception as e:
        st.error(f"خطای ارتباط با سرور ابری: {str(e)}")
        if st.button("تلاش مجدد"):
            st.rerun()

