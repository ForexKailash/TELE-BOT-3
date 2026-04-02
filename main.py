import telebot
import sqlite3
import threading
import time
import requests
from flask import Flask, request

# ---------------- CONFIG ----------------
TOKEN = "8653450456:AAER9w6Gjj5IWkyCs1taa01N-DdMFZqxt3E"
ADMIN_ID = 6253584826

PUBLIC_CHANNEL = -1003807818260
VIP_CHANNEL = -1003826269063

VIP_LINK = "https://t.me/+Snj0BVAwjDo3NTA1"
UPI = "kailashbhardwaj66-2@okicici"

API_KEY = "02ef5f7e644f43d18bbe5ae297d0666b"
WEBHOOK_URL = "https://tele-bot-2-production.up.railway.app/webhook"

PAIRS = ["EUR/USD", "GBP/USD", "XAU/USD", "BTC/USD"]

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ---------------- DATABASE ----------------
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT, free_used INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS signals (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, direction TEXT, entry REAL, tp1 REAL, tp2 REAL, sl REAL, result TEXT, msg_id INTEGER, channel TEXT)")
conn.commit()

# ---------------- INDICATORS ----------------
def sma(data, n):
    return sum(data[-n:]) / n if len(data) >= n else sum(data) / len(data)

def rsi(data):
    gain = loss = 0
    for i in range(1, len(data)):
        diff = data[i] - data[i - 1]
        if diff > 0:
            gain += diff
        else:
            loss -= diff
    if loss == 0:
        return 100
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# ---------------- DATA ----------------
def get_data(symbol):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1h&apikey={API_KEY}&outputsize=100"
        r = requests.get(url, timeout=5).json()

        if "values" not in r:
            return []

        closes = [float(i['close']) for i in r['values']]
        closes.reverse()
        return closes

    except:
        return []

# ---------------- STRATEGY ----------------
def analyze(symbol):
    data = get_data(symbol)
    if len(data) < 50:
        return None

    price = data[-1]
    s20 = sma(data, 20)
    s50 = sma(data, 50)
    r = rsi(data)

    # sideways filter
    if abs(s20 - s50) < 0.0001:
        return None

    score = 0

    if price > s50:
        score += 2
    else:
        score -= 2

    if s20 > s50:
        score += 2
    else:
        score -= 2

    if 45 < r < 65:
        score += 1
    elif r > 70 or r < 30:
        score -= 2

    confidence = min(abs(score) * 20, 100)

    if confidence < 60:
        return None

    direction = "BUY" if score > 0 else "SELL"

    tp1 = price * (1.002 if direction == "BUY" else 0.998)
    tp2 = price * (1.005 if direction == "BUY" else 0.995)
    sl = price * (0.998 if direction == "BUY" else 1.002)

    return {
        "symbol": symbol,
        "direction": direction,
        "entry": round(price, 5),
        "tp1": round(tp1, 5),
        "tp2": round(tp2, 5),
        "sl": round(sl, 5),
        "confidence": confidence
    }

# ---------------- BEST SIGNAL ----------------
def best_signal():
    best = None
    for p in PAIRS:
        s = analyze(p)
        if s and (not best or s['confidence'] > best['confidence']):
            best = s
    return best

# ---------------- SEND ----------------
def send(channel):
    s = best_signal()
    if not s:
        return

    text = f"""🚀 SIGNAL

{ s['symbol'] }
{ s['direction'] }

Entry: {s['entry']}
TP1: {s['tp1']}
TP2: {s['tp2']}
SL: {s['sl']}

Confidence: {s['confidence']}%

🔥 KAILASH TRADING
{VIP_LINK}
"""

    msg = bot.send_message(channel, text)

    cursor.execute("INSERT INTO signals(symbol,direction,entry,tp1,tp2,sl,result,msg_id,channel) VALUES(?,?,?,?,?,?,?,?,?)",
                   (s['symbol'], s['direction'], s['entry'], s['tp1'], s['tp2'], s['sl'], "open", msg.message_id, str(channel)))
    conn.commit()

# ---------------- MONITOR ----------------
def monitor():
    while True:
        try:
            cursor.execute("SELECT id,symbol,tp1,tp2,sl,msg_id,channel FROM signals WHERE result='open'")
            rows = cursor.fetchall()

            for r in rows:
                data = get_data(r[1])
                if not data:
                    continue

                price = data[-1]

                # TP
                if price >= r[2] or price <= r[3]:
                    bot.send_message(int(r[6]), "🔥 TP HIT 🚀\n" + VIP_LINK)
                    cursor.execute("UPDATE signals SET result='tp' WHERE id=?", (r[0],))

                # SL
                if price <= r[4] or price >= r[4]:
                    if int(r[6]) == PUBLIC_CHANNEL:
                        try:
                            bot.delete_message(PUBLIC_CHANNEL, r[5])
                        except:
                            pass
                    cursor.execute("UPDATE signals SET result='sl' WHERE id=?", (r[0],))

            conn.commit()
            time.sleep(180)

        except:
            pass

# ---------------- SCHEDULER ----------------
def scheduler():
    while True:
        try:
            send(PUBLIC_CHANNEL)
            time.sleep(1800)  # 30 min
        except:
            pass

# ---------------- PROMO ----------------
def promo():
    while True:
        try:
            bot.send_message(PUBLIC_CHANNEL, f"🔥 JOIN VIP NOW\nUPI:{UPI}\n{VIP_LINK}")
            time.sleep(1800)
        except:
            pass

# ---------------- COMMANDS ----------------
@bot.message_handler(commands=['start'])
def start(m):
    bot.send_message(m.chat.id, "🚀 Welcome\nUse /free")
    cursor.execute("INSERT OR IGNORE INTO users(user_id,name) VALUES(?,?)", (m.chat.id, m.from_user.first_name))
    conn.commit()

@bot.message_handler(commands=['free'])
def free(m):
    cursor.execute("SELECT free_used FROM users WHERE user_id=?", (m.chat.id,))
    d = cursor.fetchone()

    if d and d[0] >= 3:
        bot.send_message(m.chat.id, "Limit Over Join VIP\n" + VIP_LINK)
        return

    send(m.chat.id)
    cursor.execute("UPDATE users SET free_used=free_used+1 WHERE user_id=?", (m.chat.id,))
    conn.commit()

# ---------------- WEBHOOK ----------------
@app.route('/webhook', methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode())])
    return 'ok'

@app.route('/')
def home():
    return 'OK'

# ---------------- RUN ----------------
def run():
    threading.Thread(target=monitor, daemon=True).start()
    threading.Thread(target=scheduler, daemon=True).start()
    threading.Thread(target=promo, daemon=True).start()

    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        app.run(host="0.0.0.0", port=8080)
    except:
        bot.infinity_polling()

if __name__ == '__main__':
    run()
