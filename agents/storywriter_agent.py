import json
from typing import List, Dict
from llm.deepseek_client import get_openai_compatible_client, provider_config, deepseek_configured

SYSTEM_PROMPT = """
شما یک فیلم‌نامه‌نویس و کارگردان انیمیشن خلاق هستید.
وظیفه شما این است که ایده خام کاربر برای یک انیمیشن کوتاه (پانتومیم / بدون دیالوگ) را دریافت کنید و به او کمک کنید تا ایده خود را بسط دهد.
شما باید پیشنهاداتی در مورد:
- ظاهر کاراکتر (رنگ، لباس، ابعاد)
- کاری که قرار است انجام دهد (حرکت اصلی)
به او بدهید.
از او سوالات کوتاه بپرسید تا او را در مسیر خلق یک داستان جذاب و خنده‌دار یا دراماتیک هدایت کنید.
پاسخ‌های شما باید دوستانه، پرانرژی و به زبان فارسی روان باشد.
همیشه سعی کنید پیشنهادهای بصری و جذاب بدهید.
اگر کاربر ایده را تایید کرد و گفت که کافی است، به او بگویید که روی دکمه "طراحی سناریو" کلیک کند.
"""

def chat_with_storywriter(messages: List[Dict[str, str]]) -> str:
    """
    Multi-turn chat with the Storywriter Agent.
    messages: [{"role": "user"|"assistant", "content": "text"}, ...]
    """
    if not deepseek_configured():
        return "لطفاً کلید API خود را در فایل .env وارد کنید تا بتوانم به شما کمک کنم!"
        
    client = get_openai_compatible_client()
    cfg = provider_config()
    
    formatted_messages = [{"role": "system", "content": SYSTEM_PROMPT.strip()}]
    formatted_messages.extend(messages)
    
    try:
        response = client.chat.completions.create(
            model=cfg["model"],
            messages=formatted_messages,
            temperature=0.85,
            max_tokens=512
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"خطا در ارتباط با هوش مصنوعی: {str(e)}"

def summarize_story(messages: List[Dict[str, str]]) -> str:
    """
    Summarize the final agreed-upon story from the chat history.
    """
    if not deepseek_configured():
        return "بدون ایده (خطای API)"
        
    client = get_openai_compatible_client()
    cfg = provider_config()
    
    chat_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
    
    prompt = f"""
    Based on the following chat between a user and a storywriter, summarize the final animation idea into a single, highly descriptive paragraph.
    Focus exclusively on the visual appearance of the character(s) and their intended action/motion.
    
    Chat History:
    {chat_text}
    
    Summary (in Persian):
    """
    
    try:
        response = client.chat.completions.create(
            model=cfg["model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=256
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "خلاصه سازی داستان با خطا مواجه شد."
