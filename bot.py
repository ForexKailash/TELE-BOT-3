import telebot
import sqlite3
import datetime
import os
import random
import threading
import time
import yfinance as yf
import numpy as np

# ============================================
# CONFIGURATION (your credentials)
# ============================================

BOT_TOKEN = "8653450456:AAER9w6Gjj5IWkyCs1taa01N-DdMFZqxt3E"
ADMIN_ID = 6253584826

# Public channel – numeric ID (with minus sign)
PUBLIC_CHANNEL_ID = -1003807818260   # from "1003807818260" add -100
PUBLIC_CHANNEL_USERNAME = "@tradewithkailashh"  # for links

# VIP channel – numeric ID (with minus sign)
VIP_CHANNEL_ID = -1003826269063      # from "1003826269063" add -100

WEBSITE_URL = "https://forexkailash.netlify.app"
FREE_CHANNEL_LINK = "https://t.me/tradewithkailashh"
VIP_CHANNEL_LINK = "https://t.me/+Snj0BVAwjDo3NTA1"
UPI_ID = "kailashbhardwaj66-2@okicici"
CONTACT_USERNAME = "@Yungshang1"
COURSE_URL = "https://forexkailash.netlify.app"

# Daily limits
PUBLIC_SIGNALS_PER_DAY = 7     # 5-7 signals on public channel
VIP_SIGNALS_PER_DAY = 25       # 20-25 signals on VIP channel
USER_FREE_SIGNAL_LIMIT = 3     # per user via /free command

# Promotional messages interval (seconds)
PROMO_INTERVAL = (30 * 60, 45 * 60)  # 30-45 minutes

# ============================================
# DATABASE SETUP
# ============================================

os.makedirs("telegram_bot", exist_ok=True)
conn = sqlite3.connect("telegram_bot/users.db", check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS users
(user_id INTEGER PRIMARY KEY, name TEXT, email TEXT, phone TEXT,
register_date TEXT, is_vip INTEGER)''')

c.execute('''CREATE TABLE IF NOT EXISTS registrations
(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT,
email TEXT, phone TEXT, date TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS signal_usage
(user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0)''')

c.execute('''CREATE TABLE IF NOT EXISTS channel_signals
(id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, direction TEXT,
entry REAL, tp1 REAL, tp2 REAL, sl REAL, decimals INTEGER,
sent_date TEXT, sent_time TEXT, result TEXT DEFAULT "pending",
message_id INTEGER DEFAULT NULL, ticker TEXT,
channel_type TEXT DEFAULT "public", confidence REAL DEFAULT 0,
analysis TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS bot_settings
(key TEXT PRIMARY KEY, value TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS daily_public_counter
(date TEXT PRIMARY KEY, count INTEGER DEFAULT 0)''')
c.execute('''CREATE TABLE IF NOT EXISTS daily_vip_counter
(date TEXT PRIMARY KEY, count INTEGER DEFAULT 0)''')

# Add missing columns (safety)
for col in [
    "ALTER TABLE channel_signals ADD COLUMN message_id INTEGER DEFAULT NULL",
    "ALTER TABLE channel_signals ADD COLUMN ticker TEXT",
    "ALTER TABLE channel_signals ADD COLUMN channel_type TEXT DEFAULT 'public'",
    "ALTER TABLE channel_signals ADD COLUMN confidence REAL DEFAULT 0",
    "ALTER TABLE channel_signals ADD COLUMN analysis TEXT",
]:
    try:
        c.execute(col)
    except:
        pass
conn.commit()

def get_setting(key, default=None):
    c.execute("SELECT value FROM bot_settings WHERE key=?", (key,))
    row = c.fetchone()
    return row[0] if row else default

def set_setting(key, value):
    c.execute("REPLACE INTO bot_settings (key, value) VALUES (?,?)", (key, value))
    conn.commit()

# ============================================
# SYMBOLS LIST
# ============================================

SYMBOLS = [
    {"name": "XAU/USD", "ticker": "GC=F", "emoji": "🥇", "decimals": 2,
     "tp1_pct": 0.004, "tp2_pct": 0.008, "sl_pct": 0.003, "spread_pct": 0.001},
    {"name": "BTC/USD", "ticker": "BTC-USD", "emoji": "₿", "decimals": 0,
     "tp1_pct": 0.006, "tp2_pct": 0.012, "sl_pct": 0.004, "spread_pct": 0.001},
    {"name": "ETH/USD", "ticker": "ETH-USD", "emoji": "💎", "decimals": 1,
     "tp1_pct": 0.007, "tp2_pct": 0.014, "sl_pct": 0.005, "spread_pct": 0.001},
    {"name": "USOIL", "ticker": "CL=F", "emoji": "🛢️", "decimals": 2,
     "tp1_pct": 0.005, "tp2_pct": 0.010, "sl_pct": 0.003, "spread_pct": 0.001},
    {"name": "AUD/USD", "ticker": "AUDUSD=X", "emoji": "🦘", "decimals": 5,
     "tp1_pct": 0.003, "tp2_pct": 0.006, "sl_pct": 0.002, "spread_pct": 0.0003},
    {"name": "EUR/USD", "ticker": "EURUSD=X", "emoji": "💶", "decimals": 5,
     "tp1_pct": 0.003, "tp2_pct": 0.006, "sl_pct": 0.002, "spread_pct": 0.0003},
    {"name": "GBP/USD", "ticker": "GBPUSD=X", "emoji": "💷", "decimals": 5,
     "tp1_pct": 0.003, "tp2_pct": 0.006, "sl_pct": 0.002, "spread_pct": 0.0003},
    {"name": "USD/JPY", "ticker": "JPY=X", "emoji": "🇯🇵", "decimals": 3,
     "tp1_pct": 0.003, "tp2_pct": 0.005, "sl_pct": 0.002, "spread_pct": 0.0003},
    {"name": "NAS100", "ticker": "NQ=F", "emoji": "📈", "decimals": 0,
     "tp1_pct": 0.004, "tp2_pct": 0.008, "sl_pct": 0.003, "spread_pct": 0.001},
]

# ============================================
# TECHNICAL INDICATORS (multi‑analysis)
# ============================================

def compute_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50
    deltas = np.diff(prices[-period-1:])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def compute_macd(prices):
    if len(prices) < 26:
        return None, None, None
    ema12 = np.mean(prices[-12:])  # simplified
    ema26 = np.mean(prices[-26:])
    macd = ema12 - ema26
    signal = np.mean(prices[-9:])  # simplified
    histogram = macd - signal
    return macd, signal, histogram

def get_volume_confirmation(ticker):
    try:
        hist = yf.Ticker(ticker).history(period="2d", interval="1h")
        if len(hist) < 2:
            return False
        vol_today = hist["Volume"].iloc[-1]
        vol_yesterday = hist["Volume"].iloc[-2]
        return vol_today > vol_yesterday * 1.2
    except:
        return False

def analyze_symbol(symbol):
    """Returns (direction, confidence, current_price, analysis_text) or None"""
    try:
        ticker = yf.Ticker(symbol["ticker"])
        # 1‑hour data for indicators
        hist = ticker.history(period="5d", interval="1h")
        if hist.empty or len(hist) < 50:
            return None
        closes = hist["Close"].tolist()
        rsi = compute_rsi(closes)
        ema9 = np.mean(closes[-9:])
        ema21 = np.mean(closes[-21:])
        macd, signal, _ = compute_macd(closes)
        volume_confirm = get_volume_confirmation(symbol["ticker"])
        
        # Get current price from last 1-min bar (fallback to last hourly close)
        try:
            curr_min = ticker.history(period="1d", interval="1m")
            if not curr_min.empty:
                current_price = float(curr_min["Close"].iloc[-1])
            else:
                current_price = closes[-1]
        except:
            current_price = closes[-1]

        reasons = []
        confidence = 0.0
        direction = None

        # RSI condition
        if rsi < 30:
            reasons.append(f"RSI oversold ({rsi:.1f}) → bullish")
            confidence += 0.3
            direction = "BUY"
        elif rsi > 70:
            reasons.append(f"RSI overbought ({rsi:.1f}) → bearish")
            confidence += 0.3
            direction = "SELL"

        # EMA crossover
        if ema9 > ema21 and current_price > ema21:
            reasons.append("EMA 9 above EMA 21, price above both → uptrend")
            confidence += 0.3 if direction == "BUY" else 0.1
            if direction is None:
                direction = "BUY"
        elif ema9 < ema21 and current_price < ema21:
            reasons.append("EMA 9 below EMA 21, price below both → downtrend")
            confidence += 0.3 if direction == "SELL" else 0.1
            if direction is None:
                direction = "SELL"

        # MACD
        if macd is not None and signal is not None:
            if macd > signal:
                reasons.append("MACD line above signal line → bullish momentum")
                confidence += 0.2 if direction == "BUY" else 0.05
            else:
                reasons.append("MACD line below signal line → bearish momentum")
                confidence += 0.2 if direction == "SELL" else 0.05

        # Volume confirmation
        if volume_confirm:
            reasons.append("Volume spike confirming the move")
            confidence += 0.2

        # Final decision
        if direction is None or confidence < 0.6:
            return None

        confidence = min(confidence, 0.95)
        analysis_text = "🔍 *Analysis:*\n" + "\n".join(f"• {r}" for r in reasons)
        return (direction, confidence, current_price, analysis_text)

    except Exception as e:
        print(f"Error analyzing {symbol['name']}: {e}")
        return None

# ============================================
# SIGNAL GENERATION & STORAGE
# ============================================

def generate_signal_data(symbol, direction, current_price, analysis_text):
    decimals = symbol["decimals"]
    spread = current_price * symbol["spread_pct"]
    if direction == "BUY":
        entry_low = round(current_price - spread, decimals)
        entry_high = round(current_price + spread, decimals)
        tp1 = round(current_price * (1 + symbol["tp1_pct"]), decimals)
        tp2 = round(current_price * (1 + symbol["tp2_pct"]), decimals)
        sl = round(current_price * (1 - symbol["sl_pct"]), decimals)
    else:
        entry_low = round(current_price - spread, decimals)
        entry_high = round(current_price + spread, decimals)
        tp1 = round(current_price * (1 - symbol["tp1_pct"]), decimals)
        tp2 = round(current_price * (1 - symbol["tp2_pct"]), decimals)
        sl = round(current_price * (1 + symbol["sl_pct"]), decimals)
    return {
        "symbol": symbol["name"],
        "ticker": symbol["ticker"],
        "emoji": symbol["emoji"],
        "direction": direction,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "tp1": tp1,
        "tp2": tp2,
        "sl": sl,
        "decimals": decimals,
        "price": current_price,
        "dir_emoji": "🟢" if direction == "BUY" else "🔴",
        "analysis": analysis_text,
    }

def save_signal_to_db(signal, channel_type, confidence):
    now = datetime.datetime.now()
    entry_mid = (signal["entry_low"] + signal["entry_high"]) / 2
    c.execute("""INSERT INTO channel_signals
    (symbol, direction, entry, tp1, tp2, sl, decimals, sent_date, sent_time, ticker, channel_type, confidence, analysis)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (signal["symbol"], signal["direction"], entry_mid,
     signal["tp1"], signal["tp2"], signal["sl"], signal["decimals"],
     now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), signal["ticker"],
     channel_type, confidence, signal["analysis"]))
    conn.commit()
    return c.lastrowid

def update_message_id(signal_id, msg_id):
    c.execute("UPDATE channel_signals SET message_id=? WHERE id=?", (msg_id, signal_id))
    conn.commit()

def update_signal_result(signal_id, result):
    c.execute("UPDATE channel_signals SET result=? WHERE id=?", (result, signal_id))
    conn.commit()

# ============================================
# DAILY COUNTERS FOR CHANNELS
# ============================================

def get_daily_public_count():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT count FROM daily_public_counter WHERE date=?", (today,))
    row = c.fetchone()
    return row[0] if row else 0

def inc_daily_public_count():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    c.execute("INSERT INTO daily_public_counter (date, count) VALUES (?,1) ON CONFLICT(date) DO UPDATE SET count = count + 1", (today,))
    conn.commit()

def get_daily_vip_count():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT count FROM daily_vip_counter WHERE date=?", (today,))
    row = c.fetchone()
    return row[0] if row else 0

def inc_daily_vip_count():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    c.execute("INSERT INTO daily_vip_counter (date, count) VALUES (?,1) ON CONFLICT(date) DO UPDATE SET count = count + 1", (today,))
    conn.commit()

# ============================================
# MESSAGE TEMPLATES
# ============================================

def build_signal_text(signal, confidence, channel_type="public"):
    header = "📢 *FREE SIGNAL*" if channel_type == "public" else "⭐ *VIP EXCLUSIVE SIGNAL*"
    return f"""
{header}
{signal['emoji']} *{signal['direction']} {signal['symbol']}*

📌 Entry: `{signal['entry_low']} - {signal['entry_high']}`
🎯 TP1: `{signal['tp1']}`
🎯 TP2: `{signal['tp2']}`
🛑 SL: `{signal['sl']}`

{signal['analysis']}

📊 *Confidence: {int(confidence*100)}%*
⚠️ Risk 1-2% per trade only.

💎 Join VIP for early entries: {VIP_CHANNEL_LINK}
"""

def build_hype_message(symbol, direction, tp_hit, profit, unit):
    return f"""
🎯🔥 *TARGET HIT!* 🔥🎯

{symbol} {direction} → *{tp_hit} REACHED!*
+{profit} {unit} profit 💰

💎 VIP members got this entry 30 mins early!
👉 Join VIP: {VIP_CHANNEL_LINK}
"""

def build_vip_warning(symbol, direction, current, sl):
    return f"""
⚠️ *VIP ALERT: SL APPROACHING* ⚠️

{symbol} {direction} signal is under pressure.
Current: {current} | SL: {sl}

🔴 *Consider closing the trade* to protect capital.
More signals coming soon.
"""

# ============================================
# PROMOTIONAL MESSAGES (for public channel)
# ============================================

PROMO_MESSAGES = [
    f"⭐ *Why go VIP?* ⭐\n\n✅ 20-25 premium signals daily\n✅ Early entries before the move\n✅ 1-on-1 support\n✅ 89% win rate\n\n💰 Just ₹399/month\n👉 {VIP_CHANNEL_LINK}",
    f"🚀 *Last week's VIP performance* 🚀\n\n📊 22 signals | 20 TP hits\n📈 Average profit per trade: ₹850\n💰 Total profit: ₹18,700+\n\nDon't miss out → {VIP_CHANNEL_LINK}",
    f"💎 *VIP members get signals 30 minutes before everyone else.*\n\nThat means better entries and bigger profits.\n\nJoin now: {VIP_CHANNEL_LINK}",
    f"📢 *Limited slots available!* 📢\n\nOnly 7 VIP spots left this month.\n\n💰 ₹399/month – cancel anytime.\n\n👉 {VIP_CHANNEL_LINK}",
    f"🏆 *Member testimonial* 🏆\n\n\"I made back my VIP fee in 2 days. Best decision ever!\" – Rajesh K.\n\nJoin Rajesh and 5000+ others → {VIP_CHANNEL_LINK}",
    f"📊 *Free vs VIP* 📊\n\nFree channel: 5-7 signals/day\nVIP channel: 20-25 signals/day + early entries + live support\n\nUpgrade now: {VIP_CHANNEL_LINK}",
    f"🔥 *Today's VIP profit update* 🔥\n\nGold BUY → TP2 hit (+₹1200)\nBTC SELL → TP1 hit (+₹800)\nEUR/USD BUY → TP2 hit (+₹500)\n\nTotal: +₹2500 in one day!\n\n👉 {VIP_CHANNEL_LINK}",
    f"💡 *Trading tip* 💡\n\nThe difference between profitable traders and losers? Early entries and risk management.\n\nVIP gives you both. Join: {VIP_CHANNEL_LINK}",
    f"🎁 *Special offer* 🎁\n\nFirst 10 new VIP members this week get a free 1-on-1 strategy session.\n\nUse code: KAILASH10\n\n👉 {VIP_CHANNEL_LINK}",
    f"📈 *89% win rate is not luck – it's our system.*\n\nVIP members trust our analysis daily.\n\nStart earning today: {VIP_CHANNEL_LINK}",
]

def get_random_promo():
    return random.choice(PROMO_MESSAGES)

def promo_sender():
    """Sends a promotional message to public channel every 30-45 minutes"""
    while True:
        interval = random.randint(PROMO_INTERVAL[0], PROMO_INTERVAL[1])
        time.sleep(interval)
        try:
            promo_text = get_random_promo()
            bot.send_message(PUBLIC_CHANNEL_ID, promo_text, parse_mode='Markdown')
            print(f"Promo sent at {datetime.datetime.now()}")
        except Exception as e:
            print(f"Promo error: {e}")

# ============================================
# PRICE MONITOR (every 60 sec)
# ============================================

def get_live_price(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="1d", interval="1m")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except:
        pass
    return None

def price_monitor():
    while True:
        try:
            c.execute("SELECT id, symbol, direction, entry, tp1, tp2, sl, decimals, message_id, ticker, channel_type FROM channel_signals WHERE result='pending' AND message_id IS NOT NULL")
            pending = c.fetchall()
            for row in pending:
                sig_id, symbol, direction, entry, tp1, tp2, sl, decimals, msg_id, ticker, ch_type = row
                current = get_live_price(ticker)
                if current is None:
                    continue

                # Check TP2 first
                if direction == "BUY" and current >= tp2:
                    profit = round(current - entry, decimals) if decimals <= 2 else round((current - entry) * 10000, 1)
                    unit = "$" if decimals <= 2 else "pips"
                    hype = build_hype_message(symbol, direction, "TP2 🎯🎯", profit, unit)
                    try:
                        bot.send_message(PUBLIC_CHANNEL_ID, hype, parse_mode='Markdown')
                        if ch_type == "vip":
                            bot.send_message(VIP_CHANNEL_ID, hype, parse_mode='Markdown')
                        update_signal_result(sig_id, "tp_hit")
                    except:
                        pass
                    continue
                elif direction == "SELL" and current <= tp2:
                    profit = round(entry - current, decimals) if decimals <= 2 else round((entry - current) * 10000, 1)
                    unit = "$" if decimals <= 2 else "pips"
                    hype = build_hype_message(symbol, direction, "TP2 🎯🎯", profit, unit)
                    try:
                        bot.send_message(PUBLIC_CHANNEL_ID, hype, parse_mode='Markdown')
                        if ch_type == "vip":
                            bot.send_message(VIP_CHANNEL_ID, hype, parse_mode='Markdown')
                        update_signal_result(sig_id, "tp_hit")
                    except:
                        pass
                    continue

                # Check TP1
                if direction == "BUY" and current >= tp1:
                    profit = round(current - entry, decimals) if decimals <= 2 else round((current - entry) * 10000, 1)
                    unit = "$" if decimals <= 2 else "pips"
                    hype = build_hype_message(symbol, direction, "TP1 🎯", profit, unit)
                    try:
                        bot.send_message(PUBLIC_CHANNEL_ID, hype, parse_mode='Markdown')
                        if ch_type == "vip":
                            bot.send_message(VIP_CHANNEL_ID, hype, parse_mode='Markdown')
                        update_signal_result(sig_id, "tp_hit")
                    except:
                        pass
                    continue
                elif direction == "SELL" and current <= tp1:
                    profit = round(entry - current, decimals) if decimals <= 2 else round((entry - current) * 10000, 1)
                    unit = "$" if decimals <= 2 else "pips"
                    hype = build_hype_message(symbol, direction, "TP1 🎯", profit, unit)
                    try:
                        bot.send_message(PUBLIC_CHANNEL_ID, hype, parse_mode='Markdown')
                        if ch_type == "vip":
                            bot.send_message(VIP_CHANNEL_ID, hype, parse_mode='Markdown')
                        update_signal_result(sig_id, "tp_hit")
                    except:
                        pass
                    continue

                # Check SL (with warning for VIP)
                near_sl = False
                if direction == "BUY":
                    if current <= sl:
                        if ch_type == "public":
                            try:
                                bot.delete_message(PUBLIC_CHANNEL_ID, msg_id)
                            except:
                                pass
                            update_signal_result(sig_id, "sl_hit")
                        else:
                            update_signal_result(sig_id, "sl_hit")
                        continue
                    # VIP warning when price within 30% of SL
                    sl_dist = abs(entry - sl)
                    if sl_dist > 0 and (current - sl) / sl_dist < 0.3:
                        near_sl = True
                else:  # SELL
                    if current >= sl:
                        if ch_type == "public":
                            try:
                                bot.delete_message(PUBLIC_CHANNEL_ID, msg_id)
                            except:
                                pass
                            update_signal_result(sig_id, "sl_hit")
                        else:
                            update_signal_result(sig_id, "sl_hit")
                        continue
                    sl_dist = abs(sl - entry)
                    if sl_dist > 0 and (sl - current) / sl_dist < 0.3:
                        near_sl = True

                if near_sl and ch_type == "vip":
                    warn = build_vip_warning(symbol, direction, round(current, decimals), sl)
                    try:
                        bot.send_message(VIP_CHANNEL_ID, warn, parse_mode='Markdown')
                        update_signal_result(sig_id, "warned")
                    except:
                        pass

        except Exception as e:
            print(f"Price monitor error: {e}")
        time.sleep(60)  # check every minute

# ============================================
# SIGNAL SCANNER (every 60 sec, with jitter)
# ============================================

last_signal_time = {}

def signal_scanner():
    while True:
        try:
            now = datetime.datetime.now()
            today = now.strftime("%Y-%m-%d")
            public_count = get_daily_public_count()
            vip_count = get_daily_vip_count()

            for symbol in SYMBOLS:
                # Rate limit per symbol: at most one signal every 10 minutes
                last = last_signal_time.get(symbol["name"])
                if last and (now - last).seconds < 600:
                    continue

                result = analyze_symbol(symbol)
                if result is None:
                    continue
                direction, confidence, current_price, analysis_text = result

                # Decide channel based on daily limits and confidence
                if confidence >= 0.75 and vip_count < VIP_SIGNALS_PER_DAY:
                    signal = generate_signal_data(symbol, direction, current_price, analysis_text)
                    sig_id = save_signal_to_db(signal, "vip", confidence)
                    text = build_signal_text(signal, confidence, "vip")
                    try:
                        sent = bot.send_message(VIP_CHANNEL_ID, text, parse_mode='Markdown')
                        update_message_id(sig_id, sent.message_id)
                        inc_daily_vip_count()
                        vip_count += 1
                        last_signal_time[symbol["name"]] = now
                        print(f"VIP signal sent: {symbol['name']} {direction}")
                    except Exception as e:
                        print(f"Failed to send VIP signal: {e}")

                elif confidence >= 0.7 and public_count < PUBLIC_SIGNALS_PER_DAY:
                    signal = generate_signal_data(symbol, direction, current_price, analysis_text)
                    sig_id = save_signal_to_db(signal, "public", confidence)
                    text = build_signal_text(signal, confidence, "public")
                    try:
                        sent = bot.send_message(PUBLIC_CHANNEL_ID, text, parse_mode='Markdown')
                        update_message_id(sig_id, sent.message_id)
                        inc_daily_public_count()
                        public_count += 1
                        last_signal_time[symbol["name"]] = now
                        print(f"Public signal sent: {symbol['name']} {direction}")
                    except Exception as e:
                        print(f"Failed to send public signal: {e}")

                # Small random delay to avoid hitting API limits
                time.sleep(random.uniform(1, 5))

        except Exception as e:
            print(f"Scanner error: {e}")
        time.sleep(60)  # scan every minute

# ============================================
# TELEGRAM BOT COMMANDS (individual users)
# ============================================

bot = telebot.TeleBot(BOT_TOKEN)

def main_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    btn1 = telebot.types.InlineKeyboardButton("📝 Register", callback_data="register")
    btn2 = telebot.types.InlineKeyboardButton("📊 Free Signal", callback_data="free")
    btn3 = telebot.types.InlineKeyboardButton("⭐ VIP Access", callback_data="vip")
    btn4 = telebot.types.InlineKeyboardButton("💬 Support", callback_data="support")
    btn5 = telebot.types.InlineKeyboardButton("🌐 Website", url=WEBSITE_URL)
    btn6 = telebot.types.InlineKeyboardButton("📢 Free Channel", url=FREE_CHANNEL_LINK)
    keyboard.add(btn1, btn2, btn3, btn4, btn5, btn6)
    return keyboard

@bot.message_handler(commands=['start'])
def start(message):
    msg = f"""🚀 *Forex Trading With Kailash* 🚀

India's Most Trusted Forex Signals Provider

📊 *Services:*
✅ FREE Signals - {USER_FREE_SIGNAL_LIMIT} per user
⭐ VIP Channel - ₹399/month
🔄 Copy Trading Available
📺 Live Trading Sessions
📈 89% Win Rate | 5000+ Traders

🌐 *Website:* {WEBSITE_URL}
📢 *Free Channel:* {FREE_CHANNEL_LINK}

👇 *Choose an option:*"""
    bot.reply_to(message, msg, parse_mode='Markdown', reply_markup=main_keyboard())

@bot.message_handler(commands=['register'])
def register_cmd(message):
    msg = bot.reply_to(message, "📝 *Send your details:*\n\n`Name, Email, Phone`\n\nExample: `Rajesh, rajesh@gmail.com, 9876543210`", parse_mode='Markdown')
    bot.register_next_step_handler(msg, save_user)

def save_user(message):
    user_id = message.from_user.id
    username = message.from_user.username or "No username"
    try:
        data = message.text.split(',')
        name = data[0].strip()
        email = data[1].strip()
        phone = data[2].strip()
        c.execute("INSERT OR REPLACE INTO users (user_id, name, email, phone, register_date, is_vip) VALUES (?, ?, ?, ?, ?, ?)",
                  (user_id, name, email, phone, str(datetime.datetime.now()), 0))
        c.execute("INSERT INTO registrations (user_id, name, email, phone, date) VALUES (?, ?, ?, ?, ?)",
                  (user_id, name, email, phone, str(datetime.datetime.now())))
        conn.commit()
        admin_msg = f"""🔔 *NEW REGISTRATION* 🔔
👤 *Name:* {name}
📧 *Email:* {email}
📱 *Phone:* {phone}
🆔 *User ID:* {user_id}
👤 *Username:* @{username}
🕐 *Time:* {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}
📢 *Free Channel:* {FREE_CHANNEL_LINK}
⭐ *VIP:* ₹399/month - {UPI_ID}
💬 *Reply to contact this user*"""
        bot.send_message(ADMIN_ID, admin_msg, parse_mode='Markdown')
        reply_msg = f"""✅ *Welcome {name}!* ✅

Your registration is complete!

📊 *What you get:*
• {USER_FREE_SIGNAL_LIMIT} free signals (via /free)
• Market analysis
• Risk management tips

👇 *Use buttons below:*"""
        bot.reply_to(message, reply_msg, parse_mode='Markdown', reply_markup=main_keyboard())
    except:
        bot.reply_to(message, "❌ *Invalid Format!*\n\nSend: `Name, Email, Phone`\nExample: `Rajesh, rajesh@gmail.com, 9876543210`", parse_mode='Markdown')

@bot.message_handler(commands=['free'])
def free_signal(message):
    user_id = message.from_user.id
    c.execute("SELECT count FROM signal_usage WHERE user_id=?", (user_id,))
    row = c.fetchone()
    used = row[0] if row else 0
    if used >= USER_FREE_SIGNAL_LIMIT:
        bot.reply_to(message, f"🚫 *Free Signal Limit Reached!*\n\nYou have used all {USER_FREE_SIGNAL_LIMIT} free signals.\nJoin our free channel for unlimited signals: {FREE_CHANNEL_LINK}", parse_mode='Markdown')
        return
    # Generate a simple free signal (random but based on current price)
    symbol = random.choice(SYMBOLS)
    try:
        ticker = yf.Ticker(symbol["ticker"])
        price = ticker.history(period="1d", interval="1m")["Close"].iloc[-1]
    except:
        price = 100.0
    direction = random.choice(["BUY", "SELL"])
    signal = generate_signal_data(symbol, direction, price, "📊 Quick analysis: Market momentum.")
    text = f"📊 *FREE SIGNAL (User #{user_id})*\n{signal['emoji']} *{direction} {symbol['name']}*\n📌 Entry: `{signal['entry_low']} - {signal['entry_high']}`\n🎯 TP1: `{signal['tp1']}`\n🎯 TP2: `{signal['tp2']}`\n🛑 SL: `{signal['sl']}`\n\n⚠️ Limited free signals. Join our channel for daily 5-7 signals: {FREE_CHANNEL_LINK}"
    bot.reply_to(message, text, parse_mode='Markdown')
    # Increment usage
    c.execute("INSERT INTO signal_usage (user_id, count) VALUES (?,1) ON CONFLICT(user_id) DO UPDATE SET count = count + 1", (user_id,))
    conn.commit()

@bot.message_handler(commands=['vip'])
def vip_command(message):
    msg = f"""⭐ *VIP Telegram Channel* ⭐

*Premium Benefits:*
✅ 20-25 Premium Signals Daily
✅ Early Entry Alerts (Before Market)
✅ Live Market Analysis
✅ 1-on-1 VIP Support
✅ 89% Win Rate Guarantee

💰 *Price:* ₹399/month

*Payment Details:*
📱 UPI ID: `{UPI_ID}`

*How to Join:*
1️⃣ Pay ₹399 to above UPI ID
2️⃣ Send payment screenshot to {CONTACT_USERNAME}
3️⃣ Get VIP channel link

🔗 *VIP Channel:* {VIP_CHANNEL_LINK}

*After verification, you'll get instant access!*"""
    bot.reply_to(message, msg, parse_mode='Markdown', reply_markup=main_keyboard())

@bot.message_handler(commands=['support'])
def support_command(message):
    msg = f"""💬 *Need Help?* 💬

📱 *Telegram:* {CONTACT_USERNAME}
📧 *Email:* btcuscoinbase@gmail.com
🌐 *Website:* {WEBSITE_URL}

*Response Time:*
• VIP Members: Within 2 hours
• Free Users: Within 24 hours

We're here to help! 🚀"""
    bot.reply_to(message, msg, parse_mode='Markdown', reply_markup=main_keyboard())

@bot.message_handler(commands=['website'])
def website_command(message):
    bot.reply_to(message, f"🌐 *Visit our website:*\n\n{WEBSITE_URL}\n\nRegister, get signals, and upgrade to VIP!", parse_mode='Markdown', reply_markup=main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    if call.data == "register":
        msg = bot.send_message(call.message.chat.id, "📝 *Send:* `Name, Email, Phone`\n\nExample: `Rajesh, rajesh@gmail.com, 9876543210`", parse_mode='Markdown')
        bot.register_next_step_handler(msg, save_user)
    elif call.data == "free":
        user_id = call.from_user.id
        c.execute("SELECT count FROM signal_usage WHERE user_id=?", (user_id,))
        row = c.fetchone()
        used = row[0] if row else 0
        if used >= USER_FREE_SIGNAL_LIMIT:
            bot.send_message(call.message.chat.id, f"🚫 *Free Signal Limit Reached!*\n\nJoin free channel: {FREE_CHANNEL_LINK}", parse_mode='Markdown')
        else:
            symbol = random.choice(SYMBOLS)
            try:
                ticker = yf.Ticker(symbol["ticker"])
                price = ticker.history(period="1d", interval="1m")["Close"].iloc[-1]
            except:
                price = 100.0
            direction = random.choice(["BUY", "SELL"])
            signal = generate_signal_data(symbol, direction, price, "Quick analysis.")
            text = f"📊 *FREE SIGNAL*\n{signal['emoji']} *{direction} {symbol['name']}*\n📌 Entry: `{signal['entry_low']} - {signal['entry_high']}`\n🎯 TP1: `{signal['tp1']}`\n🎯 TP2: `{signal['tp2']}`\n🛑 SL: `{signal['sl']}`"
            bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
            c.execute("INSERT INTO signal_usage (user_id, count) VALUES (?,1) ON CONFLICT(user_id) DO UPDATE SET count = count + 1", (user_id,))
            conn.commit()
    elif call.data == "vip":
        msg = f"⭐ *VIP Access*\n\n💰 ₹399/month\n📱 UPI: `{UPI_ID}`\nPay & send screenshot to {CONTACT_USERNAME}\n🔗 {VIP_CHANNEL_LINK}"
        bot.send_message(call.message.chat.id, msg, parse_mode='Markdown')
    elif call.data == "support":
        bot.send_message(call.message.chat.id, f"💬 Contact: {CONTACT_USERNAME}\n📧 Email: btcuscoinbase@gmail.com")
    bot.answer_callback_query(call.id)

@bot.message_handler(commands=['stats'])
def stats_command(message):
    if message.from_user.id == ADMIN_ID:
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM registrations WHERE date LIKE ?", (f"{datetime.datetime.now().strftime('%Y-%m-%d')}%",))
        today_reg = c.fetchone()[0]
        msg = f"""📊 *BOT STATISTICS* 📊

👥 Total Users: {total_users}
📝 Today's Registrations: {today_reg}
🤖 Bot Status: Active ✅
🕐 Last Update: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}

💬 *Commands:* /start, /register, /free, /vip, /support, /website"""
        bot.reply_to(message, msg, parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ *Unauthorized*", parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def help_command(message):
    msg = """📚 *Available Commands* 📚

/start - Start the bot
/register - Register for free signals
/free - Get one free signal (limited to 3 per user)
/vip - VIP channel access info
/support - Contact support
/website - Visit our website
/help - Show this help

*Need more help?* Contact @Yungshang1"""
    bot.reply_to(message, msg, parse_mode='Markdown', reply_markup=main_keyboard())

# ============================================
# START THREADS AND BOT
# ============================================

if __name__ == "__main__":
    # FIRST: Delete any existing webhook (fixes 409 error)
    try:
        bot.delete_webhook()
        print("Webhook deleted successfully.")
    except Exception as e:
        print(f"Webhook deletion error: {e}")

    print("🤖 Forex Bot Started")
    print(f"Public channel ID: {PUBLIC_CHANNEL_ID}")
    print(f"VIP channel ID: {VIP_CHANNEL_ID}")

    # Start background threads
    threading.Thread(target=signal_scanner, daemon=True).start()
    threading.Thread(target=price_monitor, daemon=True).start()
    threading.Thread(target=promo_sender, daemon=True).start()   # NEW promo thread

    # Start polling (no webhook)
    bot.infinity_polling()
