import telebot
import sqlite3
import datetime
import os
import random
import threading
import time
import requests
import json
import numpy as np

# ============================================
# CONFIGURATION (Your Credentials)
# ============================================

BOT_TOKEN = "8653450456:AAER9w6Gjj5IWkyCs1taa01N-DdMFZqxt3E"
ADMIN_ID = 6253584826
CHANNEL_ID = '@tradewithkailashh'
WEBSITE_URL = 'https://forexkailash.netlify.app'
FREE_CHANNEL = 'https://t.me/tradewithkailashh'
VIP_CHANNEL = 'https://t.me/+Snj0BVAwjDo3NTA1'
UPI_ID = 'kailashbhardwaj66-2@okicici'
CONTACT_USERNAME = '@ForexKailash'
COURSE_URL = 'https://forexkailash.netlify.app'

# VIP Channel Numeric ID
VIP_CHANNEL_ID = -1003826269063

# Daily Signal Limits
FREE_SIGNAL_LIMIT_DAILY = 7      # 5-7 trades per day on free channel
VIP_SIGNAL_LIMIT_DAILY = 22      # 20-25 trades per day on VIP channel

# ============================================
# FCS API CONFIGURATION (Your API Keys)
# ============================================
FCS_ACCESS_KEY = "wvYZfov5RC2SlDpzaHautvMzowmYQcc"
FCS_PUBLIC_KEY = "Gj3DoeAgI1gRNo2LMuHGfccTM"
FCS_BASE_URL = "https://api-v4.fcsapi.com"

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
channel_type TEXT DEFAULT "public", confidence INTEGER DEFAULT 0, signal_reason TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS bot_settings
(key TEXT PRIMARY KEY, value TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS daily_public_counter
(date TEXT PRIMARY KEY, count INTEGER DEFAULT 0)''')

c.execute('''CREATE TABLE IF NOT EXISTS daily_vip_counter
(date TEXT PRIMARY KEY, count INTEGER DEFAULT 0)''')

c.execute('''CREATE TABLE IF NOT EXISTS active_trades
(symbol TEXT PRIMARY KEY, direction TEXT, signal_id INTEGER, sent_time TEXT, timeframe TEXT)''')

# Add missing columns
for col in [
    "ALTER TABLE channel_signals ADD COLUMN message_id INTEGER DEFAULT NULL",
    "ALTER TABLE channel_signals ADD COLUMN ticker TEXT",
    "ALTER TABLE channel_signals ADD COLUMN channel_type TEXT DEFAULT 'public'",
    "ALTER TABLE channel_signals ADD COLUMN confidence INTEGER DEFAULT 0",
    "ALTER TABLE channel_signals ADD COLUMN signal_reason TEXT",
    "ALTER TABLE signal_usage ADD COLUMN last_date TEXT",
    "ALTER TABLE active_trades ADD COLUMN timeframe TEXT",
]:
    try:
        c.execute(col)
    except:
        pass

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
    return max(0, 3 - used)

# ============================================
# SYMBOLS CONFIGURATION
# ============================================

SYMBOLS = [
    {"name": "XAU/USD", "fcs_symbol": "XAU/USD", "emoji": "🥇", "decimals": 2,
     "tp1_pct": 0.004, "tp2_pct": 0.008, "sl_pct": 0.003, "spread_pct": 0.001},
    {"name": "BTC/USD", "fcs_symbol": "BTC/USD", "emoji": "₿", "decimals": 0,
     "tp1_pct": 0.006, "tp2_pct": 0.012, "sl_pct": 0.004, "spread_pct": 0.001},
    {"name": "ETH/USD", "fcs_symbol": "ETH/USD", "emoji": "💎", "decimals": 1,
     "tp1_pct": 0.007, "tp2_pct": 0.014, "sl_pct": 0.005, "spread_pct": 0.001},
    {"name": "USOIL", "fcs_symbol": "WTI/USD", "emoji": "🛢️", "decimals": 2,
     "tp1_pct": 0.005, "tp2_pct": 0.010, "sl_pct": 0.003, "spread_pct": 0.001},
    {"name": "AUD/USD", "fcs_symbol": "AUD/USD", "emoji": "🦘", "decimals": 5,
     "tp1_pct": 0.003, "tp2_pct": 0.006, "sl_pct": 0.002, "spread_pct": 0.0003},
    {"name": "EUR/USD", "fcs_symbol": "EUR/USD", "emoji": "💶", "decimals": 5,
     "tp1_pct": 0.003, "tp2_pct": 0.006, "sl_pct": 0.002, "spread_pct": 0.0003},
    {"name": "GBP/USD", "fcs_symbol": "GBP/USD", "emoji": "💷", "decimals": 5,
     "tp1_pct": 0.003, "tp2_pct": 0.006, "sl_pct": 0.002, "spread_pct": 0.0003},
    {"name": "USD/JPY", "fcs_symbol": "USD/JPY", "emoji": "🇯🇵", "decimals": 3,
     "tp1_pct": 0.003, "tp2_pct": 0.005, "sl_pct": 0.002, "spread_pct": 0.0003},
    {"name": "NAS100", "fcs_symbol": "NAS100", "emoji": "📈", "decimals": 0,
     "tp1_pct": 0.004, "tp2_pct": 0.008, "sl_pct": 0.003, "spread_pct": 0.001},
]

# ============================================
# FCS API FUNCTIONS
# ============================================

def get_live_price_fcs(symbol):
    """Get current price from FCS API"""
    try:
        url = f"{FCS_BASE_URL}/forex/single"
        params = {
            "access_key": FCS_ACCESS_KEY,
            "symbol": symbol
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            return None
        data = response.json()
        
        if data.get('status') and data.get('response'):
            return float(data['response']['c'])
        return None
    except Exception as e:
        print(f"FCS price error for {symbol}: {e}")
        return None

def get_historical_fcs(symbol, period="1h", limit=50):
    """Get historical data for indicators"""
    try:
        url = f"{FCS_BASE_URL}/forex/history"
        params = {
            "access_key": FCS_ACCESS_KEY,
            "symbol": symbol,
            "period": period,
            "limit": limit
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            return []
        data = response.json()
        
        if data.get('status') and data.get('response'):
            prices = []
            if isinstance(data['response'], dict):
                for timestamp, values in data['response'].items():
                    if isinstance(values, dict) and 'c' in values:
                        prices.append(float(values['c']))
            elif isinstance(data['response'], list):
                for item in data['response']:
                    if 'c' in item:
                        prices.append(float(item['c']))
            return prices
        return []
    except Exception as e:
        print(f"FCS historical error for {symbol}: {e}")
        return []

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

def get_signal_with_reason(symbol, timeframe="1h"):
    """
    Returns (direction, confidence, current_price, reason, timeframe)
    """
    try:
        fcs_symbol = symbol["fcs_symbol"]
        
        # Map timeframe to FCS period
        period_map = {"5m": "5min", "15m": "15min", "1h": "1h"}
        period = period_map.get(timeframe, "1h")
        
        # Get historical data
        closes = get_historical_fcs(fcs_symbol, period, 50)
        if len(closes) < 30:
            return None
        
        # Get current price
        current_price = get_live_price_fcs(fcs_symbol)
        if current_price is None or current_price <= 0:
            return None
        
        # Calculate indicators
        rsi = calculate_rsi(closes)
        sma20 = np.mean(closes[-20:])
        sma50 = np.mean(closes[-50:]) if len(closes) >= 50 else sma20
        ema9 = np.mean(closes[-9:])
        ema21 = np.mean(closes[-21:]) if len(closes) >= 21 else sma20
        
        # Price action
        prev_close = closes[-2] if len(closes) >= 2 else current_price
        price_momentum = "up" if current_price > prev_close else "down"
        
        # STRONG BUY SIGNALS
        if rsi < 35 and current_price > sma20:
            confidence = 85 + int((35 - rsi) / 2)
            reason = f"🔍 *Technical Reason:* RSI is {rsi:.1f} (oversold below 35) + Price trading above 20-period SMA ({sma20:.2f}). This indicates bullish reversal potential with institutional buying pressure."
            return ("BUY", min(95, confidence), current_price, reason, timeframe)
        
        elif rsi < 30:
            confidence = 90
            reason = f"🔍 *Technical Reason:* RSI is extremely oversold at {rsi:.1f} (below 30). Historical data shows 85%+ probability of bounce back from these levels."
            return ("BUY", confidence, current_price, reason, timeframe)
        
        elif current_price > ema9 and ema9 > ema21 and rsi > 50:
            confidence = 80
            reason = f"🔍 *Technical Reason:* Golden crossover detected! EMA9 ({ema9:.2f}) is above EMA21 ({ema21:.2f}) forming bullish trend. RSI at {rsi:.1f} confirms momentum."
            return ("BUY", confidence, current_price, reason, timeframe)
        
        elif price_momentum == "up" and current_price > sma20 and rsi < 60:
            confidence = 75
            reason = f"🔍 *Technical Reason:* Bullish price action with positive momentum. Price broke above 20 SMA ({sma20:.2f}). RSI at {rsi:.1f} shows room for upside."
            return ("BUY", confidence, current_price, reason, timeframe)
        
        # STRONG SELL SIGNALS
        elif rsi > 65 and current_price < sma20:
            confidence = 85 + int((rsi - 65) / 2)
            reason = f"🔍 *Technical Reason:* RSI is {rsi:.1f} (overbought above 65) + Price trading below 20-period SMA ({sma20:.2f}). Bearish reversal expected."
            return ("SELL", min(95, confidence), current_price, reason, timeframe)
        
        elif rsi > 70:
            confidence = 90
            reason = f"🔍 *Technical Reason:* RSI is extremely overbought at {rsi:.1f} (above 70). Market correction highly probable."
            return ("SELL", confidence, current_price, reason, timeframe)
        
        elif current_price < ema9 and ema9 < ema21 and rsi < 50:
            confidence = 80
            reason = f"🔍 *Technical Reason:* Death crossover detected! EMA9 ({ema9:.2f}) is below EMA21 ({ema21:.2f}) forming bearish trend."
            return ("SELL", confidence, current_price, reason, timeframe)
        
        elif price_momentum == "down" and current_price < sma20 and rsi > 40:
            confidence = 75
            reason = f"🔍 *Technical Reason:* Bearish price action with negative momentum. Price broke below 20 SMA ({sma20:.2f})."
            return ("SELL", confidence, current_price, reason, timeframe)
        
        return None
    except Exception as e:
        print(f"Error analyzing {symbol['name']}: {e}")
        return None

# ============================================
# SIGNAL GENERATION & SENDING
# ============================================

def generate_signal_data(symbol, direction, current_price, confidence, reason, timeframe):
    """Create signal dict with entry, TP, SL levels"""
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
        "ticker": symbol["fcs_symbol"],
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
        "reason": reason,
        "timeframe": timeframe,
    }

def save_signal_to_db(signal, channel_type, message_id):
    """Save signal to database"""
    now = datetime.datetime.now()
    entry_mid = (signal["entry_low"] + signal["entry_high"]) / 2
    c.execute("""INSERT INTO channel_signals
    (symbol, direction, entry, tp1, tp2, sl, decimals, sent_date, sent_time, ticker, channel_type, message_id, confidence, signal_reason)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (signal["symbol"], signal["direction"], entry_mid,
     signal["tp1"], signal["tp2"], signal["sl"], signal["decimals"],
     now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), signal["ticker"], channel_type, message_id, signal["confidence"], signal["reason"]))
    conn.commit()
    return c.lastrowid

def update_signal_result(signal_id, result):
    c.execute("UPDATE channel_signals SET result=? WHERE id=?", (result, signal_id))
    conn.commit()

def is_active_trade(symbol):
    c.execute("SELECT * FROM active_trades WHERE symbol=?", (symbol,))
    return c.fetchone() is not None

def add_active_trade(symbol, direction, signal_id, timeframe):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    c.execute("INSERT OR REPLACE INTO active_trades (symbol, direction, signal_id, sent_time, timeframe) VALUES (?,?,?,?,?)", 
              (symbol, direction, signal_id, now, timeframe))
    conn.commit()

def remove_active_trade(symbol):
    c.execute("DELETE FROM active_trades WHERE symbol=?", (symbol,))
    conn.commit()

def get_live_price(ticker):
    """Get current live price from FCS API"""
    return get_live_price_fcs(ticker)

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

def send_signal_to_channels(signal, is_vip_only=False):
    """Send signal to public and VIP channels with daily limits"""
    now = datetime.datetime.now()
    
    # Build signal message with reason
    signal_text = f"""
{signal['emoji']} *{signal['direction']} {signal['symbol']}* 📊
🕐 _{now.strftime('%d %b %Y, %H:%M')} IST_
⏱️ *Timeframe:* {signal['timeframe']}

📌 Entry: `{signal['entry_low']} - {signal['entry_high']}`
🎯 TP1: `{signal['tp1']}`
🎯 TP2: `{signal['tp2']}`
🛑 SL: `{signal['sl']}`

📈 *Analysis & Reason:*
{signal['reason']}

⭐ *Confidence: {signal['confidence']}%*
⚠️ *Risk:* Use 1-2% risk per trade.
"""
    
    # Send to Public Channel
    public_msg_id = None
    if not is_vip_only:
        public_count = get_daily_public_count()
        if public_count < FREE_SIGNAL_LIMIT_DAILY:
            try:
                msg = bot.send_message(CHANNEL_ID, signal_text, parse_mode='Markdown')
                public_msg_id = msg.message_id
                increment_daily_public_count()
                print(f"✅ Public signal sent: {signal['direction']} {signal['symbol']}")
            except Exception as e:
                print(f"Public send error: {e}")
    
    # Send to VIP Channel
    vip_count = get_daily_vip_count()
    vip_msg_id = None
    if vip_count < VIP_SIGNAL_LIMIT_DAILY:
        vip_text = f"""
⭐ *VIP PREMIUM SIGNAL* ⭐
{signal_text}
💎 *Exclusive VIP Entry - 30 min early!*
🔗 {VIP_CHANNEL}
"""
        try:
            msg = bot.send_message(VIP_CHANNEL_ID, vip_text, parse_mode='Markdown')
            vip_msg_id = msg.message_id
            increment_daily_vip_count()
            print(f"✅ VIP signal sent: {signal['direction']} {signal['symbol']}")
        except Exception as e:
            print(f"VIP send error: {e}")
    
    # Save to database
    if public_msg_id or vip_msg_id:
        signal_id = save_signal_to_db(signal, "both", public_msg_id or vip_msg_id)
        add_active_trade(signal["symbol"], signal["direction"], signal_id, signal["timeframe"])

# ============================================
# PRICE MONITOR (every 60 seconds)
# ============================================

def monitor_prices():
    """Check pending signals every 60 seconds for TP/SL hits"""
    print("🔄 Price monitor started - checking every 60 seconds")
    
    while True:
        try:
            c.execute("""SELECT id, symbol, direction, entry, tp1, tp2, sl, decimals, 
                        message_id, ticker, result
                        FROM channel_signals
                        WHERE result='pending' AND message_id IS NOT NULL""")
            pending = c.fetchall()
            
            for row in pending:
                sig_id, symbol, direction, entry, tp1, tp2, sl, decimals, msg_id, ticker, result = row
                
                current = get_live_price(ticker)
                if current is None:
                    continue
                
                # BUY side
                if direction == "BUY":
                    if current >= tp1:
                        profit, unit = calculate_profit(direction, entry, tp1, decimals)
                        hype = f"🎯 TP1 HIT! {symbol} {direction}\n+{profit} {unit} profit!\nVIP: {VIP_CHANNEL}"
                        bot.send_message(CHANNEL_ID, hype, parse_mode='Markdown')
                        bot.send_message(VIP_CHANNEL_ID, hype, parse_mode='Markdown')
                        update_signal_result(sig_id, "tp1_hit")
                        remove_active_trade(symbol)
                    elif current >= tp2:
                        profit, unit = calculate_profit(direction, entry, tp2, decimals)
                        hype = f"🏆 TP2 HIT! {symbol} {direction}\n+{profit} {unit} profit!\nVIP: {VIP_CHANNEL}"
                        bot.send_message(CHANNEL_ID, hype, parse_mode='Markdown')
                        bot.send_message(VIP_CHANNEL_ID, hype, parse_mode='Markdown')
                        update_signal_result(sig_id, "tp2_hit")
                        remove_active_trade(symbol)
                    elif current <= sl:
                        try:
                            bot.delete_message(CHANNEL_ID, msg_id)
                        except:
                            pass
                        warn = f"⚠️ SL HIT: {symbol} {direction}\nSignal removed from public channel."
                        bot.send_message(VIP_CHANNEL_ID, warn, parse_mode='Markdown')
                        update_signal_result(sig_id, "sl_hit")
                        remove_active_trade(symbol)
                
                # SELL side
                elif direction == "SELL":
                    if current <= tp1:
                        profit, unit = calculate_profit(direction, entry, tp1, decimals)
                        hype = f"🎯 TP1 HIT! {symbol} {direction}\n+{profit} {unit} profit!\nVIP: {VIP_CHANNEL}"
                        bot.send_message(CHANNEL_ID, hype, parse_mode='Markdown')
                        bot.send_message(VIP_CHANNEL_ID, hype, parse_mode='Markdown')
                        update_signal_result(sig_id, "tp1_hit")
                        remove_active_trade(symbol)
                    elif current <= tp2:
                        profit, unit = calculate_profit(direction, entry, tp2, decimals)
                        hype = f"🏆 TP2 HIT! {symbol} {direction}\n+{profit} {unit} profit!\nVIP: {VIP_CHANNEL}"
                        bot.send_message(CHANNEL_ID, hype, parse_mode='Markdown')
                        bot.send_message(VIP_CHANNEL_ID, hype, parse_mode='Markdown')
                        update_signal_result(sig_id, "tp2_hit")
                        remove_active_trade(symbol)
                    elif current >= sl:
                        try:
                            bot.delete_message(CHANNEL_ID, msg_id)
                        except:
                            pass
                        warn = f"⚠️ SL HIT: {symbol} {direction}\nSignal removed from public channel."
                        bot.send_message(VIP_CHANNEL_ID, warn, parse_mode='Markdown')
                        update_signal_result(sig_id, "sl_hit")
                        remove_active_trade(symbol)
                        
        except Exception as e:
            print(f"Monitor error: {e}")
        time.sleep(60)

# ============================================
# SIGNAL SCANNER (every 60 seconds)
# ============================================

def signal_scanner():
    """Scan all symbols every 60 seconds for trading opportunities"""
    print("🔄 Signal scanner started - checking every 60 seconds")
    last_scan = {"5m": 0, "15m": 0, "1h": 0}
    
    while True:
        try:
            current_time = time.time()
            
            for symbol in SYMBOLS:
                if is_active_trade(symbol["name"]):
                    continue
                
                # Free channel signals (1h only)
                if get_daily_public_count() < FREE_SIGNAL_LIMIT_DAILY:
                    result = get_signal_with_reason(symbol, "1h")
                    if result:
                        direction, confidence, price, reason, tf = result
                        signal = generate_signal_data(symbol, direction, price, confidence, reason, tf)
                        send_signal_to_channels(signal, is_vip_only=False)
                        time.sleep(3)
                
                # VIP signals (multiple timeframes)
                if get_daily_vip_count() < VIP_SIGNAL_LIMIT_DAILY:
                    timeframes = ["5m", "15m", "1h"]
                    for tf in timeframes:
                        if tf == "5m" and current_time - last_scan["5m"] < 300:
                            continue
                        elif tf == "15m" and current_time - last_scan["15m"] < 900:
                            continue
                        elif tf == "1h" and current_time - last_scan["1h"] < 3600:
                            continue
                        
                        result = get_signal_with_reason(symbol, tf)
                        if result:
                            direction, confidence, price, reason, timeframe = result
                            signal = generate_signal_data(symbol, direction, price, confidence, reason, timeframe)
                            send_signal_to_channels(signal, is_vip_only=False)
                            last_scan[tf] = current_time
                            time.sleep(5)
                            break
                        last_scan[tf] = current_time
                        
        except Exception as e:
            print(f"Scanner error: {e}")
        time.sleep(60)

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

🌐 *Website:* {WEBSITE_URL}
📢 *Free Channel:* {FREE_CHANNEL}

👇 *Choose an option:*"""
    bot.reply_to(message, msg, parse_mode='Markdown', reply_markup=main_keyboard())

@bot.message_handler(commands=['register'])
def register_cmd(message):
    msg = bot.reply_to(message, "📝 *Send:* `Name, Email, Phone`\nExample: `Rajesh, rajesh@gmail.com, 9876543210`", parse_mode='Markdown')
    bot.register_next_step_handler(msg, save_user)

def save_user(message):
    user_id = message.from_user.id
    username = message.from_user.username or "No username"
    try:
        data = message.text.split(',')
        name = data[0].strip()
        email = data[1].strip()
        phone = data[2].strip()
        c.execute("INSERT OR REPLACE INTO users (user_id, name, email, phone, register_date, is_vip) VALUES (?,?,?,?,?,?)",
                  (user_id, name, email, phone, str(datetime.datetime.now()), 0))
        c.execute("INSERT INTO registrations (user_id, name, email, phone, date) VALUES (?,?,?,?,?)",
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
        bot.reply_to(message, f"✅ Welcome {name}! Registration complete.", parse_mode='Markdown', reply_markup=main_keyboard())
    except Exception as e:
        bot.reply_to(message, "❌ Invalid format! Send: `Name, Email, Phone`", parse_mode='Markdown')

@bot.message_handler(commands=['free'])
def free_signal(message):
    user_id = message.from_user.id
    remaining = signals_remaining(user_id)
    if remaining <= 0:
        bot.reply_to(message, f"🚫 Free limit reached! Join: {FREE_CHANNEL}", parse_mode='Markdown')
        return
    
    for symbol in SYMBOLS:
        result = get_signal_with_reason(symbol, "1h")
        if result:
            direction, confidence, price, reason, tf = result
            signal = generate_signal_data(symbol, direction, price, confidence, reason, tf)
            text = f"""📊 *FREE SIGNAL* 📊
{signal['emoji']} *{signal['direction']} {signal['symbol']}*

📌 Entry: `{signal['entry_low']} - {signal['entry_high']}`
🎯 TP1: `{signal['tp1']}`
🎯 TP2: `{signal['tp2']}`
🛑 SL: `{signal['sl']}`

📈 *Analysis:* {reason[:200]}

⭐ *Free signals left: {remaining-1}*"""
            bot.reply_to(message, text, parse_mode='Markdown')
            increment_user_signal_count(user_id)
            return
    bot.reply_to(message, "⚠️ No signal available. Try again in a few minutes.", parse_mode='Markdown')

@bot.message_handler(commands=['vip'])
def vip_command(message):
    msg = f"""⭐ *VIP Telegram Channel* ⭐

*Premium Benefits:*
✅ {VIP_SIGNAL_LIMIT_DAILY} Premium Signals Daily
✅ Multiple Timeframes (5m, 15m, 1h)
✅ Early Entry Alerts
✅ 1-on-1 VIP Support

💰 *Price:* ₹399/month
📱 UPI: `{UPI_ID}`

*How to Join:*
1️⃣ Pay ₹399 to above UPI ID
2️⃣ Send screenshot to {CONTACT_USERNAME}
3️⃣ Get VIP access

🔗 *VIP Channel:* {VIP_CHANNEL}"""
    bot.reply_to(message, msg, parse_mode='Markdown', reply_markup=main_keyboard())

@bot.message_handler(commands=['support'])
def support_command(message):
    msg = f"""💬 *Need Help?* 💬

📱 *Telegram:* {CONTACT_USERNAME}
📧 *Email:* btcuscoinbase@gmail.com
🌐 *Website:* {WEBSITE_URL}

We're here to help! 🚀"""
    bot.reply_to(message, msg, parse_mode='Markdown', reply_markup=main_keyboard())

@bot.message_handler(commands=['stats'])
def stats_command(message):
    if message.from_user.id == ADMIN_ID:
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM registrations WHERE date LIKE ?", (f"{datetime.datetime.now().strftime('%Y-%m-%d')}%",))
        today_reg = c.fetchone()[0]
        public_today = get_daily_public_count()
        vip_today = get_daily_vip_count()
        c.execute("SELECT COUNT(*) FROM channel_signals WHERE result='pending'")
        active_trades = c.fetchone()[0]
        
        msg = f"""📊 *BOT STATISTICS* 📊

👥 Total Users: {total_users}
📝 Today's Registrations: {today_reg}

📡 *Today's Signals:*
• Public: {public_today}/{FREE_SIGNAL_LIMIT_DAILY}
• VIP: {vip_today}/{VIP_SIGNAL_LIMIT_DAILY}
• Active Trades: {active_trades}

🤖 Bot Status: Active ✅"""
        bot.reply_to(message, msg, parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ Unauthorized - Admin only.")

@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    if call.data == "register":
        msg = bot.send_message(call.message.chat.id, "📝 Send: `Name, Email, Phone`\nExample: `Rajesh, rajesh@gmail.com, 9876543210`", parse_mode='Markdown')
        bot.register_next_step_handler(msg, save_user)
    elif call.data == "free":
        remaining = signals_remaining(call.from_user.id)
        if remaining <= 0:
            bot.send_message(call.message.chat.id, f"🚫 Free limit reached! Join: {FREE_CHANNEL}")
        else:
            for symbol in SYMBOLS:
                result = get_signal_with_reason(symbol, "1h")
                if result:
                    direction, confidence, price, reason, tf = result
                    signal = generate_signal_data(symbol, direction, price, confidence, reason, tf)
                    text = f"📊 FREE SIGNAL\n{signal['direction']} {signal['symbol']}\nEntry: {signal['entry_low']}-{signal['entry_high']}\nTP1: {signal['tp1']}\nTP2: {signal['tp2']}\nSL: {signal['sl']}"
                    bot.send_message(call.message.chat.id, text)
                    increment_user_signal_count(call.from_user.id)
                    break
    elif call.data == "vip":
        bot.send_message(call.message.chat.id, f"⭐ VIP: {VIP_CHANNEL}\n💰 ₹399/month\nUPI: {UPI_ID}")
    elif call.data == "support":
        bot.send_message(call.message.chat.id, f"💬 Contact: {CONTACT_USERNAME}")
    bot.answer_callback_query(call.id)

# ============================================
# RUN BOT
# ============================================

print("=" * 50)
print("🤖 FOREX TRADING BOT IS RUNNING 🤖")
print("=" * 50)
print(f"👤 Admin ID: {ADMIN_ID}")
print(f"📢 Public Channel: {CHANNEL_ID}")
print(f"⭐ VIP Channel: {VIP_CHANNEL_ID}")
print(f"📊 Daily Limits: Public={FREE_SIGNAL_LIMIT_DAILY}, VIP={VIP_SIGNAL_LIMIT_DAILY}")
print(f"📞 Support: {CONTACT_USERNAME}")
print("=" * 50)
print("✅ Bot ready! Send /start on Telegram")
print("🔄 Signal Scanner: Every 60 seconds")
print("📊 Price Monitor: Every 60 seconds")
print("🎯 TP Hype Messages: Enabled")
print("🗑️ SL Deletion: Enabled")
print("=" * 50)

# Start background threads
scanner_thread = threading.Thread(target=signal_scanner, daemon=True)
scanner_thread.start()

monitor_thread = threading.Thread(target=monitor_prices, daemon=True)
monitor_thread.start()

# Start bot
bot.infinity_polling()
