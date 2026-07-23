import json
from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, END

from doodler_ir import SketchBrief
from agents.sketch_planner_agent import plan_sketch_parts
from agents.timeline_director_agent import direct_timeline
from llm.deepseek_client import get_openai_compatible_client, provider_config, deepseek_configured

class StudioState(TypedDict):
    messages: List[Dict[str, str]]
    target_duration: int
    sketch_draft: dict
    timeline_draft: dict

def storywriter_node(state: StudioState):
    if not deepseek_configured():
        new_msg = state["messages"].copy()
        new_msg.append({"role": "assistant", "content": "خطای API Key"})
        return {"messages": new_msg}
        
    client = get_openai_compatible_client()
    cfg = provider_config()
    
    sys_prompt = f"""شما یک کارگردان و فیلم‌نامه‌نویس استودیوی انیمیشن هستید.
کاربر با شما صحبت می‌کند تا ایده‌اش را بسازد.
در حال حاضر تیم متخصصان شما این پیش‌نویس‌ها را آماده کرده‌اند:
طراحی کاراکتر: {json.dumps(state.get('sketch_draft', {}), ensure_ascii=False)}
سکانس‌بندی تایم‌لاین: {json.dumps(state.get('timeline_draft', {}), ensure_ascii=False)}
مدت زمان انیمیشن: {state.get('target_duration', 15)} ثانیه.

وظیفه شما:
به کاربر دوستانه و به زبان فارسی پاسخ دهید. 
حتماً با لحن هیجان‌انگیز به کاربر بگویید که تیم شما چه تغییراتی در طراحی کاراکتر (مثلا چه اعضایی قراره کشیده بشه) یا تایم‌لاین داده است.
از او بپرسید که آیا موافق است یا می‌خواهد تغییری بدهد.
"""
    formatted_messages = [{"role": "system", "content": sys_prompt}]
    formatted_messages.extend(state["messages"])
    
    try:
        response = client.chat.completions.create(
            model=cfg["model"],
            messages=formatted_messages,
            temperature=0.7,
            max_tokens=2048
        )
        content = response.choices[0].message.content
        reply = content.strip() if content else "در حال حاضر نمی‌توانم پاسخ دهم (خطای مدل)."
    except Exception as e:
        reply = f"خطا: {str(e)}"
        
    new_messages = state["messages"].copy()
    new_messages.append({"role": "assistant", "content": reply})
    
    return {"messages": new_messages}

def update_drafts_node(state: StudioState):
    if not deepseek_configured():
        return {"sketch_draft": {}, "timeline_draft": {}}
        
    client = get_openai_compatible_client()
    cfg = provider_config()
    
    chat_text = "\\n".join([f"{m['role']}: {m['content']}" for m in state["messages"]])
    summary_prompt = f"Summarize the character appearance and story so far in 1 paragraph:\\n{chat_text}"
    
    try:
        response = client.chat.completions.create(
            model=cfg["model"],
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.3,
            max_tokens=1024
        )
        content = response.choices[0].message.content
        summary = content.strip() if content else "A character."
    except:
        summary = "A character."
        
    # Call planners
    brief = SketchBrief(user_prompt=summary)
    sketch = plan_sketch_parts(brief)
    timeline = direct_timeline(sketch, state.get("target_duration", 15))
    
    return {
        "sketch_draft": sketch.model_dump(),
        "timeline_draft": timeline.model_dump()
    }

def router(state: StudioState):
    last_msg = state["messages"][-1]
    if last_msg["role"] == "user":
        return "update_drafts"
    return END

builder = StateGraph(StudioState)
builder.add_node("storywriter", storywriter_node)
builder.add_node("update_drafts", update_drafts_node)

builder.set_entry_point("update_drafts")
builder.add_edge("update_drafts", "storywriter")
builder.add_conditional_edges("storywriter", router, {
    "update_drafts": "update_drafts",
    END: END
})

studio_graph = builder.compile()

def process_chat_graph(messages: List[Dict[str, str]], target_duration: int) -> StudioState:
    """Executes one turn of the LangGraph multi-agent system."""
    initial_state = {
        "messages": messages,
        "target_duration": target_duration,
        "sketch_draft": {},
        "timeline_draft": {}
    }
    return studio_graph.invoke(initial_state)
