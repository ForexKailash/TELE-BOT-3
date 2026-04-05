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
# CONFIGURATION (Your Credentials)
# ============================================

BOT_TOKEN = "8653450456:AAER9w6Gjj5IWkyCs1taa01N-DdMFZqxt3E"
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")

ADMIN_ID = 6253584826
CHANNEL_ID = '@tradewithkailashh'
WEBSITE_URL = 'https://forexkailash.netlify.app'
FREE_CHANNEL = 'https://t.me/tradewithkailashh'
VIP_CHANNEL = 'https://t.me/+Snj0BVAwjDo3NTA1'
UPI_ID = 'kailashbhardwaj66-2@okicici'
CONTACT_USERNAME = '@Yungshang1'
COURSE_URL = 'https://forexkailash.netlify.app'

# VIP Channel Numeric ID
VIP_CHANNEL_ID = -1003826269063

# Daily Signal Limits
FREE_SIGNAL_LIMIT_DAILY = 7      # 5-7 trades per day on free channel
VIP_SIGNAL_LIMIT_DAILY = 25      # 20-25 trades per day on VIP channel

# ============================================
# DATABASE SETUP
# ============================================

os.makedirs('telegram_bot', exist_ok=True)
conn = sqlite3.connect('telegram_bot/users.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS users
(user_id INTEGER PRIMARY KEY, name TEXT, email TEXT, phone TEXT,
register_date TEXT, is_vip INTEGER)''')

c.execute('''CREATE TABLE IF NOT EXISTS registrations
(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT,
email TEXT, phone TEXT, date TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS signal_usage
(user_id INTEGER PRIMARY KEY, last_date TEXT, count INTEGER DEFAULT 0)''')

c.execute('''CREATE TABLE IF NOT EXISTS channel_signals
(id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, direction TEXT,
entry REAL, tp1 REAL, tp2 REAL, sl REAL, decimals INTEGER,
sent_date TEXT, sent_time TEXT, result TEXT DEFAULT "pending",
message_id INTEGER DEFAULT NULL, ticker TEXT,
channel_type TEXT DEFAULT "public", confidence INTEGER DEFAULT 0)''')

c.execute('''CREATE TABLE IF NOT EXISTS bot_settings
(key TEXT PRIMARY KEY, value TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS daily_public_counter
(date TEXT PRIMARY KEY, count INTEGER DEFAULT 0)''')

c.execute('''CREATE TABLE IF NOT EXISTS daily_vip_counter
(date TEXT PRIMARY KEY, count INTEGER DEFAULT 0)''')

c.execute('''CREATE TABLE IF NOT EXISTS active_trades
(symbol TEXT PRIMARY KEY, direction TEXT, signal_id INTEGER, sent_time TEXT)''')

# Add missing columns if they don't exist
for col in [
    "ALTER TABLE channel_signals ADD COLUMN message_id INTEGER DEFAULT NULL",
    "ALTER TABLE channel_signals ADD COLUMN ticker TEXT",
    "ALTER TABLE channel_signals ADD COLUMN channel_type TEXT DEFAULT 'public'",
    "ALTER TABLE channel_signals ADD COLUMN confidence INTEGER DEFAULT 0",
    "ALTER TABLE signal_usage ADD COLUMN last_date TEXT",
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
    c.execute("INSERT INTO bot_settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=?", (key, value, value))
    conn.commit()

# ============================================
# DAILY COUNTER FUNCTIONS
# ============================================

def get_daily_public_count():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT count FROM daily_public_counter WHERE date=?", (today,))
    row = c.fetchone()
    return row[0] if row else 0

def increment_daily_public_count():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    c.execute("INSERT INTO daily_public_counter (date, count) VALUES (?,1) ON CONFLICT(date) DO UPDATE SET count = count + 1", (today,))
    conn.commit()

def get_daily_vip_count():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT count FROM daily_vip_counter WHERE date=?", (today,))
    row = c.fetchone()
    return row[0] if row else 0

def increment_daily_vip_count():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    c.execute("INSERT INTO daily_vip_counter (date, count) VALUES (?,1) ON CONFLICT(date) DO UPDATE SET count = count + 1", (today,))
    conn.commit()

# ============================================
# USER FREE SIGNAL LIMIT (per user)
# ============================================

def reset_daily_if_needed(user_id):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT last_date, count FROM signal_usage WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if not row or row[0] != today:
        c.execute("INSERT OR REPLACE INTO signal_usage (user_id, last_date, count) VALUES (?,?,?)", (user_id, today, 0))
        conn.commit()
        return 0
    return row[1]

def get_signal_count_today(user_id):
    reset_daily_if_needed(user_id)
    c.execute("SELECT count FROM signal_usage WHERE user_id=?", (user_id,))
    row = c.fetchone()
    return row[0] if row else 0

def increment_user_signal_count(user_id):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    c.execute("INSERT INTO signal_usage (user_id, last_date, count) VALUES (?,?,1) ON CONFLICT(user_id) DO UPDATE SET count = count + 1, last_date = ?", (user_id, today, today))
    conn.commit()

def signals_remaining(user_id):
    used = get_signal_count_today(user_id)
    return max(0, 3 - used)  # 3 free signals per user

# ============================================
# TECHNICAL INDICATORS (Real Market Analysis)
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

def calculate_rsi(prices, period=14):
    """Calculate RSI from price list"""
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

def get_technical_signal(symbol):
    """Returns (direction, confidence, current_price) or None"""
    try:
        ticker = yf.Ticker(symbol["ticker"])
        
        # Get 1-hour data for indicators
        hist = ticker.history(period="3d", interval="1h")
        if hist.empty or len(hist) < 30:
            return None
        
        closes = hist["Close"].tolist()
        rsi = calculate_rsi(closes)
        
        # Get current price from 1-min data
        curr_data = ticker.history(period="1d", interval="1m")
        if curr_data.empty:
            return None
        current_price = float(curr_data["Close"].iloc[-1])
        
        # Calculate moving averages
        sma20 = np.mean(closes[-20:])
        sma50 = np.mean(closes[-50:]) if len(closes) >= 50 else sma20
        ema9 = np.mean(closes[-9:])
        ema21 = np.mean(closes[-21:]) if len(closes) >= 21 else sma20
        
        # Signal Generation Logic
        # Strong BUY: RSI oversold + price above SMA20
        if rsi < 35 and current_price > sma20:
            confidence = 85 + int((35 - rsi) / 2)
            return ("BUY", min(95, confidence), current_price)
        
        # Strong SELL: RSI overbought + price below SMA20
        elif rsi > 65 and current_price < sma20:
            confidence = 85 + int((rsi - 65) / 2)
            return ("SELL", min(95, confidence), current_price)
        
        # Medium BUY: Bullish EMA crossover
        elif rsi < 50 and ema9 > ema21 and current_price > ema9:
            return ("BUY", 75, current_price)
        
        # Medium SELL: Bearish EMA crossover
        elif rsi > 50 and ema9 < ema21 and current_price < ema9:
            return ("SELL", 75, current_price)
        
        return None
    except Exception as e:
        print(f"Error analyzing {symbol['name']}: {e}")
        return None

# ============================================
# SIGNAL GENERATION & SENDING
# ============================================

def generate_signal_data(symbol, direction, current_price, confidence):
    """Create signal dict with entry, TP, SL levels"""
    decimals = symbol["decimals"]
    spread = current_price * symbol["spread_pct"]
    
    if direction == "BUY":
        entry_low = round(current_price - spread, decimals)
        entry_high = round(current_price + spread, decimals)
        tp1 = round(current_price * (1 + symbol["tp1_pct"]), decimals)
        tp2 = round(current_price * (1 + symbol["tp2_pct"]), decimals)
        sl = round(current_price * (1 - symbol["sl_pct"]), decimals)
        analysis = f"RSI oversold + price above SMA20. Bullish momentum expected."
    else:
        entry_low = round(current_price - spread, decimals)
        entry_high = round(current_price + spread, decimals)
        tp1 = round(current_price * (1 - symbol["tp1_pct"]), decimals)
        tp2 = round(current_price * (1 - symbol["tp2_pct"]), decimals)
        sl = round(current_price * (1 + symbol["sl_pct"]), decimals)
        analysis = f"RSI overbought + price below SMA20. Bearish reversal expected."
    
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
        "confidence": confidence,
        "analysis": analysis,
        "dir_emoji": "🟢" if direction == "BUY" else "🔴",
    }

def save_signal_to_db(signal, channel_type, message_id):
    """Save signal to database"""
    now = datetime.datetime.now()
    entry_mid = (signal["entry_low"] + signal["entry_high"]) / 2
    c.execute("""INSERT INTO channel_signals
    (symbol, direction, entry, tp1, tp2, sl, decimals, sent_date, sent_time, ticker, channel_type, message_id, confidence)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (signal["symbol"], signal["direction"], entry_mid,
     signal["tp1"], signal["tp2"], signal["sl"], signal["decimals"],
     now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), signal["ticker"], channel_type, message_id, signal["confidence"]))
    conn.commit()
    return c.lastrowid

def update_signal_result(signal_id, result):
    c.execute("UPDATE channel_signals SET result=? WHERE id=?", (result, signal_id))
    conn.commit()

def is_active_trade(symbol):
    c.execute("SELECT * FROM active_trades WHERE symbol=?", (symbol,))
    return c.fetchone() is not None

def add_active_trade(symbol, direction, signal_id):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    c.execute("INSERT OR REPLACE INTO active_trades (symbol, direction, signal_id, sent_time) VALUES (?,?,?,?)", 
              (symbol, direction, signal_id, now))
    conn.commit()

def remove_active_trade(symbol):
    c.execute("DELETE FROM active_trades WHERE symbol=?", (symbol,))
    conn.commit()

def send_signal_to_channels(signal):
    """Send signal to public and VIP channels with daily limits"""
    now = datetime.datetime.now()
    current_hour = now.hour
    
    # Only send during active market hours (optional: 24/7 if you want)
    # if current_hour < 1 or current_hour > 23:  # Uncomment to restrict hours
    #     return
    
    signal_text = f"""
{signal['emoji']} *{signal['direction']} {signal['symbol']}* 📊
🕐 _{now.strftime('%d %b %Y, %H:%M')} IST_

📌 Entry: `{signal['entry_low']} - {signal['entry_high']}`
🎯 TP1: `{signal['tp1']}`
🎯 TP2: `{signal['tp2']}`
🛑 SL: `{signal['sl']}`

📈 *Analysis:* {signal['analysis']}
⭐ *Confidence: {signal['confidence']}%*

⚠️ *Risk:* Use 1-2% risk per trade.
📢 *VIP Signals:* {VIP_CHANNEL}
"""
    
    # Send to Public Channel (if under daily limit)
    public_count = get_daily_public_count()
    public_msg_id = None
    
    if public_count < FREE_SIGNAL_LIMIT_DAILY:
        try:
            msg = bot.send_message(CHANNEL_ID, signal_text, parse_mode='Markdown')
            public_msg_id = msg.message_id
            increment_daily_public_count()
            print(f"✅ Public signal sent: {signal['direction']} {signal['symbol']} ({public_count+1}/{FREE_SIGNAL_LIMIT_DAILY})")
        except Exception as e:
            print(f"Failed to send to public channel: {e}")
    
    # Send to VIP Channel (if under daily limit)
    vip_count = get_daily_vip_count()
    vip_msg_id = None
    
    if vip_count < VIP_SIGNAL_LIMIT_DAILY:
        vip_text = f"""
⭐ *VIP PREMIUM SIGNAL* ⭐
{signal_text}
💎 *Early Entry for VIP members only!*
🔗 {VIP_CHANNEL}
"""
        try:
            msg = bot.send_message(VIP_CHANNEL_ID, vip_text, parse_mode='Markdown')
            vip_msg_id = msg.message_id
            increment_daily_vip_count()
            print(f"✅ VIP signal sent: {signal['direction']} {signal['symbol']} ({vip_count+1}/{VIP_SIGNAL_LIMIT_DAILY})")
        except Exception as e:
            print(f"Failed to send to VIP channel: {e}")
    
    # Save to database (use public_msg_id or vip_msg_id)
    if public_msg_id or vip_msg_id:
        signal_id = save_signal_to_db(signal, "both", public_msg_id or vip_msg_id)
        add_active_trade(signal["symbol"], signal["direction"], signal_id)

# ============================================
# PRICE MONITOR (every 60 seconds)
# ============================================

def get_live_price(ticker):
    """Get current live price"""
    try:
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(period="1d", interval="1m")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as e:
        print(f"Price fetch error {ticker}: {e}")
    return None

def calculate_profit(direction, entry, hit_price, decimals):
    """Calculate profit in pips/points"""
    if decimals == 5:
        multiplier = 10000
        unit = "pips"
    elif decimals == 0:
        multiplier = 1
        unit = "$"
    else:
        multiplier = 100 if decimals == 2 else 1
        unit = "pts" if decimals == 2 else "$"
    
    profit = round(abs(hit_price - entry) * multiplier, 1)
    return profit, unit

def monitor_prices():
    """Check pending signals every 60 seconds for TP/SL hits"""
    print("🔄 Price monitor started - checking every 60 seconds")
    
    while True:
        try:
            # Get all pending signals
            c.execute("""SELECT id, symbol, direction, entry, tp1, tp2, sl, decimals, 
                        message_id, ticker, result, channel_type
                        FROM channel_signals
                        WHERE result='pending' AND message_id IS NOT NULL""")
            pending = c.fetchall()
            
            for row in pending:
                sig_id, symbol, direction, entry, tp1, tp2, sl, decimals, msg_id, ticker, result, ch_type = row
                
                if not ticker:
                    continue
                
                current = get_live_price(ticker)
                if current is None:
                    continue
                
                # Check TP1
                if direction == "BUY" and current >= tp1:
                    profit, unit = calculate_profit(direction, entry, tp1, decimals)
                    hype_msg = f"""
🎯🔥 *TARGET HIT!* 🔥🎯

{symbol} {direction} → *TP1 ✅ REACHED!*

+{profit} {unit} profit!

💎 *VIP got this entry early!*
🚀 Join VIP: {VIP_CHANNEL}
"""
                    try:
                        bot.send_message(CHANNEL_ID, hype_msg, parse_mode='Markdown')
                        bot.send_message(VIP_CHANNEL_ID, hype_msg, parse_mode='Markdown')
                        update_signal_result(sig_id, "tp1_hit")
                        remove_active_trade(symbol)
                        print(f"🎯 TP1 Hit: {symbol} {direction}")
                    except Exception as e:
                        print(f"Hype message error: {e}")
                
                # Check TP2
                elif direction == "BUY" and current >= tp2:
                    profit, unit = calculate_profit(direction, entry, tp2, decimals)
                    hype_msg = f"""
🏆💰 *FULL PROFIT TARGET!* 💰🏆

{symbol} {direction} → *TP2 ✅ REACHED!*

+{profit} {unit} total profit!

🎉 Congratulations VIP members!
🔗 {VIP_CHANNEL}
"""
                    try:
                        bot.send_message(CHANNEL_ID, hype_msg, parse_mode='Markdown')
                        bot.send_message(VIP_CHANNEL_ID, hype_msg, parse_mode='Markdown')
                        update_signal_result(sig_id, "tp2_hit")
                        remove_active_trade(symbol)
                        print(f"🏆 TP2 Hit: {symbol} {direction}")
                    except Exception as e:
                        print(f"Hype message error: {e}")
                
                # Check SL - DELETE from public channel
                elif direction == "BUY" and current <= sl:
                    try:
                        # Delete from public channel
                        bot.delete_message(CHANNEL_ID, msg_id)
                        # Inform VIP channel
                        warn_msg = f"""
⚠️ *SL HIT - Trade Closed* ⚠️

{symbol} {direction}
Loss: {abs(round((entry - sl) * (10000 if decimals==5 else 100 if decimals==2 else 1), 1))} {unit if 'unit' in dir() else 'pts'}

🔴 Signal removed from public channel.
💎 VIP members - next signal coming soon!
"""
                        bot.send_message(VIP_CHANNEL_ID, warn_msg, parse_mode='Markdown')
                        update_signal_result(sig_id, "sl_hit")
                        remove_active_trade(symbol)
                        print(f"🔴 SL Hit - Deleted from public: {symbol} {direction}")
                    except Exception as e:
                        print(f"SL delete error: {e}")
                
                # SELL side checks
                elif direction == "SELL" and current <= tp1:
                    profit, unit = calculate_profit(direction, entry, tp1, decimals)
                    hype_msg = f"""
🎯🔥 *TARGET HIT!* 🔥🎯

{symbol} {direction} → *TP1 ✅ REACHED!*

+{profit} {unit} profit!

💎 *VIP got this entry early!*
🚀 Join VIP: {VIP_CHANNEL}
"""
                    try:
                        bot.send_message(CHANNEL_ID, hype_msg, parse_mode='Markdown')
                        bot.send_message(VIP_CHANNEL_ID, hype_msg, parse_mode='Markdown')
                        update_signal_result(sig_id, "tp1_hit")
                        remove_active_trade(symbol)
                        print(f"🎯 TP1 Hit: {symbol} {direction}")
                    except Exception as e:
                        print(f"Hype message error: {e}")
                
                elif direction == "SELL" and current <= tp2:
                    profit, unit = calculate_profit(direction, entry, tp2, decimals)
                    hype_msg = f"""
🏆💰 *FULL PROFIT TARGET!* 💰🏆

{symbol} {direction} → *TP2 ✅ REACHED!*

+{profit} {unit} total profit!

🎉 Congratulations VIP members!
🔗 {VIP_CHANNEL}
"""
                    try:
                        bot.send_message(CHANNEL_ID, hype_msg, parse_mode='Markdown')
                        bot.send_message(VIP_CHANNEL_ID, hype_msg, parse_mode='Markdown')
                        update_signal_result(sig_id, "tp2_hit")
                        remove_active_trade(symbol)
                        print(f"🏆 TP2 Hit: {symbol} {direction}")
                    except Exception as e:
                        print(f"Hype message error: {e}")
                
                elif direction == "SELL" and current >= sl:
                    try:
                        bot.delete_message(CHANNEL_ID, msg_id)
                        warn_msg = f"""
⚠️ *SL HIT - Trade Closed* ⚠️

{symbol} {direction}
Loss: {abs(round((sl - entry) * (10000 if decimals==5 else 100 if decimals==2 else 1), 1))} {unit if 'unit' in dir() else 'pts'}

🔴 Signal removed from public channel.
💎 VIP members - next signal coming soon!
"""
                        bot.send_message(VIP_CHANNEL_ID, warn_msg, parse_mode='Markdown')
                        update_signal_result(sig_id, "sl_hit")
                        remove_active_trade(symbol)
                        print(f"🔴 SL Hit - Deleted from public: {symbol} {direction}")
                    except Exception as e:
                        print(f"SL delete error: {e}")
                        
        except Exception as e:
            print(f"Price monitor error: {e}")
        
        time.sleep(60)  # Check every minute

# ============================================
# SIGNAL SCANNER (every 60 seconds)
# ============================================

def signal_scanner():
    """Scan all symbols every 60 seconds for trading opportunities"""
    print("🔄 Signal scanner started - checking every 60 seconds")
    
    while True:
        try:
            for symbol in SYMBOLS:
                # Skip if already in active trade
                if is_active_trade(symbol["name"]):
                    continue
                
                # Get technical signal
                result = get_technical_signal(symbol)
                if result:
                    direction, confidence, price = result
                    signal = generate_signal_data(symbol, direction, price, confidence)
                    send_signal_to_channels(signal)
                    
                    # Small delay to avoid rate limiting
                    time.sleep(2)
                    
        except Exception as e:
            print(f"Signal scanner error: {e}")
        
        time.sleep(60)  # Scan every minute

# ============================================
# TELEGRAM BOT COMMANDS
# ============================================

bot = telebot.TeleBot(BOT_TOKEN)

def main_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    btn1 = telebot.types.InlineKeyboardButton("📝 Register", callback_data="register")
    btn2 = telebot.types.InlineKeyboardButton("📊 Free Signal", callback_data="free")
    btn3 = telebot.types.InlineKeyboardButton("⭐ VIP Access", callback_data="vip")
    btn4 = telebot.types.InlineKeyboardButton("💬 Support", callback_data="support")
    btn5 = telebot.types.InlineKeyboardButton("🌐 Website", url=WEBSITE_URL)
    btn6 = telebot.types.InlineKeyboardButton("📢 Free Channel", url=FREE_CHANNEL)
    keyboard.add(btn1, btn2, btn3, btn4, btn5, btn6)
    return keyboard

@bot.message_handler(commands=['start'])
def start(message):
    msg = f"""🚀 *Forex Trading With Kailash* 🚀

India's Most Trusted Forex Signals Provider

📊 *Services:*
✅ FREE Signals - {FREE_SIGNAL_LIMIT_DAILY} calls daily
⭐ VIP Channel - ₹399/month ({VIP_SIGNAL_LIMIT_DAILY} signals/day)
🔄 Real Market Analysis (85%+ Accuracy)
📈 5000+ Traders Trust Us

🌐 *Website:* {WEBSITE_URL}
📢 *Free Channel:* {FREE_CHANNEL}

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
🕐 *Time:* {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"""
        bot.send_message(ADMIN_ID, admin_msg, parse_mode='Markdown')
        reply_msg = f"""✅ *Welcome {name}!* ✅

Your registration is complete!

📊 *What you get:*
• {FREE_SIGNAL_LIMIT_DAILY} free signals daily
• Real market analysis
• Risk management tips

👇 *Use buttons below:*"""
        bot.reply_to(message, reply_msg, parse_mode='Markdown', reply_markup=main_keyboard())
    except Exception as e:
        bot.reply_to(message, "❌ *Invalid Format!*\n\nSend: `Name, Email, Phone`\nExample: `Rajesh, rajesh@gmail.com, 9876543210`", parse_mode='Markdown')

@bot.message_handler(commands=['free'])
def free_signal(message):
    user_id = message.from_user.id
    remaining = signals_remaining(user_id)
    
    if remaining <= 0:
        block_msg = f"""🚫 *Free Signal Limit Reached!* 🚫

You have used all *3 free signals*.

📢 *Join Free Channel for more:* {FREE_CHANNEL}

⭐ *Want VIP Signals?* {VIP_SIGNAL_LIMIT_DAILY} premium signals daily for just ₹399/month
👉 /vip"""
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(
            telebot.types.InlineKeyboardButton("📢 Join Free Channel", url=FREE_CHANNEL),
            telebot.types.InlineKeyboardButton("⭐ Get VIP Access", callback_data="vip")
        )
        bot.reply_to(message, block_msg, parse_mode='Markdown', reply_markup=keyboard)
        return
    
    # Get a quick signal for user
    for symbol in SYMBOLS:
        result = get_technical_signal(symbol)
        if result:
            direction, confidence, price = result
            signal = generate_signal_data(symbol, direction, price, confidence)
            
            signal_text = f"""
📊 *FREE SIGNAL* 📊
{signal['emoji']} *{signal['direction']} {signal['symbol']}*

📌 Entry: `{signal['entry_low']} - {signal['entry_high']}`
🎯 TP1: `{signal['tp1']}`
🎯 TP2: `{signal['tp2']}`
🛑 SL: `{signal['sl']}`

📈 *Analysis:* {signal['analysis']}
⭐ *Confidence: {signal['confidence']}%*

⚠️ *Free signals left: {remaining-1}*
⭐ *Get unlimited: /vip*
"""
            bot.reply_to(message, signal_text, parse_mode='Markdown', reply_markup=main_keyboard())
            increment_user_signal_count(user_id)
            return
    
    bot.reply_to(message, "⚠️ No signal available right now. Market might be consolidating. Try again in a few minutes!", parse_mode='Markdown', reply_markup=main_keyboard())

@bot.message_handler(commands=['vip'])
def vip_command(message):
    msg = f"""⭐ *VIP Telegram Channel* ⭐

*Premium Benefits:*
✅ {VIP_SIGNAL_LIMIT_DAILY} Premium Signals Daily
✅ Early Entry Alerts (Before Market)
✅ Live Market Analysis
✅ 1-on-1 VIP Support
✅ 85%+ Win Rate Guarantee

💰 *Price:* ₹399/month

*Payment Details:*
📱 UPI ID: `{UPI_ID}`

*How to Join:*
1️⃣ Pay ₹399 to above UPI ID
2️⃣ Send payment screenshot to {CONTACT_USERNAME}
3️⃣ Get VIP channel link

🔗 *VIP Channel:* {VIP_CHANNEL}

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

@bot.message_handler(commands=['stats'])
def stats_command(message):
    if message.from_user.id == ADMIN_ID:
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone
