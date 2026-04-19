import feedparser
import requests
import sqlite3
import time
from datetime import datetime
from deep_translator import GoogleTranslator

# ================= НАЛАШТУВАННЯ =================

BOT_TOKEN = "8682834780:AAFA2LNrbqrygTkkdbLhOZwy9nPShAsnZvo"
GROUP_CHAT_ID = "-1003749922724"

# Справжні ID гілок
THREADS = {
    "news": 7,        # ⚡️ Оперативні новини
    "analytics": 9,   # 📊 Аналітика та ресерч
    "onchain": 11,    # 📈 Ончейн та трейдинг
    "web3": 13,       # 🦄 Web3 та DeFi
    "ua": 15          # 🇺🇦 Українські медіа
}

# ================= ДЖЕРЕЛА (RSS) =================

SOURCES = [
    # --- Оперативні новини ---
    {"name": "Cointelegraph", "url": "https://cointelegraph.com/rss", "thread": THREADS["news"]},
    {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "thread": THREADS["news"]},
    {"name": "CryptoSlate", "url": "https://cryptoslate.com/feed/", "thread": THREADS["news"]},
    {"name": "BeInCrypto", "url": "https://beincrypto.com/feed/", "thread": THREADS["news"]},
    {"name": "AMBCrypto", "url": "https://ambcrypto.com/feed/", "thread": THREADS["news"]},
    {"name": "U.Today", "url": "https://u.today/rss", "thread": THREADS["news"]},
    
    # --- Аналітика та ресерч ---
    {"name": "The Block", "url": "https://www.theblock.co/rss.xml", "thread": THREADS["analytics"]},
    {"name": "Crypto Briefing", "url": "https://cryptobriefing.com/feed/", "thread": THREADS["analytics"]},
    
    # --- Ончейн та трейдинг ---
    {"name": "Glassnode", "url": "https://insights.glassnode.com/rss/", "thread": THREADS["onchain"]},
    {"name": "NewsBTC", "url": "https://www.newsbtc.com/feed/", "thread": THREADS["onchain"]},
    {"name": "Bitcoinist", "url": "https://bitcoinist.com/feed/", "thread": THREADS["onchain"]},
    
    # --- Web3 та DeFi ---
    {"name": "The Defiant", "url": "https://thedefiant.io/api/feed", "thread": THREADS["web3"]},
    
    # --- Українські медіа ---
    {"name": "Incrypted", "url": "https://incrypted.com/feed/", "thread": THREADS["ua"]},
    {"name": "ForkLog UA", "url": "https://forklog.com.ua/feed", "thread": THREADS["ua"]}
]

# ================= ЛОГІКА БОТА =================

def init_db():
    conn = sqlite3.connect("crypto_news.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posted_news (
            link TEXT PRIMARY KEY
        )
    """)
    conn.commit()
    conn.close()

def is_posted(link):
    conn = sqlite3.connect("crypto_news.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM posted_news WHERE link = ?", (link,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def mark_as_posted(link):
    conn = sqlite3.connect("crypto_news.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO posted_news (link) VALUES (?)", (link,))
    conn.commit()
    conn.close()

def translate_to_ukrainian(text):
    """Функція перекладу тексту на українську"""
    try:
        # Перекладаємо на українську (uk)
        return GoogleTranslator(source='auto', target='uk').translate(text)
    except Exception as e:
        print(f"Помилка перекладу: {e}")
        return text # Якщо сталася помилка, повертаємо оригінальний текст

def send_to_telegram(text, thread_id):
    """Відправка з обходом блокування Telegram (Flood Wait)"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": GROUP_CHAT_ID,
        "message_thread_id": thread_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    
    while True: # Нескінченний цикл, поки не відправить успішно
        try:
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            
            if response.status_code == 200:
                return True
                
            # Якщо Telegram каже "Зачекайте X секунд" (код 429)
            elif response.status_code == 429:
                retry_after = data['parameters']['retry_after']
                print(f"⏳ Telegram просить зачекати {retry_after} сек. Чекаємо...")
                time.sleep(retry_after + 1) # Бот чекає потрібний час і цикл повторюється
                
            else:
                print(f"❌ Помилка Telegram: {response.text}")
                return False
                
        except Exception as e:
            print(f"Помилка відправки: {e}")
            return False

def run_parser():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Запуск перевірки новин...")
    
    for source in SOURCES:
        try:
            feed = feedparser.parse(source["url"])
            
            # Беремо свіжі новини
            for entry in feed.entries[:2]:
                link = entry.link
                title = entry.title
                
                if not is_posted(link):
                    # Перекладаємо заголовок перед публікацією
                    translated_title = translate_to_ukrainian(title)
                    
                    message = f"📰 <b>{source['name']}</b>\n\n🔹 {translated_title}\n\n👉 <a href='{link}'>Читати джерело</a>"
                    
                    if send_to_telegram(message, source["thread"]):
                        mark_as_posted(link)
                        print(f"✅ Опубліковано: {translated_title[:30]}... -> Гілка {source['thread']}")
                        time.sleep(3) # Базова пауза між повідомленнями
                        
        except Exception as e:
            print(f"Помилка парсингу {source['name']}: {e}")

if __name__ == "__main__":
    init_db()
    print("🤖 Market Scanner Bot запущено!")
    
    while True:
        run_parser()
        print("💤 Очікування 10 хвилин...\n")
        time.sleep(600)
