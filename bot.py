import sys
import io
import openai
import requests
import json
import urllib.parse
import time
import random
import feedparser
import os
import re  # اضافه شده برای تمیزکاری متن
import os  # این کتابخانه برای خواندن رمزها از گیت‌هاب است

# ==================== CONFIGURATION (SECURE MODE) ====================
# به جای نوشتن رمز، می‌گوییم: "برو از گیت‌هاب بپرس رمز چیه"
METIS_API_KEY = os.environ.get("METIS_API_KEY")
GOOGLE_SCRIPT_URL = os.environ.get("GOOGLE_SCRIPT_URL")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")

SEARCH_TOPICS_POOL = [
    "Artificial Intelligence Video Generation Marketing",
    "AI in Content Creation Tools",
    "Gen-Z Marketing Trends 2025",
    "Gen-Z psychology and consumer behavior",
    "Psychology of Gen-Z for business owners"
]
# =====================================================================sdfsd

client = openai.OpenAI(
    api_key=METIS_API_KEY,
    base_url="https://api.metisai.ir/openai/v1"
)

# --- تابع جدید برای تمیز کردن متن‌های اضافی ---
def clean_prefix(text):
    # حذف عباراتی مثل "کپشن تلگرام:" یا "متن لینکدین:" از اول جملات
    patterns = [r"کپشن تلگرام:?", r"متن تلگرام:?", r"Telegram Caption:?", r"LinkedIn Post:?", r"متن لینکدین:?"]
    for p in patterns:
        text = re.sub(p, "", text, flags=re.IGNORECASE).strip()
    return text

def load_knowledge_base():
    try:
        with open("knowledge.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

# --- بخش گوگل نیوز (بدون تغییر) ---
def fetch_real_trends():
    chosen_topic = random.choice(SEARCH_TOPICS_POOL)
    print(f"🌍 Topic: '{chosen_topic}'")
    rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(chosen_topic)}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(rss_url)
        return [entry.title for entry in feed.entries[:5]]
    except: return []

def translate_and_filter_topics(english_topics):
    topics_str = "\n".join(english_topics)
    knowledge = load_knowledge_base()
    prompt = f"""
    Context: {knowledge}
    Select 3 best topics for A-ART Studio from list below.
    Translate to viral PERSIAN blog titles.
    List: {topics_str}
    Output: Just 3 Persian lines.
    """
    try:
        res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        return [t.strip().replace('- ', '').replace('• ', '') for t in res.choices[0].message.content.split('\n') if t.strip()]
    except: return []

# --- مدیریت صف ---
def get_pending_topics():
    print("🔎 Checking Queue...")
    try:
        response = requests.get(f"{GOOGLE_SCRIPT_URL}?action=get_queue")
        pending_tasks = response.json()
        if not pending_tasks:
            print("⚠️ Queue empty. Fetching news...")
            news = fetch_real_trends()
            if news:
                persian = translate_and_filter_topics(news)
                add_topics_to_queue(persian)
                time.sleep(3)
                return get_pending_topics()
            return []
        return pending_tasks
    except: return []

def add_topics_to_queue(topics_list):
    if topics_list:
        requests.post(GOOGLE_SCRIPT_URL, data=json.dumps({"action": "add_topics", "topics": topics_list}), headers={'Content-Type': 'application/json'})

# --- تولید محتوا (با فیکس باگ‌ها) ---
def generate_content(topic):
    print(f"✍️  Writing: {topic}") 
    knowledge = load_knowledge_base()
    
    article_prompt = f"""
    ROLE: Senior Content Strategist at A-ART.
    LANGUAGE: PERSIAN (Farsi).
    KNOWLEDGE: {knowledge}
    TOPIC: {topic}
    
    INSTRUCTIONS:
    Write a 600-word blog post.
    FORMAT: HTML tags only (<p>, <h2>, <ul>, <li>).
    
    ⛔ CRITICAL RULES:
    1. DO NOT use ```html or ``` markdown tags at the start/end.
    2. DO NOT write <h1>.
    3. Start directly with the text.
    """
    
    try:
        article_raw = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content": article_prompt}]).choices[0].message.content
        
        # ✅ فیکس ۱: حذف تگ‌های مارک‌داون مزاحم
        article = article_raw.replace("```html", "").replace("```", "").strip()
        
        social_prompt = f"""
        Topic: {topic}
        
        1. Write a Telegram Caption:
           - Casual, Gen-Z tone.
           - Use paragraphs (leave empty lines).
           - Do NOT start with "Here is caption". Just the text.
        
        2. Write a LinkedIn Post:
           - Professional & Analytical.
        
        Separator: '---'
        """
        socials = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content": social_prompt}]).choices[0].message.content
        parts = socials.split('---')
        
        # ✅ فیکس ۲: تمیز کردن پیشوندها
        tg_text = clean_prefix(parts[0].strip())
        li_text = clean_prefix(parts[1].strip()) if len(parts) > 1 else ""
        
        title = client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role":"user", "content": f"Clickbait Persian title for: {topic}"}]).choices[0].message.content.replace('"','')
        
        return title, article, tg_text, li_text
    except Exception as e:
        print(f"❌ Generation Error: {e}")
        return None, None, None, None

def generate_image(topic):
    print("🎨 Image...")
    try:
        trans = client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role":"user", "content": f"Translate topic to visual description: {topic}"}]).choices[0].message.content
        prompt = f"Cinematic shot, {trans}, Dark Cyberpunk style, Matte Black background with Acid Lime Green (#CCFF00) neon highlights. A mysterious black crow with glowing green eyes is watching. 8k render."
        encoded = urllib.parse.quote(prompt)
        seed = random.randint(1, 99999)
        return f"https://image.pollinations.ai/prompt/{encoded}?width=1280&height=720&nologo=true&seed={seed}&model=flux"
    except: return "https://via.placeholder.com/800x450"

# --- انتشار (با فیکس لینک) ---
def publish_telegram(image_url, caption, title):
    print("✈️  Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    
    # ✅ فیکس ۳: پاراگراف‌بندی و فاصله درست لینک
    final_caption = f"<b>{title}</b>\n\n{caption}\n\n──────────────\n🔗 <b>مطالعه کامل مقاله:</b>\nhttps://aart-team.com/blog/"
    
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "photo": image_url,
        "caption": final_caption,
        "parse_mode": "HTML" # استفاده از HTML برای بولد کردن تایتل
    }
    try:
        res = requests.post(url, data=payload).json()
        if res.get('ok'):
            return f"https://t.me/{TELEGRAM_CHANNEL_ID.replace('@','')}/{res['result']['message_id']}"
        print(f"TeleErr: {res}")
        return "Failed"
    except: return "Error"

def finalize(row_id, title, content, image, tg_link, li_text):
    print("💾 Saving...")
    payload = {"action": "publish", "rowId": row_id, "title": title, "content": content, "image": image, "tgLink": tg_link, "liText": li_text}
    requests.post(GOOGLE_SCRIPT_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
    print(f"✅ DONE: {title}")

# --- MAIN ---
if __name__ == "__main__":
    print("\n--- 🚀 A-ART BOT (Bug Fix Edition) ---")
    tasks = get_pending_topics()
    if tasks:
        t = tasks[0]
        title, article, tg, li = generate_content(t['topic'])
        if title:
            img = generate_image(t['topic'])
            tg_link = publish_telegram(img, tg, title)
            finalize(t['row'], title, article, img, tg_link, li)
    else: print("No tasks.")
