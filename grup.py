import os
import requests
import time
import xml.etree.ElementTree as ET
import re
from flask import Flask
from threading import Thread

# --- 1. FLASK SERVER (Щоб Render не засинав) ---
app = Flask('')

@app.route('/')
def home():
    return "Market Scanner AI is running!"

def run():
    # Render використовує порт 8080 за замовчуванням або змінну PORT
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 2. КОНФІГУРАЦІЯ (Беремо з Environment Variables) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
OR_KEY = os.getenv("OPENROUTER_API_KEY")

# Список джерел
FEEDS = [
    "https://forklog.com.ua/feed/",
    "https://incrypted.com/feed/",
    "https://itc.ua/news/feed/",
    "https://bits.media/rss/",
    "https://ru.beincrypto.com/feed/"
]

# Історія опублікованих новин (у пам'яті)
POSTED_NEWS = set()

# --- 3. ЛОГІКА ПЕРЕКЛАДУ ---
def translate_news(text):
    """Потужний переклад через OpenRouter з 3 спробами та валідацією мови"""
    print(f"🔄 Запит на переклад: {text[:50]}...")
    
    clean_text = re.sub(r'<[^>]+>', '', text)[:1200] 
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OR_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = (
        "Ти професійний крипто-журналіст. Твоє завдання: перекласти текст на УКРАЇНСЬКУ мову. "
        "Пиши стисло, професійно, використовуй крипто-терміни. Не використовуй фрази 'Ось переклад'. "
        f"Текст для перекладу:\n{clean_text}"
    )

    for attempt in range(3):
        try:
            res = requests.post(url, headers=headers, json={
                "model": "google/gemini-2.0-flash-001",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }, timeout=45)
            
            if res.status_code == 200:
                translated = res.json()['choices'][0]['message']['content'].strip()
                
                # Перевірка: чи не залишилася англійська мова?
                english_indicators = [' the ', ' is ', ' with ', ' and ', ' that ']
                if not any(word in translated.lower() for word in english_indicators):
                    return translated
                else:
                    print(f"⚠️ Спроба {attempt+1}: Отримано текст з англійськими словами. Повтор...")
            else:
                print(f"⚠️ Помилка OpenRouter ({res.status_code}): {res.text}")
        except Exception as e:
            print(f"⚠️ Збій мережі при перекладі: {e}")
        
        time.sleep(5) # Пауза перед наступною спробою
    
    return None # Якщо всі 3 спроби провалені

# --- 4. ВІДПРАВКА В TELEGRAM ---
def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        res = requests.post(url, json=payload, timeout=20)
        return res.status_code == 200
    except:
        return False

# --- 5. ОСНОВНИЙ ЦИКЛ ---
def parse_and_post():
    print(f"\n--- ПЕРЕВІРКА НОВИН: {time.strftime('%H:%M:%S')} ---")
    
    for feed_url in FEEDS:
        try:
            response = requests.get(feed_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
            if response.status_code != 200: continue
            
            root = ET.fromstring(response.content)
            # Перевіряємо останні 3 новини з кожного джерела
            for item in root.findall('.//item')[:3]:
                title = item.find('title').text
                link = item.find('link').text
                
                if title in POSTED_NEWS:
                    continue
                
                print(f"🆕 Знайдено: {title}")
                
                translated_text = translate_news(title)
                
                if translated_text
