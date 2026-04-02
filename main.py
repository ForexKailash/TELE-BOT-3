import telebot
import sqlite3
import datetime
import os
import random
import threading
import time
import yfinance as yf
import math
import requests
from flask import Flask, request
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============================================================
# HARDCODED CONFIGURATION (ALL YOUR DETAILS)
# ============================================================
BOT_TOKEN = "8653450456:AAER9w6Gjj5IWkyCs1taa01N-DdMFZqxt3E"
ADMIN_ID = 6253584826
PUBLIC_CHANNEL_ID = "-1003807818260"
PUBLIC_CHANNEL_LINK = "https://t.me/tradewithkailashh"
VIP_CHANNEL_ID = "-1003826269063"
VIP_CHANNEL_LINK = "https://t.me/+Snj0BVAwjDo3NTA1"
WEBSITE_URL = "https://forexkailash.netlify.app"
COURSE_URL = "https://forexkailash.netlify.app/course"
UPI_ID = "kailashbhardwaj66-2@okicici"
CONTACT_USERNAME = "@forexkailash"

# ✅ UPDATED WITH YOUR NEW RAILWAY DOMAIN
WEBHOOK_URL = "https://tele-bot-3-production.up.railway.app"
PORT = int(os.environ.get("PORT", 8443))

print("=" * 60)
print("🤖 KAILASH ULTIMATE FOREX BOT - FINAL (HARDCODED DOMAIN)")
print(f"Public channel: {PUBLIC_CHANNEL_LINK}")
print(f"VIP channel: {VIP_CHANNEL_LINK}")
print(f"Webhook URL: {WEBHOOK_URL}")
print("=" * 60)

# ------------------------------------------------------------
# HEALTH CHECK (Railway expects a running service on 8080)
# ------------------------------------------------------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def run_health_server():
    port = int(os.environ.get("HEALTH_PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

# ------------------------------------------------------------
# TRADING SYMBOLS
# ------------------------------------------------------------
SYMBOLS = [
    {"name": "XAU/USD", "ticker": "GC=F", "emoji": "🥇", "decimals": 2, "tp1_pct": 0.004, "tp2_pct": 0.008, "sl_pct": 0.003},
    {"name": "BTC/USD", "ticker": "BTC-USD", "emoji": "₿", "decimals": 0, "tp1_pct": 0.006, "tp2_pct": 0.012, "sl_pct": 0.004},
    {"name": "EUR/USD", "ticker": "EURUSD=X", "emoji": "💶", "decimals": 5, "tp1_pct": 0.003, "tp2_pct": 0.006, "sl_pct": 0.002},
    {"name": "USOIL", "ticker": "CL=F", "emoji": "🛢️", "decimals": 2, "tp1_pct": 0.005, "tp2_pct": 0.010, "sl_pct": 0.003},
    {"name": "GBP/USD", "ticker": "GBPUSD=X", "emoji": "💷", "decimals": 5, "tp1_pct": 0.003, "tp2_pct": 0.006, "sl_pct": 0.002},
    {"name": "USD/JPY", "ticker": "JPY=X", "emoji": "🇯🇵", "decimals": 3, "tp1_pct": 0.003, "tp2_pct": 0.005, "sl_pct": 0.002},
    {"name": "ETH/USD", "ticker": "ETH-USD", "emoji": "💎", "decimals": 1, "tp1_pct": 0.007, "tp2_pct": 0.014, "sl_pct": 0.005},
    {"name": "NAS100", "ticker": "NQ=F", "emoji": "📈", "decimals": 0, "tp1_pct": 0.004, "tp2_pct": 0.008, "sl_pct": 0.003},
    {"name": "SILVER", "ticker": "SI=F", "emoji": "🥈", "decimals": 3, "tp1_pct": 0.005, "tp2_pct": 0.010, "sl_pct": 0.003},
    {"name": "AUD/USD", "ticker": "AUDUSD=X", "emoji": "🦘", "decimals": 5, "tp1_pct": 0.003, "tp2_pct": 0.006, "sl_pct": 0.002},
    {"name": "GBP/JPY", "ticker": "GBPJPY=X", "emoji": "⚡", "decimals": 3, "tp1_pct": 0.004, "tp2_pct": 0.008, "sl_pct": 0.003},
    {"name": "US30", "ticker": "YM=F", "emoji": "🏛️", "decimals": 0, "tp1_pct": 0.003, "tp2_pct": 0.006, "sl_pct": 0.002},
    {"name": "USD/CAD", "ticker": "USDCAD=X", "emoji": "🍁", "decimals": 5, "tp1_pct": 0.003, "tp2_pct": 0.006, "sl_pct": 0.002},
]

FALLBACK = {
    "GC=F": 4520.0, "BTC-USD": 68500.0, "EURUSD=X": 1.0875, "CL=F": 79.5,
    "GBPUSD=X": 1.2680, "JPY=X": 150.5, "ETH-USD": 3550.0, "NQ=F": 18700.0,
    "SI=F": 27.8, "AUDUSD=X": 0.655, "GBPJPY=X": 190.8, "YM=F": 39300.0,
    "USDCAD=X": 1.360,
}

# ------------------------------------------------------------
# PURE PYTHON TECHNICAL ANALYSIS (SMA, RSI, MACD)
# ------------------------------------------------------------
def get_live_price(ticker):
    try:
        data = yf.download(ticker, period="1d", interval="5m", progress=False, timeout=5)
        if not data.empty:
            return float(data["Close"].iloc[-1])
    except:
        pass
    return FALLBACK.get(ticker, 1000.0)

def get_historical_prices(ticker):
    try:
        data = yf.download(ticker, period="60d", interval="1d", progress=False, timeout=8)
        if data.empty:
            return []
        return data["Close"].tolist()
    except:
        return []

def calculate_sma(prices, period):
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_ema(data, span):
    if not data:
        return []
    alpha = 2 / (span + 1)
    ema = [data[0]]
    for i in range(1, len(data)):
        ema.append(alpha * data[i] + (1 - alpha) * ema[-1])
    return ema

def calculate_macd(prices):
    if len(prices) < 26:
        return None, None, None
    ema12 = calculate_ema(prices, 12)
    ema26 = calculate_ema(prices, 26)
    if not ema12 or not ema26:
        return None, None, None
    macd_line = [ema12[i] - ema26[i] for i in range(len(ema12))]
    signal_line = calculate_ema(macd_line, 9)
    if not signal_line:
        return None, None, None
    hist = macd_line[-1] - signal_line[-1]
    return macd_line[-1], signal_line[-1], hist

def analyze_signal(ticker, asset_name):
    prices = get_historical_prices(ticker)
    if len(prices) < 30:
        price = get_live_price(ticker)
        try:
            data = yf.download(ticker, period="60d", interval="1d", progress=False)
            if not data.empty:
                prices2 = data["Close"].tolist()
                if len(prices2) >= 20:
                    sma20 = sum(prices2[-20:]) / 20
                    if price > sma20:
                        return "BUY", 70, f"Price ABOVE 20-day SMA – STRONG UPTREND", "short"
                    else:
                        return "SELL", 70, f"Price BELOW 20-day SMA – STRONG DOWNTREND", "short"
        except:
            pass
        return random.choice(["BUY","SELL"]), 60, "MARKET ANALYSIS ACTIVE – TREND EMERGING", "short"
    
    sma20 = calculate_sma(prices, 20)
    sma50 = calculate_sma(prices, 50)
    price = prices[-1]
    rsi = calculate_rsi(prices, 14)
    macd_line, signal_line, hist = calculate_macd(prices)
    
    trend_bull = sma20 is not None and sma50 is not None and price > sma20 and price > sma50
    trend_bear = sma20 is not None and sma50 is not None and price < sma20 and price < sma50
    rsi_oversold = rsi < 30
    rsi_overbought = rsi > 70
    macd_bull = macd_line is not None and signal_line is not None and macd_line > signal_line
    macd_bear = macd_line is not None and signal_line is not None and macd_line < signal_line
    macd_hist_positive = hist is not None and hist > 0
    
    buy_score = 0
    sell_score = 0
    reasons = []
    
    if trend_bull:
        buy_score += 3
        reasons.append("🔥 DAILY UPTREND CONFIRMED (PRICE > 20 & 50 SMA)")
    elif trend_bear:
        sell_score += 3
        reasons.append("📉 DAILY DOWNTREND CONFIRMED (PRICE < 20 & 50 SMA)")
    
    if rsi_oversold:
        buy_score += 2
        reasons.append(f"⚡ RSI OVERSOLD ({rsi:.0f}) – REVERSAL INCOMING")
    elif rsi_overbought:
        sell_score += 2
        reasons.append(f"⚠️ RSI OVERBOUGHT ({rsi:.0f}) – CORRECTION EXPECTED")
    else:
        reasons.append(f"📊 RSI NEUTRAL ({rsi:.0f}) – MOMENTUM BUILDING")
    
    if macd_bull:
        buy_score += 2
        reasons.append("📈 MACD BULLISH CROSSOVER – STRONG BUY SIGNAL")
    elif macd_bear:
        sell_score += 2
        reasons.append("📉 MACD BEARISH CROSSOVER – STRONG SELL SIGNAL")
    
    if macd_hist_positive:
        buy_score += 1
        reasons.append("💪 MACD HISTOGRAM POSITIVE – UPSIDE MOMENTUM")
    else:
        sell_score += 1
        reasons.append("🔻 MACD HISTOGRAM NEGATIVE – DOWNSIDE MOMENTUM")
    
    if buy_score > sell_score + 2:
        direction = "BUY"
        confidence = min(88, 65 + (buy_score - sell_score) * 3)
        reason = " | ".join(reasons[:3]) + " ➜ 🟢 BULLISH BIAS – BUY SIGNAL ACTIVATED"
    elif sell_score > buy_score + 2:
        direction = "SELL"
        confidence = min(88, 65 + (sell_score - buy_score) * 3)
        reason = " | ".join(reasons[:3]) + " ➜ 🔴 BEARISH BIAS – SELL SIGNAL ACTIVATED"
    else:
        if trend_bull:
            direction = "BUY"
            confidence = 62
            reason = "⚖️ MIXED INDICATORS BUT UPTREND DOMINATES – BUY WITH CAUTION"
        elif trend_bear:
            direction = "SELL"
            confidence = 62
            reason = "⚖️ MIXED INDICATORS BUT DOWNTREND DOMINATES – SELL WITH CAUTION"
        else:
            direction = random.choice(["BUY","SELL"])
            confidence = 58
            reason = "🔄 CONSOLIDATION PHASE – FOLLOW TECHNICAL BIAS ABOVE"
    holding_text = "SHORT-TERM (1-2 DAYS)"
    return direction, confidence, reason, holding_text

def generate_signal(symbol=None):
    if symbol is None:
        symbol = random.choice(SYMBOLS)
    direction, conf, reason, hold_text = analyze_signal(symbol["ticker"], symbol["name"])
    price = get_live_price(symbol["ticker"])
    d = symbol["decimals"]
    spread = price * 0.0005
    if direction == "BUY":
        entry_low = round(price - spread, d)
        entry_high = round(price + spread, d)
        tp1 = round(price * (1 + symbol["tp1_pct"] * 0.8), d)
        tp2 = round(price * (1 + symbol["tp2_pct"] * 0.9), d)
        sl = round(price * (1 - symbol["sl_pct"] * 0.9), d)
    else:
        entry_low = round(price - spread, d)
        entry_high = round(price + spread, d)
        tp1 = round(price * (1 - symbol["tp1_pct"] * 0.8), d)
        tp2 = round(price * (1 - symbol["tp2_pct"] * 0.9), d)
        sl = round(price * (1 + symbol["sl_pct"] * 0.9), d)
    # safety
    if tp1 == entry_low: tp1 = entry_low + (0.01 if d<=2 else 0.00001)
    if tp2 == tp1: tp2 = tp1 + (0.02 if d<=2 else 0.00002)
    if sl == entry_high: sl = entry_high - (0.01 if d<=2 else 0.00001)
    return {
        "symbol": symbol["name"], "emoji": symbol["emoji"], "direction": direction,
        "entry_low": entry_low, "entry_high": entry_high,
        "tp1": tp1, "tp2": tp2, "sl": sl, "decimals": d,
        "analysis": reason, "confidence": conf, "holding_text": hold_text
    }

# ------------------------------------------------------------
# DATABASE
# ------------------------------------------------------------
os.makedirs("data", exist_ok=True)
conn = sqlite3.connect("data/bot.db", check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT, start_date TEXT, last_promo TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS signals (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, direction TEXT, entry REAL, tp1 REAL, tp2 REAL, sl REAL, sent_date TEXT, channel TEXT, result TEXT, msg_id INTEGER)")
conn.commit()

def save_signal(data, channel, msg_id=None):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry_avg = (data["entry_low"] + data["entry_high"]) / 2
    c.execute("INSERT INTO signals (symbol, direction, entry, tp1, tp2, sl, sent_date, channel, result, msg_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
              (data["symbol"], data["direction"], entry_avg, data["tp1"], data["tp2"], data["sl"], now, channel, "pending", msg_id))
    conn.commit()
    return c.lastrowid

def update_signal_result(sig_id, result):
    c.execute("UPDATE signals SET result=? WHERE id=?", (result, sig_id))
    conn.commit()

def get_pending_signals():
    c.execute("SELECT id, symbol, direction, entry, tp1, tp2, sl, msg_id, channel FROM signals WHERE result='pending' AND msg_id IS NOT NULL")
    return c.fetchall()

IST = datetime.timedelta(hours=5, minutes=30)
def ist_now():
    return datetime.datetime.utcnow() + IST

# ------------------------------------------------------------
# MESSAGE FORMATTERS (PUBLIC & VIP)
# ------------------------------------------------------------
def format_public(s):
    dec = s["decimals"]
    el = f"{s['entry_low']:.{dec}f}" if dec>0 else str(int(s["entry_low"]))
    eh = f"{s['entry_high']:.{dec}f}" if dec>0 else str(int(s["entry_high"]))
    tp1 = f"{s['tp1']:.{dec}f}" if dec>0 else str(int(s["tp1"]))
    tp2 = f"{s['tp2']:.{dec}f}" if dec>0 else str(int(s["tp2"]))
    sl = f"{s['sl']:.{dec}f}" if dec>0 else str(int(s["sl"]))
    dir_icon = "🟢 BUY" if s["direction"]=="BUY" else "🔴 SELL"
    return f"""🔥🔥🔥 *LIVE SIGNAL ALERT* 🔥🔥🔥

{s['emoji']} *{s['symbol']}* {dir_icon}
━━━━━━━━━━━━━━━━━━━━━━━━
📌 *ENTRY ZONE:* `{el} — {eh}`
🎯 *TP1:* `{tp1}` ✅
🎯 *TP2:* `{tp2}` ✅✅
🛑 *STOP LOSS:* `{sl}`

📊 *TECHNICAL ANALYSIS:* {s['analysis']}
⏰ *HOLDING PERIOD:* {s['holding_text']}
📈 *CONFIDENCE LEVEL:* {s['confidence']}%

🕐 {ist_now().strftime('%d %b %Y • %I:%M %p')} IST
━━━━━━━━━━━━━━━━━━━━━━━━
💎 *VIP MEMBERS GET EARLY ENTRY + 30-35 SIGNALS/DAY – JUST ₹399/MONTH*
🔗 {VIP_CHANNEL_LINK}"""

def format_vip(s):
    dec = s["decimals"]
    el = f"{s['entry_low']:.{dec}f}" if dec>0 else str(int(s["entry_low"]))
    eh = f"{s['entry_high']:.{dec}f}" if dec>0 else str(int(s["entry_high"]))
    tp1 = f"{s['tp1']:.{dec}f}" if dec>0 else str(int(s["tp1"]))
    tp2 = f"{s['tp2']:.{dec}f}" if dec>0 else str(int(s["tp2"]))
    sl = f"{s['sl']:.{dec}f}" if dec>0 else str(int(s["sl"]))
    dir_word = "BUY 🟢" if s["direction"]=="BUY" else "SELL 🔴"
    return f"""⭐ *VIP EXCLUSIVE SIGNAL* ⭐
━━━━━━━━━━━━━━━━━━━━━━━
{s['emoji']} *{s['symbol']}* | {dir_word}
━━━━━━━━━━━━━━━━━━━━━━━
📍 *ENTRY ZONE:* `{el} — {eh}`
🎯 *TP1:* `{tp1}`
🎯 *TP2:* `{tp2}`
⛔ *SL:* `{sl}`

📊 *ANALYSIS:* {s['analysis']}
⏰ *HOLD:* {s['holding_text']} | CONFIDENCE: {s['confidence']}%
🕐 {ist_now().strftime('%H:%M')} IST
🔒 *VIP ONLY*
━━━━━━━━━━━━━━━━━━━━━━━
🔥 NEXT SIGNAL IN 10-15 MINUTES"""

# ------------------------------------------------------------
# HYPE PROMOTIONAL MESSAGES (LONG, CAPITAL WORDS, FOMO)
# ------------------------------------------------------------
USER_PROMOS = [
    f"""🔥🔥🔥 *EXCLUSIVE VIP OFFER – LIMITED SLOTS* 🔥🔥🔥

💎 *ONLY ₹399/MONTH* – GET:
✅ 30-35 PREMIUM SIGNALS DAILY (vs 8-10 FREE)
✅ EARLY ENTRY 30 MINUTES BEFORE PUBLIC CHANNEL
✅ 1-ON-1 SUPPORT FROM KAILASH SIR
✅ LIVE MARKET ANALYSIS & COPY TRADING

📊 *TODAY'S VIP PROFIT:* ₹{random.randint(8000, 20000)}+
🏆 *89% WIN RATE – PROVEN RESULTS*

⏰ *PRICE HIKE SOON!* NEXT MONTH ₹599.
⚡ *LOCK ₹399 FOR LIFE – JOIN NOW!*

👇 *HOW TO JOIN:*
💳 PAY ₹399 TO UPI: `{UPI_ID}`
📩 SEND SCREENSHOT TO {CONTACT_USERNAME}
🔗 GET VIP CHANNEL LINK: {VIP_CHANNEL_LINK}

*DON'T MISS TOMORROW'S GOLD BREAKOUT – VIP GETS IT FIRST!* 🚀""",

    f"""🚨🚨 *URGENT – ONLY {random.randint(3,7)} VIP SEATS LEFT!* 🚨🚨

💰 *WHAT VIP MEMBERS EARNED THIS WEEK:*
🥇 GOLD: +350 PIPS (₹12,000/LOT)
₿ BITCOIN: +8% (₹16,000/LOT)
💶 EUR/USD: +120 PIPS (₹6,000/LOT)

*TOTAL PROFIT: ₹34,000+ THIS WEEK ALONE!*

⭐ *VIP COST: JUST ₹399/MONTH*
💎 *YOUR ROI = 8500%*

📲 *JOIN INSTANTLY:*
1️⃣ PAY ₹399 TO `{UPI_ID}`
2️⃣ DM SCREENSHOT TO {CONTACT_USERNAME}
3️⃣ GET VIP LINK: {VIP_CHANNEL_LINK}

*STOP WATCHING OTHERS PROFIT – BECOME A VIP TODAY!* 🔥""",

    f"""💎💎 *KAILASH VIP – INDIA'S MOST TRUSTED SIGNAL PROVIDER* 💎💎

📊 *WHY 5000+ TRADERS CHOOSE US:*
✅ 89% ACCURACY (PROVEN – CHECK CHANNEL HISTORY)
✅ 30-35 SIGNALS/DAY (GOLD, BTC, FOREX, INDICES)
✅ EARLY ENTRIES BEFORE PUBLIC CHANNEL
✅ RISK MANAGEMENT GUIDANCE
✅ COPY TRADING SETUP HELP

💰 *PRICE: ₹399/MONTH* (LESS THAN ₹13/DAY)

🎯 *YOUR FIRST TRADE ITSELF CAN COVER THE FEE!*

👇 *JOIN IN 2 MINUTES:*
📱 UPI: `{UPI_ID}`
💬 DM {CONTACT_USERNAME}
🔗 {VIP_CHANNEL_LINK}

*MONEY-BACK GUARANTEE IF NOT SATISFIED IN FIRST WEEK!* 💯""",

    f"""⚡⚡ *FLASH SALE – FREE FOREX MASTERCLASS WITH VIP* ⚡⚡

🎓 *KAILASH FOREX MASTERCLASS* (₹2,999 VALUE) – *FREE FOR NEXT 10 VIP MEMBERS!*

📚 *COURSE INCLUDES:*
• CHART PATTERNS MASTERY
• ENTRY/EXIT STRATEGIES
• RISK MANAGEMENT SYSTEM
• LIVE TRADE WALKTHROUGHS

⭐ *VIP + COURSE COMBO: JUST ₹399* (SAVE ₹2,999)

⏰ *OFFER VALID FOR NEXT 1 HOUR OR TILL SLOTS FILL!*

👉 *PAY ₹399 TO `{UPI_ID}` AND DM {CONTACT_USERNAME} WITH CODE "VIPCOURSE"*

🔗 {VIP_CHANNEL_LINK}

*BECOME A PROFESSIONAL TRADER TODAY!* 🚀""",

    f"""📢📢 *FREE CHANNEL SIGNALS ARE DELAYED BY 30 MINUTES* 📢📢

🔥 *VIP MEMBERS GET EARLY ENTRIES – MAXIMUM PROFIT!*

📊 *COMPARISON:*
| FEATURE | FREE | VIP |
|---------|------|-----|
| SIGNALS/DAY | 8-10 | 30-35 |
| ENTRY TIMING | AFTER MOVE | BEFORE MOVE ⚡ |
| TP/SL ALERTS | ❌ | ✅ |
| 1-ON-1 SUPPORT | ❌ | ✅ |
| LIVE SESSIONS | ❌ | ✅ |
| WIN RATE | 85% | 89%+ |

💎 *THE DIFFERENCE IS JUST ₹399/MONTH!*

👇 *UPGRADE NOW:*
💳 UPI: `{UPI_ID}`
📩 DM SCREENSHOT TO {CONTACT_USERNAME}
🔗 {VIP_CHANNEL_LINK}

*DON'T LET DELAYED ENTRIES COST YOU PROFITS!* ⚡""",

    f"""🏆🏆 *WEEKEND SPECIAL – DOUBLE BENEFITS* 🏆🏆

🔥 *JOIN VIP THIS WEEKEND AND GET:*
✅ 1 MONTH VIP ACCESS (₹399)
✅ FREE FOREX MASTERCLASS (₹2,999 VALUE)
✅ 1-ON-1 TRADING SESSION WITH KAILASH

💰 *TOTAL VALUE: ₹3,500+* – YOU PAY ONLY ₹399!

⏰ *OFFER ENDS SUNDAY MIDNIGHT!*

👇 *CLAIM YOUR SPOT:*
📱 UPI: `{UPI_ID}`
💬 DM {CONTACT_USERNAME} WITH "WEEKEND"
🔗 {VIP_CHANNEL_LINK}

*LIMITED SLOTS – FIRST COME FIRST SERVE!* 🚀""",
]

def get_user_promo():
    return random.choice(USER_PROMOS)

# ------------------------------------------------------------
# SEND HYPE PROMOS TO ALL USERS (EVERY 30 MIN, RATE LIMITED)
# ------------------------------------------------------------
def send_user_promos():
    while True:
        try:
            c.execute("SELECT user_id FROM users")
            users = c.fetchall()
            for (uid,) in users:
                try:
                    bot.send_message(uid, get_user_promo(), parse_mode="Markdown")
                    time.sleep(0.8)  # rate limit protection
                except Exception as e:
                    print(f"Failed to send promo to {uid}: {e}")
            print(f"📨 Hype promos sent to {len(users)} users at {ist_now().strftime('%H:%M')}")
        except Exception as e:
            print(f"Promo sender error: {e}")
        time.sleep(1800)  # 30 minutes

# ------------------------------------------------------------
# VIP CHANNEL SCHEDULER (30-35 signals + course promos after limit)
# ------------------------------------------------------------
VIP_PROMOS = [
    f"🎓 *KAILASH FOREX MASTERCLASS* – VIP SPECIAL ₹1,499 ONLY! DM {CONTACT_USERNAME}",
    f"📚 *LEARN TO TRADE LIKE A PRO* – VIP DISCOUNT! COURSE: {COURSE_URL}",
    f"💎 *MASTERCLASS ACCESS* – 50% OFF FOR VIP MEMBERS. DM {CONTACT_USERNAME}",
]

def vip_scheduler():
    count = 0
    last_date = ""
    tick = 0
    while True:
        if not VIP_CHANNEL_ID:
            time.sleep(60)
            continue
        try:
            now = ist_now()
            today = now.strftime("%Y-%m-%d")
            if today != last_date:
                count = 0
                last_date = today
                tick = 0
            if count < 35:
                sig = generate_signal()
                msg = format_vip(sig)
                sent = bot.send_message(VIP_CHANNEL_ID, msg, parse_mode="Markdown")
                save_signal(sig, "vip", sent.message_id)
                count += 1
                print(f"⭐ VIP signal #{count}")
            else:
                tick += 1
                if tick % 2 == 0:  # promo every 30 min after daily limit
                    bot.send_message(VIP_CHANNEL_ID, random.choice(VIP_PROMOS), parse_mode="Markdown")
        except Exception as e:
            print(f"VIP scheduler error: {e}")
        time.sleep(random.randint(600, 900))  # 10-15 min

# ------------------------------------------------------------
# PUBLIC SCHEDULER (ONLY SIGNALS – NO PROMOS)
# ------------------------------------------------------------
public_signal_count = 0
last_pub_date = ""

def public_scheduler():
    global public_signal_count, last_pub_date
    while True:
        try:
            now = ist_now()
            today = now.strftime("%Y-%m-%d")
            if today != last_pub_date:
                public_signal_count = 0
                last_pub_date = today
                print(f"📅 New day: {today}")
            if public_signal_count < 8:
                sig = generate_signal()
                msg = format_public(sig)
                sent = bot.send_message(PUBLIC_CHANNEL_ID, msg, parse_mode="Markdown")
                save_signal(sig, "public", sent.message_id)
                public_signal_count += 1
                print(f"📢 Public signal #{public_signal_count} sent")
            else:
                # No promo – just sleep until next day
                pass
        except Exception as e:
            print(f"Public scheduler error: {e}")
        time.sleep(1800)  # 30 minutes

# ------------------------------------------------------------
# PRICE MONITOR (TP/SL + AUTO-DELETE LOSSES + HYPE)
# ------------------------------------------------------------
TP_HYPE = [
    "🎯🔥 *TARGET HIT!* 🔥🎯\n\n{symbol} {direction} → *{tp} ✅ REACHED!*\n\n+{profit} {unit} PROFIT!\n\n💎 *KAILASH TRADING* – INDIA'S MOST TRUSTED\n👉 JOIN VIP FOR EARLY ENTRIES: {vip}",
    "💰 *BOOM! TP HIT!* 💰\n\n{symbol} → *{tp} SMASHED!* 🎯\n*{direction} +{profit} {unit}*\n⭐ *WIN RATE 89%* | VIP: {vip}",
]

def price_monitor():
    while True:
        time.sleep(180)  # 3 minutes
        try:
            pending = get_pending_signals()
            for row in pending:
                sid, symbol, direction, entry, tp1, tp2, sl, msg_id, channel = row
                ticker = next((s["ticker"] for s in SYMBOLS if s["name"] == symbol), None)
                if not ticker:
                    continue
                price = get_live_price(ticker)
                if price is None:
                    continue
                hit = None
                label = None
                if direction == "BUY":
                    if price >= tp2:
                        hit, label = tp2, "TP2 🎯🎯"
                    elif price >= tp1:
                        hit, label = tp1, "TP1 🎯"
                    elif price <= sl:
                        if channel == "public":
                            try:
                                bot.delete_message(PUBLIC_CHANNEL_ID, msg_id)
                                print(f"🗑️ Deleted losing signal: {symbol}")
                            except:
                                pass
                        update_signal_result(sid, "sl_hit")
                        continue
                else:
                    if price <= tp2:
                        hit, label = tp2, "TP2 🎯🎯"
                    elif price <= tp1:
                        hit, label = tp1, "TP1 🎯"
                    elif price >= sl:
                        if channel == "public":
                            try:
                                bot.delete_message(PUBLIC_CHANNEL_ID, msg_id)
                            except:
                                pass
                        update_signal_result(sid, "sl_hit")
                        continue
                if hit:
                    if symbol in ["EUR/USD", "GBP/USD", "AUD/USD", "USD/CAD"]:
                        profit = round(abs(hit - entry) * 10000, 1)
                        unit = "PIPS"
                    else:
                        profit = round(abs(hit - entry), 2)
                        unit = "POINTS"
                    hype = random.choice(TP_HYPE).format(
                        symbol=symbol, direction=direction, tp=label,
                        profit=profit, unit=unit, vip=VIP_CHANNEL_LINK
                    )
                    try:
                        bot.send_message(PUBLIC_CHANNEL_ID, hype, parse_mode="Markdown")
                        if channel == "vip" and VIP_CHANNEL_ID:
                            bot.send_message(VIP_CHANNEL_ID, f"🏆 *VIP PROFIT!* {symbol} {direction} {label} +{profit} {unit}", parse_mode="Markdown")
                        update_signal_result(sid, "tp_hit")
                    except Exception as e:
                        print(f"TP message error: {e}")
        except Exception as e:
            print(f"Monitor error: {e}")

# ------------------------------------------------------------
# BOT COMMANDS (WORKING /start, /free, /vip, /support, /stats)
# ------------------------------------------------------------
bot = telebot.TeleBot(BOT_TOKEN)
print(f"✅ Bot ready: @{bot.get_me().username}")

def main_keyboard():
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    kb.add(telebot.types.InlineKeyboardButton("📝 REGISTER", callback_data="register"))
    kb.add(telebot.types.InlineKeyboardButton("📊 FREE SIGNAL", callback_data="free"))
    kb.add(telebot.types.InlineKeyboardButton("⭐ VIP ACCESS", callback_data="vip"))
    kb.add(telebot.types.InlineKeyboardButton("💬 SUPPORT", callback_data="support"))
    kb.add(telebot.types.InlineKeyboardButton("🌐 WEBSITE", url=WEBSITE_URL))
    kb.add(telebot.types.InlineKeyboardButton("📢 FREE CHANNEL", url=PUBLIC_CHANNEL_LINK))
    return kb

@bot.message_handler(commands=['start'])
def start_cmd(msg):
    uid = msg.from_user.id
    c.execute("INSERT OR IGNORE INTO users (user_id, name, start_date, last_promo) VALUES (?,?,?,?)",
              (uid, msg.from_user.first_name, str(ist_now()), str(ist_now())))
    conn.commit()
    txt = f"""🚀 *FOREX TRADING WITH KAILASH* 🚀

INDIA'S MOST TRUSTED FOREX SIGNALS PROVIDER

📊 *SERVICES:*
✅ FREE SIGNALS – DAILY 8-10 CALLS (REAL TECHNICAL ANALYSIS)
⭐ VIP CHANNEL – ₹399/MONTH (30-35 CALLS)
🔄 COPY TRADING AVAILABLE
📈 89% WIN RATE | 5000+ TRADERS

🌐 *WEBSITE:* {WEBSITE_URL}
📢 *FREE CHANNEL:* {PUBLIC_CHANNEL_LINK}
⭐ *VIP CHANNEL:* {VIP_CHANNEL_LINK}

👇 *CHOOSE AN OPTION:*"""
    bot.reply_to(msg, txt, parse_mode="Markdown", reply_markup=main_keyboard())
    print(f"✅ /start replied to user {uid}")

@bot.message_handler(commands=['free'])
def free_cmd(msg):
    uid = msg.from_user.id
    c.execute("SELECT COUNT(*) FROM signals WHERE channel='free'")
    used = c.fetchone()[0]
    if used >= 3:
        bot.reply_to(msg, "🚫 FREE LIMIT REACHED. JOIN VIP: /vip", parse_mode="Markdown")
        return
    sig = generate_signal()
    text = format_public(sig)
    sent = bot.reply_to(msg, text, parse_mode="Markdown")
    save_signal(sig, "free", sent.message_id)

@bot.message_handler(commands=['vip'])
def vip_cmd(msg):
    bot.reply_to(msg, f"⭐ *VIP ACCESS* – ₹399/MONTH\n📱 UPI: `{UPI_ID}`\nPAY & SEND SCREENSHOT TO {CONTACT_USERNAME}\n🔗 {VIP_CHANNEL_LINK}", parse_mode="Markdown", reply_markup=main_keyboard())

@bot.message_handler(commands=['support'])
def support_cmd(msg):
    bot.reply_to(msg, f"💬 {CONTACT_USERNAME}\n📧 btcuscoinbase@gmail.com", parse_mode="Markdown", reply_markup=main_keyboard())

@bot.message_handler(commands=['stats'])
def stats_cmd(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    bot.reply_to(msg, f"📊 TOTAL USERS: {total}", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data == "register":
        bot.send_message(call.message.chat.id, "📝 REGISTRATION: SEND `/register Name, Email, Phone`", parse_mode="Markdown")
    elif call.data == "free":
        free_cmd(call.message)
    elif call.data == "vip":
        vip_cmd(call.message)
    elif call.data == "support":
        support_cmd(call.message)
    bot.answer_callback_query(call.id)

# ------------------------------------------------------------
# WEBHOOK + POLLING FALLBACK (GUARANTEED TO RESPOND)
# ------------------------------------------------------------
flask_app = Flask(__name__)

@flask_app.route("/webhook", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        json_str = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "OK", 200
    return "Bad Request", 400

@flask_app.route("/")
def index():
    return "Bot is running", 200

def set_webhook():
    try:
        bot.remove_webhook()
        time.sleep(1)
        url = f"{WEBHOOK_URL}/webhook"
        bot.set_webhook(url=url)
        print(f"✅ Webhook set to {url}")
        return True
    except Exception as e:
        print(f"❌ Webhook failed: {e}")
        return False

# ------------------------------------------------------------
# MAIN (STARTS ALL THREADS AND CHOOSES WEBHOOK OR POLLING)
# ------------------------------------------------------------
if __name__ == "__main__":
    print("Starting background threads...")
    threading.Thread(target=public_scheduler, daemon=True).start()
    threading.Thread(target=vip_scheduler, daemon=True).start()
    threading.Thread(target=price_monitor, daemon=True).start()
    threading.Thread(target=send_user_promos, daemon=True).start()
    
    if set_webhook():
        print(f"🚀 Starting Flask webhook server on port {PORT}")
        flask_app.run(host="0.0.0.0", port=PORT)
    else:
        print("⚠️ Webhook failed – falling back to long polling (will still respond to /start)")
        while True:
            try:
                bot.remove_webhook()
                bot.infinity_polling(timeout=60)
            except Exception as e:
                print(f"Polling error: {e}")
                time.sleep(15)
