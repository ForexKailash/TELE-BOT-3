import telebot
import sqlite3
import datetime
import os
import random
import threading
import time
import yfinance as yf
import numpy as np
import requests
from flask import Flask, request
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============================================================
# HARDCODED CONFIGURATION
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
WEBHOOK_URL = "https://tele-bot-2-production.up.railway.app"   # CHANGE THIS
PORT = int(os.environ.get("PORT", 8443))

print("=" * 60)
print("🤖 KAILASH FOREX SIGNAL BOT - NO PANDAS VERSION")
print(f"Admin: {CONTACT_USERNAME}")
print(f"Public: {PUBLIC_CHANNEL_LINK}")
print(f"VIP: {VIP_CHANNEL_LINK}")
print(f"Webhook: {WEBHOOK_URL}")
print("=" * 60)

# ------------------------------------------------------------
# HEALTH CHECK (Railway)
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
# SYMBOLS & FALLBACK PRICES
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
# REAL TECHNICAL ANALYSIS (No pandas, pure numpy)
# ------------------------------------------------------------
def get_live_price(ticker):
    try:
        data = yf.download(ticker, period="1d", interval="5m", progress=False, timeout=5)
        if not data.empty:
            return float(data["Close"].iloc[-1])
    except:
        pass
    return FALLBACK.get(ticker, 1000.0)

def get_historical_data(ticker, period="60d"):
    """Return numpy array of close prices and dates"""
    try:
        data = yf.download(ticker, period=period, interval="1d", progress=False, timeout=8)
        if data.empty:
            return None, None
        closes = data['Close'].values
        return closes, data.index
    except:
        return None, None

def calculate_sma(prices, period):
    if len(prices) < period:
        return None
    return np.mean(prices[-period:])

def calculate_rsi(prices, period=14):
    if len(prices) < period+1:
        return 50
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices):
    """Return (macd_line, signal_line, histogram) as tuples of last values"""
    if len(prices) < 26:
        return None, None, None
    # Exponential weighting
    def ema(data, span):
        alpha = 2 / (span + 1)
        result = np.zeros_like(data)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i-1]
        return result
    ema12 = ema(prices, 12)
    ema26 = ema(prices, 26)
    macd_line = ema12 - ema26
    signal_line = ema(macd_line, 9)
    hist = macd_line - signal_line
    return macd_line[-1], signal_line[-1], hist[-1]

def analyze_signal(ticker, asset_name):
    closes, _ = get_historical_data(ticker)
    if closes is None or len(closes) < 30:
        price = get_live_price(ticker)
        try:
            # quick SMA20 using yfinance (still without pandas)
            data = yf.download(ticker, period="60d", interval="1d", progress=False)
            if not data.empty:
                closes2 = data['Close'].values
                sma20 = np.mean(closes2[-20:]) if len(closes2) >= 20 else price
                if price > sma20:
                    return "BUY", 60, f"Price above 20-day SMA (fallback)", "short"
                else:
                    return "SELL", 60, f"Price below 20-day SMA (fallback)", "short"
        except:
            pass
        return random.choice(["BUY","SELL"]), 55, "Limited data, using safe bias", "short"
    
    # SMA20 and SMA50
    sma20 = calculate_sma(closes, 20)
    sma50 = calculate_sma(closes, 50)
    price = closes[-1]
    rsi = calculate_rsi(closes, 14)
    macd_line, signal_line, hist = calculate_macd(closes)
    
    # Trend detection
    trend_bull = sma20 is not None and sma50 is not None and price > sma20 and price > sma50
    trend_bear = sma20 is not None and sma50 is not None and price < sma20 and price < sma50
    
    # RSI conditions
    rsi_oversold = rsi < 30
    rsi_overbought = rsi > 70
    
    # MACD
    macd_bull = macd_line is not None and signal_line is not None and macd_line > signal_line
    macd_bear = macd_line is not None and signal_line is not None and macd_line < signal_line
    macd_hist_positive = hist is not None and hist > 0
    
    # Score based on multiple factors
    buy_score = 0
    sell_score = 0
    reasons = []
    
    if trend_bull:
        buy_score += 3
        reasons.append("Daily uptrend (price > 20 & 50 SMA)")
    elif trend_bear:
        sell_score += 3
        reasons.append("Daily downtrend (price < 20 & 50 SMA)")
    
    if rsi_oversold:
        buy_score += 2
        reasons.append(f"RSI oversold ({rsi:.0f}) → potential reversal up")
    elif rsi_overbought:
        sell_score += 2
        reasons.append(f"RSI overbought ({rsi:.0f}) → potential reversal down")
    else:
        reasons.append(f"RSI neutral ({rsi:.0f})")
    
    if macd_bull:
        buy_score += 2
        reasons.append("MACD bullish (above signal line)")
    elif macd_bear:
        sell_score += 2
        reasons.append("MACD bearish (below signal line)")
    
    if macd_hist_positive:
        buy_score += 1
        reasons.append("MACD histogram positive (momentum up)")
    else:
        sell_score += 1
        reasons.append("MACD histogram negative (momentum down)")
    
    if buy_score > sell_score + 2:
        direction = "BUY"
        confidence = min(85, 60 + (buy_score - sell_score) * 3)
        reason = " | ".join(reasons[:3]) + ". Bullish bias."
    elif sell_score > buy_score + 2:
        direction = "SELL"
        confidence = min(85, 60 + (sell_score - buy_score) * 3)
        reason = " | ".join(reasons[:3]) + ". Bearish bias."
    else:
        if trend_bull:
            direction = "BUY"
            confidence = 60
            reason = "Neutral indicators, but uptrend favors buying."
        elif trend_bear:
            direction = "SELL"
            confidence = 60
            reason = "Neutral indicators, but downtrend favors selling."
        else:
            direction = random.choice(["BUY", "SELL"])
            confidence = 55
            reason = "Mixed signals, using conservative bias."
    holding_text = "Short-term (1-2 days)"
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
# DATABASE (unchanged)
# ------------------------------------------------------------
os.makedirs("data", exist_ok=True)
conn = sqlite3.connect("data/bot.db", check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT, start_date TEXT)")
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
# MESSAGE FORMATTERS (same as before)
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
📌 *Entry:* `{el} — {eh}`
🎯 *TP1:* `{tp1}` ✅
🎯 *TP2:* `{tp2}` ✅✅
🛑 *SL:* `{sl}`

📊 *Analysis:* {s['analysis']}
⏰ *Holding:* {s['holding_text']}
📈 *Confidence:* {s['confidence']}%

🕐 {ist_now().strftime('%d %b %Y • %I:%M %p')} IST
━━━━━━━━━━━━━━━━━━━━━━━━
💎 VIP gets early entry + 30-35 signals/day – ₹399/month
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
📍 *Entry Zone:* `{el} — {eh}`
🎯 *TP1:* `{tp1}`
🎯 *TP2:* `{tp2}`
⛔ *SL:* `{sl}`

📊 *Analysis:* {s['analysis']}
⏰ *Hold:* {s['holding_text']} | Conf: {s['confidence']}%
🕐 {ist_now().strftime('%H:%M')} IST
🔒 VIP Only
━━━━━━━━━━━━━━━━━━━━━━━
🔥 Next signal in 10-15 mins"""

# ------------------------------------------------------------
# PROMOTIONAL MESSAGES (unchanged)
# ------------------------------------------------------------
PUBLIC_PROMOS = [
    f"💎 *FREE SIGNALS DAILY!* Join free channel: {PUBLIC_CHANNEL_LINK}\n⭐ Upgrade to VIP: {VIP_CHANNEL_LINK}",
    f"🚀 *VIP members made ₹{random.randint(5000,15000)} today!* Join now: {VIP_CHANNEL_LINK}",
    f"⚠️ *Limited VIP slots* – only {random.randint(3,7)} left! {VIP_CHANNEL_LINK}",
    f"📚 *FREE FOREX COURSE* for VIP members! DM {CONTACT_USERNAME}",
    f"🏆 *89% win rate* – join VIP: {VIP_CHANNEL_LINK}",
    f"💰 *₹399/month* = 30-35 premium signals. ROI 3600%! {VIP_CHANNEL_LINK}",
    f"🎯 *Early entry* before public – only VIP. Join: {VIP_CHANNEL_LINK}",
    f"📊 *Free vs VIP* – VIP gets signals 30 min earlier! {VIP_CHANNEL_LINK}",
    f"⏰ *Price hike soon* – lock ₹399 now: {VIP_CHANNEL_LINK}",
    f"💬 *DM for payment* – UPI: {UPI_ID} – join VIP today!",
]

VIP_PROMOS = [
    f"🎓 *KAILASH FOREX MASTERCLASS* - VIP Special ₹1,499 only! DM {CONTACT_USERNAME}",
    f"📚 *Learn to trade like a pro* - VIP discount! Course: {COURSE_URL}",
    f"💎 *Masterclass Access* - 50% OFF for VIP members. DM {CONTACT_USERNAME}",
]

USER_PROMOS = [
    f"📢 *Join our FREE channel* for daily signals: {PUBLIC_CHANNEL_LINK}\n⭐ *Upgrade to VIP* for early entries: {VIP_CHANNEL_LINK}\n💬 {CONTACT_USERNAME}",
    f"🚀 *Want consistent profits?* VIP signals with 89% accuracy – ₹399/month! {VIP_CHANNEL_LINK}",
    f"💰 *Today's VIP profit* – ₹{random.randint(5000,12000)}. Don't miss out: {VIP_CHANNEL_LINK}",
]

def get_promo(typ):
    if typ == "public":
        return random.choice(PUBLIC_PROMOS)
    elif typ == "vip":
        return random.choice(VIP_PROMOS)
    else:
        return random.choice(USER_PROMOS)

# ------------------------------------------------------------
# BOT INIT
# ------------------------------------------------------------
bot = telebot.TeleBot(BOT_TOKEN)
print(f"✅ Bot ready: @{bot.get_me().username}")

# ------------------------------------------------------------
# BACKGROUND THREADS (schedulers, monitor, user promos)
# ------------------------------------------------------------
def send_user_promos():
    while True:
        try:
            c.execute("SELECT user_id FROM users")
            users = c.fetchall()
            for (uid,) in users:
                try:
                    bot.send_message(uid, get_promo("user"), parse_mode="Markdown")
                    time.sleep(0.5)
                except:
                    pass
            print(f"📨 User promos sent to {len(users)} users")
        except Exception as e:
            print(f"User promo error: {e}")
        time.sleep(1800)

def public_scheduler():
    count = 0
    last_date = ""
    tick = 0
    while True:
        try:
            now = ist_now()
            today = now.strftime("%Y-%m-%d")
            if today != last_date:
                count = 0
                last_date = today
                tick = 0
            tick += 1
            if tick % 2 == 0:  # signal
                if count < 8:
                    sig = generate_signal()
                    msg = format_public(sig)
                    sent = bot.send_message(PUBLIC_CHANNEL_ID, msg, parse_mode="Markdown")
                    save_signal(sig, "public", sent.message_id)
                    count += 1
                    print(f"📢 Public signal #{count}")
                else:
                    bot.send_message(PUBLIC_CHANNEL_ID, get_promo("public"), parse_mode="Markdown")
            else:
                bot.send_message(PUBLIC_CHANNEL_ID, get_promo("public"), parse_mode="Markdown")
        except Exception as e:
            print(f"Public error: {e}")
        time.sleep(1800)

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
                if tick % 2 == 0:
                    bot.send_message(VIP_CHANNEL_ID, get_promo("vip"), parse_mode="Markdown")
        except Exception as e:
            print(f"VIP error: {e}")
        time.sleep(random.randint(600, 900))

def price_monitor():
    while True:
        time.sleep(180)
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
                        unit = "pips"
                    else:
                        profit = round(abs(hit - entry), 2)
                        unit = "points"
                    hype = random.choice([
                        f"🎯🔥 *TARGET HIT!* 🔥🎯\n\n{symbol} {direction} → *{label} ✅ REACHED!*\n\n+{profit} {unit} profit!\n\n💎 *KAILASH TRADING*\n👉 Join VIP: {VIP_CHANNEL_LINK}",
                        f"💰 *BOOM! TP HIT!* 💰\n\n{symbol} → *{label} SMASHED!* 🎯\n*{direction} +{profit} {unit}*\n⭐ VIP: {VIP_CHANNEL_LINK}"
                    ])
                    try:
                        bot.send_message(PUBLIC_CHANNEL_ID, hype, parse_mode="Markdown")
                        if channel == "vip" and VIP_CHANNEL_ID:
                            bot.send_message(VIP_CHANNEL_ID, f"🏆 *VIP PROFIT!* {symbol} {direction} {label} +{profit} {unit}", parse_mode="Markdown")
                        update_signal_result(sid, "tp_hit")
                    except:
                        pass
        except Exception as e:
            print(f"Monitor error: {e}")

# ------------------------------------------------------------
# BOT COMMANDS
# ------------------------------------------------------------
def main_keyboard():
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    kb.add(telebot.types.InlineKeyboardButton("📝 Register", callback_data="register"))
    kb.add(telebot.types.InlineKeyboardButton("📊 Free Signal", callback_data="free"))
    kb.add(telebot.types.InlineKeyboardButton("⭐ VIP Access", callback_data="vip"))
    kb.add(telebot.types.InlineKeyboardButton("💬 Support", callback_data="support"))
    kb.add(telebot.types.InlineKeyboardButton("🌐 Website", url=WEBSITE_URL))
    kb.add(telebot.types.InlineKeyboardButton("📢 Free Channel", url=PUBLIC_CHANNEL_LINK))
    return kb

@bot.message_handler(commands=['start'])
def start_cmd(msg):
    uid = msg.from_user.id
    c.execute("INSERT OR IGNORE INTO users (user_id, name, start_date) VALUES (?,?,?)",
              (uid, msg.from_user.first_name, str(ist_now())))
    conn.commit()
    txt = f"""🚀 *Forex Trading With Kailash* 🚀

India's Most Trusted Forex Signals Provider

📊 *Services:*
✅ FREE Signals - Daily 8-10 calls (Real Technical Analysis)
⭐ VIP Channel - ₹399/month (30-35 calls)
🔄 Copy Trading Available
📈 89% Win Rate | 5000+ Traders

🌐 *Website:* {WEBSITE_URL}
📢 *Free Channel:* {PUBLIC_CHANNEL_LINK}
⭐ *VIP Channel:* {VIP_CHANNEL_LINK}

👇 *Choose an option:*"""
    bot.reply_to(msg, txt, parse_mode="Markdown", reply_markup=main_keyboard())

@bot.message_handler(commands=['free'])
def free_cmd(msg):
    uid = msg.from_user.id
    c.execute("SELECT COUNT(*) FROM signals WHERE channel='free'")
    used = c.fetchone()[0]
    if used >= 3:
        bot.reply_to(msg, "🚫 Free limit reached. Join VIP: /vip", parse_mode="Markdown")
        return
    sig = generate_signal()
    text = format_public(sig)
    sent = bot.reply_to(msg, text, parse_mode="Markdown")
    save_signal(sig, "free", sent.message_id)

@bot.message_handler(commands=['vip'])
def vip_cmd(msg):
    bot.reply_to(msg, f"⭐ *VIP ACCESS* - ₹399/month\n📱 UPI: `{UPI_ID}`\nPay & send screenshot to {CONTACT_USERNAME}\n🔗 {VIP_CHANNEL_LINK}", parse_mode="Markdown", reply_markup=main_keyboard())

@bot.message_handler(commands=['support'])
def support_cmd(msg):
    bot.reply_to(msg, f"💬 {CONTACT_USERNAME}\n📧 btcuscoinbase@gmail.com", parse_mode="Markdown", reply_markup=main_keyboard())

@bot.message_handler(commands=['stats'])
def stats_cmd(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    bot.reply_to(msg, f"📊 Total users: {total}", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data == "register":
        bot.send_message(call.message.chat.id, "📝 Registration: Send `/register Name, Email, Phone`", parse_mode="Markdown")
    elif call.data == "free":
        free_cmd(call.message)
    elif call.data == "vip":
        vip_cmd(call.message)
    elif call.data == "support":
        support_cmd(call.message)
    bot.answer_callback_query(call.id)

# ------------------------------------------------------------
# WEBHOOK SETUP
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
# MAIN
# ------------------------------------------------------------
if __name__ == "__main__":
    print("Starting background threads...")
    threading.Thread(target=public_scheduler, daemon=True).start()
    threading.Thread(target=vip_scheduler, daemon=True).start()
    threading.Thread(target=price_monitor, daemon=True).start()
    threading.Thread(target=send_user_promos, daemon=True).start()
    if set_webhook():
        flask_app.run(host="0.0.0.0", port=PORT)
    else:
        print("Falling back to polling")
        while True:
            try:
                bot.remove_webhook()
                bot.infinity_polling(timeout=60)
            except Exception as e:
                print(f"Polling error: {e}")
                time.sleep(15)
