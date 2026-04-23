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
    return "Market Scanner AI: High-Speed Clean Mode"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

t = Thread(target=run)
t.daemon = True
t.start()

# --- 2. КОНФІГУРАЦІЯ ---
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("GROUP_CHAT_ID")
OR_KEY = os.getenv("OPENROUTER_API_KEY")

FEEDS = [
    "https://forklog.com.ua/feed/",
    "https://incrypted.com/feed/",
    "https://itc.ua/news/feed/",
    "https://ru.beincrypto.com/feed/",
    "https://bits.media/rss/",
    "https://coingape.com/feed/",
    "https://en.bits.media/rss/"
]

POSTED_NEWS = set()

# --- 3. ШВИДКИЙ ПЕРЕКЛАД (CLEAN MODE) ---
def fast_translate(text):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OR_KEY}", 
        "Content-Type": "application/json",
        "HTTP-Referer": "https://render.com"
    }
    
    # Жорстка інструкція не використовувати зайві слова
    prompt = (
        f"Переклади цей заголовок новини на українську та з нового рядка додай одне речення пояснення. "
        f"КАТЕГОРИЧНО ЗАБОРОНЕНО використовувати слова 'Заголовок:', 'Суть новини:', 'Ось переклад:' чи подібні. "
        f"Просто чистий текст перекладу та пояснення.\n\n"
        f"Новина: {text}"
    )

    models_to_try = ["openai/gpt-4o-mini", "google/gemini-2.0-flash-001", "anthropic/claude-3-haiku"]

    for model_name in models_to_try:
        try:
            res = requests.post(url, headers=headers, json={
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 250
            }, timeout=30) 
            
            if res.status_code == 200:
                result = res.json()['choices'][0]['message']['content'].strip()
                
                # Додатковий фільтр-зачистка (на випадок, якщо ШІ проігнорував інструкцію)
                bad_labels = [
                    "Заголовок:", "Суть новини:", "Заголовок", "Суть", 
                    "Headline:", "Summary:", "Переклад:", "Ось переклад:"
                ]
                for label in bad_labels:
                    # Видаляємо без врахування регістру
                    result = re.sub(re.escape(label), "", result, flags=re.IGNORECASE).strip()
                
                if len(result) > 30:
                    return result.replace("**", "").replace("«", "").replace("»", "")
            
            print(f"⚠️ Модель {model_name} не підійшла, зміна...", flush=True)
            time.sleep(1)
        except:
            continue
            
    return None

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False}
    try:
        res = requests.post(url, json=payload, timeout=20)
        if res.status_code != 200:
            print(f"❌ TG ERROR: {res.text}", flush=True)
        return res.status_code == 200
    except:
        return False

# --- 4. ОСНОВНИЙ ЦИКЛ ---
def main_logic():
    print(f"\n⚡ --- СКАНИРОВАНИЕ РИНКУ: {time.strftime('%H:%M')} ---", flush=True)
    
    req_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/114.0.0.0 Safari/537.36'}
    
    for feed_url in FEEDS:
        try:
            response = requests.get(feed_url, headers=req_headers, timeout=20)
            if response.status_code != 200: continue
            
            root = ET.fromstring(response.content)
            items = root.findall('.//item')[:3]
            
            for item in items:
                title = item.find('title').text
                link = item.find('link').text
                
                if title in POSTED_NEWS: continue
                
                print(f"📡 Обробка новини: {title[:50]}...", flush=True)
                final_text = fast_translate(title)
                
                if final_text:
                    # Розбиваємо текст, щоб зробити перше речення (заголовок) жирним
                    lines = final_text.split('\n')
                    if len(lines) > 1:
                        # Перша лінія жирна, інші — звичайні
                        formatted_text = f"<b>{lines[0]}</b>\n\n" + "\n".join(lines[1:])
                    else:
                        formatted_text = f"<b>{final_text}</b>"

                    post = f"🗞 {formatted_text}\n\n🔗 <a href='{link}'>Джерело</a>"
                    
                    if send_to_telegram(post):
                        POSTED_NEWS.add(title)
                        print(f"✅ Готово!", flush=True)
                        time.sleep(10)
            
        except Exception as e:
            print(f"⚠️ Помилка на {feed_url}: {e}", flush=True)

if __name__ == "__main__":
    print("🚀 Бот запущено: CLEAN HIGH-SPEED MODE", flush=True)
    main_logic()
    
    while True:
        time.sleep(600)
        try:
            main_logic()
        except Exception as e:
            print(f"☢️ Збій: {e}", flush=True)
