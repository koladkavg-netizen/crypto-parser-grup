import os
import requests
import time
import xml.etree.ElementTree as ET
import re
from flask import Flask
from threading import Thread

# --- 1. ВЕБ-СЕРВЕР ---
app = Flask('')

@app.route('/')
def home():
    return "Market Scanner AI: Multi-Model Fallback Active"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

t = Thread(target=run)
t.daemon = True
t.start()

# --- 2. КОНФІГУРАЦІЯ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
OR_KEY = os.getenv("OPENROUTER_API_KEY")

FEEDS = [
    "https://forklog.com.ua/feed/",
    "https://incrypted.com/feed/",
    "https://itc.ua/news/feed/",
    "https://ru.beincrypto.com/feed/"
]

POSTED_NEWS = set()

# --- 3. АНАЛІТИКА (КАРУСЕЛЬ МОДЕЛЕЙ) ---
def translate_and_analyze(text):
    print(f"🧠 Аналіз новини: {text[:50]}...", flush=True)
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OR_KEY}", 
        "Content-Type": "application/json",
        "HTTP-Referer": "https://render.com"
    }
    
    prompt = (
        f"Ти — провідний український крипто-аналітик. Твоє завдання:\n"
        f"1. Якісно перекласти заголовок на українську.\n"
        f"2. Додати 1-2 речення глибокої аналітики (чому це важливо для ринку).\n"
        f"3. Текст має бути завершеним, БЕЗ обірваних слів.\n"
        f"4. Стиль: професійний, лаконічний.\n\n"
        f"Новина: {text}"
    )

    # Список моделей для ротації (Fallback)
    models_to_try = [
        "openai/gpt-4o-mini",
        "google/gemini-2.0-flash-001",
        "meta-llama/llama-3.3-70b-instruct",
        "anthropic/claude-3.5-haiku"
    ]

    for attempt, model_name in enumerate(models_to_try):
        print(f"🔄 Спроба {attempt+1} з моделлю: {model_name}...", flush=True)
        try:
            res = requests.post(url, headers=headers, json={
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": 400
            }, timeout=45) # Таймаут 45 секунд на одну модель
            
            if res.status_code == 200:
                result = res.json()['choices'][0]['message']['content'].strip()
                
                print(f"🔍 [ДІАГНОСТИКА - {model_name}] Відповідь (довжина {len(result)}): {result[:120]}...", flush=True)
                
                # Фільтр якості
                if len(result) > 80 and not any(w in result.lower() for w in [' the ', ' is ', ' with ', ' translation ']):
                    return result
                else:
                    print(f"⚠️ Відхилено фільтром (закоротке або англійська). Йдемо далі...", flush=True)
            else:
                print(f"🛑 [ДІАГНОСТИКА] Помилка {model_name} ({res.status_code}): {res.text}", flush=True)
            
            time.sleep(3) # Мікро-пауза перед наступною моделлю
        except Exception as e:
            print(f"❌ Збій з'єднання з {model_name}: {e}", flush=True)
            time.sleep(3)
            
    print("❌ Жодна з 4 моделей не впоралась. Пропускаємо новину.", flush=True)
    return None

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False}
    try:
        res = requests.post(url, json=payload, timeout=20)
        return res.status_code == 200
    except:
        return False

# --- 4. ОСНОВНИЙ ЦИКЛ ---
def main_logic():
    print(f"\n🚀 --- ЗАПУСК МОНІТОРИНГУ: {time.strftime('%H:%M')} ---", flush=True)
    
    req_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/114.0.0.0 Safari/537.36'
    }
    
    for feed_url in FEEDS:
        try:
            response = requests.get(feed_url, headers=req_headers, timeout=20)
            if response.status_code != 200:
                print(f"🛑 Сайт {feed_url} заблокував доступ ({response.status_code})", flush=True)
                continue
            
            root = ET.fromstring(response.content)
            item = root.find('.//item')
            if item is None: continue
            
            title = item.find('title').text
            link = item.find('link').text
            
            if title in POSTED_NEWS: continue
            
            final_text = translate_and_analyze(title)
            
            if final_text:
                post = f"<b>💎 MARKET SCANNER ANALYTICS</b>\n\n{final_text}\n\n🔗 <a href='{link}'>Джерело</a>"
                
                if send_to_telegram(post):
                    POSTED_NEWS.add(title)
                    print(f"✅ Опубліковано: {title[:30]}...", flush=True)
                    time.sleep(45) # Затримка між постами
            
        except Exception as e:
            print(f"⚠️ Помилка обробки {feed_url}: {e}", flush=True)

if __name__ == "__main__":
    print("🤖 Бот запущено в режимі МУЛЬТИ-МОДЕЛЬ (Fallback)", flush=True)
    main_logic()
    
    while True:
        time.sleep(900)
        try:
            main_logic()
        except Exception as e:
            print(f"☢️ Збій циклу: {e}", flush=True)
