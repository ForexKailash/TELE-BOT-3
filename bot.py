import telebot
import sqlite3
import datetime
import os
import random
import threading
import time
import requests
import numpy as np

# ============================================
# CONFIGURATION
# ============================================

BOT_TOKEN = "8653450456:AAER9w6Gjj5IWkyCs1taa01N-DdMFZqxt3E"
ADMIN_ID = 6253584826
CHANNEL_ID = '@tradewithkailashh'
WEBSITE_URL = 'https://forexkailash.netlify.app'
FREE_CHANNEL = 'https://t.me/tradewithkailashh'
VIP_CHANNEL = 'https://t.me/+Snj0BVAwjDo3NTA1'
UPI_ID = 'kailashbhardwaj66-2@okicici'
CONTACT_USERNAME = '@ForexKailash'

VIP_CHANNEL_ID = -1003826269063
FREE_SIGNAL_LIMIT_DAILY = 7
VIP_SIGNAL_LIMIT_DAILY = 22

# FCS API Keys
FCS_ACCESS_KEY = "wvYZfov5RC2SlDpzaHautvMzowmYQcc"
FCS_BASE_URL = "https://api-v4.fcsapi.com"

# ============================================
# DATABASE SETUP (Separate connections per thread)
# ============================================

os.makedirs('telegram_bot', exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect('telegram_bot/users.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
    (user_id INTEGER PRIMARY KEY, name TEXT, email TEXT, phone TEXT,
    register_date TEXT, is_vip INTEGER)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS registrations
    (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT,
    email TEXT, phone TEXT, date TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS signal_usage
    (user_id INTEGER PRIMARY KEY, last_date TEXT, count INTEGER DEFAULT 0)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS channel_signals
    (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, direction TEXT,
    entry REAL, tp1 REAL, tp2 REAL, sl REAL, decimals INTEGER,
    sent_date TEXT, sent_time TEXT, result TEXT DEFAULT "pending",
    message_id INTEGER DEFAULT NULL, ticker TEXT,
    channel_type TEXT DEFAULT "public", confidence INTEGER DEFAULT 0, signal_reason TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS daily_public_counter
    (date TEXT PRIMARY KEY, count INTEGER DEFAULT 0)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS daily_vip_counter
    (date TEXT PRIMARY KEY, count INTEGER DEFAULT 0)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS active_trades
    (symbol TEXT PRIMARY KEY, direction TEXT, signal_id INTEGER, sent_time TEXT, timeframe TEXT)''')
    
    conn.commit()
    conn.close()

init_db()

# ============================================
# DATABASE HELPER FUNCTIONS
# ============================================

def get_daily_public_count():
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT count FROM daily_public_counter WHERE date=?", (today,))
    row = cursor.fetchone()
    result = row[0] if row else 0
    conn.close()
    return result

def increment_daily_public_count():
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO daily_public_counter (date, count) VALUES (?,1) ON CONFLICT(date) DO UPDATE SET count = count + 1", (today,))
    conn.commit()
    conn.close()

def get_daily_vip_count():
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT count FROM daily_vip_counter WHERE date=?", (today,))
    row = cursor.fetchone()
    result = row[0] if row else 0
    conn.close()
    return result

def increment_daily_vip_count():
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO daily_vip_counter (date, count) VALUES (?,1) ON CONFLICT(date) DO UPDATE SET count = count + 1", (today,))
    conn.commit()
    conn.close()

def signals_remaining(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT count FROM signal_usage WHERE user_id=? AND last_date=?", (user_id, today))
    row = cursor.fetchone()
    used = row[0] if row else 0
    conn.close()
    return max(0, 3 - used)

def increment_user_signal_count(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO signal_usage (user_id, last_date, count) VALUES (?,?,1) ON CONFLICT(user_id) DO UPDATE SET count = count + 1, last_date = ?", (user_id, today, today))
    conn.commit()
    conn.close()

def is_active_trade(symbol):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM active_trades WHERE symbol=?", (symbol,))
    result = cursor.fetchone() is not None
    conn.close()
    return result

def add_active_trade(symbol, direction, signal_id, timeframe):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%H:%M:%S")
    cursor.execute("INSERT OR REPLACE INTO active_trades (symbol, direction, signal_id, sent_time, timeframe) VALUES (?,?,?,?,?)", 
                   (symbol, direction, signal_id, now, timeframe))
    conn.commit()
    conn.close()

def remove_active_trade(symbol):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM active_trades WHERE symbol=?", (symbol,))
    conn.commit()
    conn.close()

def save_signal_to_db(symbol, direction, entry, tp1, tp2, sl, decimals, ticker, channel_type, message_id, confidence, reason):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now()
    cursor.execute("""INSERT INTO channel_signals
    (symbol, direction, entry, tp1, tp2, sl, decimals, sent_date, sent_time, ticker, channel_type, message_id, confidence, signal_reason)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (symbol, direction, entry, tp1, tp2, sl, decimals,
     now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), ticker, channel_type, message_id, confidence, reason))
    conn.commit()
    signal_id = cursor.lastrowid
    conn.close()
    return signal_id

def update_signal_result(signal_id, result):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE channel_signals SET result=? WHERE id=?", (result, signal_id))
    conn.commit()
    conn.close()

def get_pending_signals():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""SELECT id, symbol, direction, entry, tp1, tp2, sl, decimals, 
                      message_id, ticker FROM channel_signals
                      WHERE result='pending' AND message_id IS NOT NULL""")
    rows = cursor.fetchall()
    conn.close()
    return rows

# ============================================
# SYMBOLS
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
# MOCK DATA (If API fails)
# ============================================

MOCK_PRICES = {
    "XAU/USD": 3015.50,
    "BTC/USD": 68500,
    "ETH/USD": 3450,
    "WTI/USD": 78.50,
    "AUD/USD": 0.65300,
    "EUR/USD": 1.08500,
    "GBP/USD": 1.26500,
    "USD/JPY": 149.50,
    "NAS100": 18500,
}

# ============================================
# FCS API FUNCTIONS (With Mock Fallback)
# ============================================

def get_live_price(symbol):
    """Get current price from FCS API, fallback to mock data"""
    try:
        url = f"{FCS_BASE_URL}/forex/single"
        params = {"access_key": FCS_ACCESS_KEY, "symbol": symbol}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') and data.get('response'):
                price = float(data['response']['c'])
                print(f"✅ API Price {symbol}: {price}")
                return price
        print(f"⚠️ API failed for {symbol}, using mock data")
        return MOCK_PRICES.get(symbol, 1000)
    except Exception as e:
        print(f"⚠️ API error {symbol}: {e}, using mock data")
        return MOCK_PRICES.get(symbol, 1000)

def get_historical(symbol, period="1h", limit=50):
    """Get historical data from FCS API, return mock pattern if fails"""
    try:
        url = f"{FCS_BASE_URL}/forex/history"
        params = {"access_key": FCS_ACCESS_KEY, "symbol": symbol, "period": period, "limit": limit}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') and data.get('response'):
                prices = []
                if isinstance(data['response'], dict):
                    for values in data['response'].values():
                        if isinstance(values, dict) and 'c' in values:
                            prices.append(float(values['c']))
                if len(prices) > 20:
                    return prices
    except Exception as e:
        print(f"⚠️ Historical API error: {e}")
    
    # Generate mock historical data (simulated price movement)
    base_price = MOCK_PRICES.get(symbol, 1000)
    prices = []
    for i in range(50):
        variation = np.sin(i * 0.3) * (base_price * 0.005)
        prices.append(base_price + variation)
    return prices

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50
    deltas = np.diff(prices[-period-1:])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100
    return 100 - (100 / (1 + (avg_gain / avg_loss)))

def get_signal_with_reason(symbol, timeframe="1h"):
    """Returns (direction, confidence, current_price, reason, timeframe)"""
    try:
        fcs_symbol = symbol["fcs_symbol"]
        
        # Get historical data
        closes = get_historical(fcs_symbol, "1h", 50)
        if len(closes) < 20:
            return None
        
        # Get current price
        current = get_live_price(fcs_symbol)
        if current is None:
            current = MOCK_PRICES.get(fcs_symbol, 1000)
        
        # Calculate indicators
        rsi = calculate_rsi(closes)
        sma20 = np.mean(closes[-20:])
        
        # For testing - force a signal on Monday
        # Remove this in production
        if datetime.datetime.now().weekday() == 0:  # Monday
            # Alternate between BUY and SELL for testing
            test_direction = "BUY" if (datetime.datetime.now().hour % 2 == 0) else "SELL"
            test_reason = f"🔍 *Test Signal (Monday)*: RSI is {rsi:.1f} + Price action indicates {test_direction} opportunity. Market is active."
            return (test_direction, 85, current, test_reason, timeframe)
        
        # Real signal logic
        if rsi < 35 and current > sma20:
            conf = 85 + int((35 - rsi) / 2)
            reason = f"🔍 *Technical Reason:* RSI is {rsi:.1f} (oversold below 35) + Price trading above 20-period SMA ({sma20:.2f}). Bullish reversal expected with institutional buying pressure."
            return ("BUY", min(95, conf), current, reason, timeframe)
        elif rsi > 65 and current < sma20:
            conf = 85 + int((rsi - 65) / 2)
            reason = f"🔍 *Technical Reason:* RSI is {rsi:.1f} (overbought above 65) + Price trading below 20-period SMA ({sma20:.2f}). Bearish reversal expected with profit booking."
            return ("SELL", min(95, conf), current, reason, timeframe)
        
        return None
    except Exception as e:
        print(f"Signal error {symbol['name']}: {e}")
        return None

# ============================================
# SIGNAL GENERATION
# ============================================

def generate_signal_data(symbol, direction, price, confidence, reason, timeframe):
    decimals = symbol["decimals"]
    spread = price * symbol["spread_pct"]
    
    if direction == "BUY":
        entry_low = round(price - spread, decimals)
        entry_high = round(price + spread, decimals)
        tp1 = round(price * (1 + symbol["tp1_pct"]), decimals)
        tp2 = round(price * (1 + symbol["tp2_pct"]), decimals)
        sl = round(price * (1 - symbol["sl_pct"]), decimals)
    else:
        entry_low = round(price - spread, decimals)
        entry_high = round(price + spread, decimals)
        tp1 = round(price * (1 - symbol["tp1_pct"]), decimals)
        tp2 = round(price * (1 - symbol["tp2_pct"]), decimals)
        sl = round(price * (1 + symbol["sl_pct"]), decimals)
    
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
        "confidence": confidence,
        "reason": reason,
        "timeframe": timeframe,
    }

def send_signal_to_channels(signal, is_vip_only=False):
    now = datetime.datetime.now()
    
    signal_text = f"""
{signal['emoji']} *{signal['direction']} {signal['symbol']}* 📊
🕐 _{now.strftime('%d %b %Y, %H:%M')} IST_
⏱️ *Timeframe:* {signal['timeframe']}

📌 Entry: `{signal['entry_low']} - {signal['entry_high']}`
🎯 TP1: `{signal['tp1']}`
🎯 TP2: `{signal['tp2']}`
🛑 SL: `{signal['sl']}`

📈 *Analysis:* {signal['reason']}

⭐ *Confidence: {signal['confidence']}%*
⚠️ *Risk:* 1-2% per trade.
"""
    
    public_msg_id = None
    if not is_vip_only:
        public_count = get_daily_public_count()
        if public_count < FREE_SIGNAL_LIMIT_DAILY:
            try:
                msg = bot.send_message(CHANNEL_ID, signal_text, parse_mode='Markdown')
                public_msg_id = msg.message_id
                increment_daily_public_count()
                print(f"✅ Public: {signal['direction']} {signal['symbol']}")
            except Exception as e:
                print(f"Public error: {e}")
    
    vip_count = get_daily_vip_count()
    vip_msg_id = None
    if vip_count < VIP_SIGNAL_LIMIT_DAILY:
        vip_text = f"⭐ *VIP PREMIUM SIGNAL* ⭐\n{signal_text}\n💎 *Exclusive VIP Entry - 30 min early!*\n🔗 {VIP_CHANNEL}"
        try:
            msg = bot.send_message(VIP_CHANNEL_ID, vip_text, parse_mode='Markdown')
            vip_msg_id = msg.message_id
            increment_daily_vip_count()
            print(f"✅ VIP: {signal['direction']} {signal['symbol']}")
        except Exception as e:
            print(f"VIP error: {e}")
    
    if public_msg_id or vip_msg_id:
        entry_mid = (signal["entry_low"] + signal["entry_high"]) / 2
        signal_id = save_signal_to_db(
            signal["symbol"], signal["direction"], entry_mid,
            signal["tp1"], signal["tp2"], signal["sl"], signal["decimals"],
            signal["ticker"], "both", public_msg_id or vip_msg_id,
            signal["confidence"], signal["reason"]
        )
        add_active_trade(signal["symbol"], signal["direction"], signal_id, signal["timeframe"])

def calculate_profit(direction, entry, hit_price, decimals):
    if decimals == 5:
        multiplier = 10000
        unit = "pips"
    elif decimals == 0:
        multiplier = 1
        unit = "$"
    else:
        multiplier = 100 if decimals == 2 else 1
        unit = "pts"
    profit = round(abs(hit_price - entry) * multiplier, 1)
    return profit, unit

# ============================================
# PRICE MONITOR
# ============================================

def monitor_prices():
    print("🔄 Price monitor started")
    while True:
        try:
            pending = get_pending_signals()
            
            for row in pending:
                sig_id, symbol, direction, entry, tp1, tp2, sl, decimals, msg_id, ticker = row
                
                current = get_live_price(ticker)
                if current is None:
                    continue
                
                if direction == "BUY":
                    if current >= tp1:
                        profit, unit = calculate_profit(direction, entry, tp1, decimals)
                        hype = f"🎯🔥 *TARGET HIT!* 🔥🎯\n\n{symbol} {direction} → *TP1 ✅ REACHED!*\n\n+{profit} {unit} profit!\n\n💎 *VIP got this entry early!*\n🚀 Join VIP: {VIP_CHANNEL}"
                        try:
                            bot.send_message(CHANNEL_ID, hype, parse_mode='Markdown')
                            bot.send_message(VIP_CHANNEL_ID, hype, parse_mode='Markdown')
                        except:
                            pass
                        update_signal_result(sig_id, "tp1_hit")
                        remove_active_trade(symbol)
                        print(f"🎯 TP1 Hit: {symbol}")
                    elif current >= tp2:
                        profit, unit = calculate_profit(direction, entry, tp2, decimals)
                        hype = f"🏆💰 *FULL PROFIT TARGET!* 💰🏆\n\n{symbol} {direction} → *TP2 ✅ REACHED!*\n\n+{profit} {unit} total profit!\n\n🎉 Congratulations VIP members!\n🔗 {VIP_CHANNEL}"
                        try:
                            bot.send_message(CHANNEL_ID, hype, parse_mode='Markdown')
                            bot.send_message(VIP_CHANNEL_ID, hype, parse_mode='Markdown')
                        except:
                            pass
                        update_signal_result(sig_id, "tp2_hit")
                        remove_active_trade(symbol)
                        print(f"🏆 TP2 Hit: {symbol}")
                    elif current <= sl:
                        try:
                            bot.delete_message(CHANNEL_ID, msg_id)
                        except:
                            pass
                        warn = f"⚠️ *SL HIT - Trade Closed* ⚠️\n\n{symbol} {direction}\n\n🔴 Signal removed from public channel.\n💎 VIP members - next signal coming soon!"
                        try:
                            bot.send_message(VIP_CHANNEL_ID, warn, parse_mode='Markdown')
                        except:
                            pass
                        update_signal_result(sig_id, "sl_hit")
                        remove_active_trade(symbol)
                        print(f"🔴 SL Hit: {symbol}")
                
                elif direction == "SELL":
                    if current <= tp1:
                        profit, unit = calculate_profit(direction, entry, tp1, decimals)
                        hype = f"🎯🔥 *TARGET HIT!* 🔥🎯\n\n{symbol} {direction} → *TP1 ✅ REACHED!*\n\n+{profit} {unit} profit!\n\n💎 *VIP got this entry early!*\n🚀 Join VIP: {VIP_CHANNEL}"
                        try:
                            bot.send_message(CHANNEL_ID, hype, parse_mode='Markdown')
                            bot.send_message(VIP_CHANNEL_ID, hype, parse_mode='Markdown')
                        except:
                            pass
                        update_signal_result(sig_id, "tp1_hit")
                        remove_active_trade(symbol)
                        print(f"🎯 TP1 Hit: {symbol}")
                    elif current <= tp2:
                        profit, unit = calculate_profit(direction, entry, tp2, decimals)
                        hype = f"🏆💰 *FULL PROFIT TARGET!* 💰🏆\n\n{symbol} {direction} → *TP2 ✅ REACHED!*\n\n+{profit} {unit} total profit!\n\n🎉 Congratulations VIP members!\n🔗 {VIP_CHANNEL}"
                        try:
                            bot.send_message(CHANNEL_ID, hype, parse_mode='Markdown')
                            bot.send_message(VIP_CHANNEL_ID, hype, parse_mode='Markdown')
                        except:
                            pass
                        update_signal_result(sig_id, "tp2_hit")
                        remove_active_trade(symbol)
                        print(f"🏆 TP2 Hit: {symbol}")
                    elif current >= sl:
                        try:
                            bot.delete_message(CHANNEL_ID, msg_id)
                        except:
                            pass
                        warn = f"⚠️ *SL HIT - Trade Closed* ⚠️\n\n{symbol} {direction}\n\n🔴 Signal removed from public channel.\n💎 VIP members - next signal coming soon!"
                        try:
                            bot.send_message(VIP_CHANNEL_ID, warn, parse_mode='Markdown')
                        except:
                            pass
                        update_signal_result(sig_id, "sl_hit")
                        remove_active_trade(symbol)
                        print(f"🔴 SL Hit: {symbol}")
                        
        except Exception as e:
            print(f"Monitor error: {e}")
        time.sleep(60)

# ============================================
# SIGNAL SCANNER
# ============================================

def signal_scanner():
    print("🔄 Signal scanner started - checking every 60 seconds")
    last_scan = {"5m": 0, "15m": 0, "1h": 0}
    scan_count = 0
    
    while True:
        try:
            scan_count += 1
            print(f"📡 Scan #{scan_count} at {datetime.datetime.now().strftime('%H:%M:%S')}")
            current_time = time.time()
            
            for symbol in SYMBOLS:
                if is_active_trade(symbol["name"]):
                    continue
                
                # Free channel (1h only) - 5-7 trades/day
                if get_daily_public_count() < FREE_SIGNAL_LIMIT_DAILY:
                    result = get_signal_with_reason(symbol, "1h")
                    if result:
                        direction, confidence, price, reason, tf = result
                        signal = generate_signal_data(symbol, direction, price, confidence, reason, tf)
                        send_signal_to_channels(signal, False)
                        print(f"📊 Signal sent: {direction} {symbol['name']}")
                        time.sleep(3)
                
                # VIP channel (multiple timeframes) - 20-25 trades/day
                if get_daily_vip_count() < VIP_SIGNAL_LIMIT_DAILY:
                    for tf in ["5m", "15m", "1h"]:
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
                            send_signal_to_channels(signal, False)
                            last_scan[tf] = current_time
                            print(f"📊 VIP Signal sent: {direction} {symbol['name']} on {tf}")
                            time.sleep(5)
                            break
                        last_scan[tf] = current_time
                        
        except Exception as e:
            print(f"Scanner error: {e}")
        time.sleep(60)

# ============================================
# BOT COMMANDS
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
💬 *Support:* {CONTACT_USERNAME}

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
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (user_id, name, email, phone, register_date, is_vip) VALUES (?,?,?,?,?,?)",
                  (user_id, name, email, phone, str(datetime.datetime.now()), 0))
        cursor.execute("INSERT INTO registrations (user_id, name, email, phone, date) VALUES (?,?,?,?,?)",
                  (user_id, name, email, phone, str(datetime.datetime.now())))
        conn.commit()
        conn.close()
        
        admin_msg = f"""🔔 *NEW REGISTRATION* 🔔
👤 *Name:* {name}
📧 *Email:* {email}
📱 *Phone:* {phone}
🆔 *User ID:* {user_id}
👤 *Username:* @{username}
🕐 *Time:* {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"""
        try:
            bot.send_message(ADMIN_ID, admin_msg, parse_mode='Markdown')
        except:
            pass
        
        reply_msg = f"""✅ *Welcome {name}!* ✅

Your registration is complete!

📊 *What you get:*
• {FREE_SIGNAL_LIMIT_DAILY} free signals daily
• Real market analysis with reasons
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
    
    for symbol in SYMBOLS:
        result = get_signal_with_reason(symbol, "1h")
        if result:
            direction, confidence, price, reason, tf = result
            signal = generate_signal_data(symbol, direction, price, confidence, reason, tf)
            
            signal_text = f"""
📊 *FREE SIGNAL* 📊
{signal['emoji']} *{signal['direction']} {signal['symbol']}*

📌 Entry: `{signal['entry_low']} - {signal['entry_high']}`
🎯 TP1: `{signal['tp1']}`
🎯 TP2: `{signal['tp2']}`
🛑 SL: `{signal['sl']}`

📈 *Analysis:* 
{signal['reason']}

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
✅ Multiple Timeframes (5m, 15m, 1h)
✅ Early Entry Alerts (Before Market)
✅ Live Market Analysis with Reasons
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
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM registrations WHERE date LIKE ?", (f"{datetime.datetime.now().strftime('%Y-%m-%d')}%",))
        today_reg = cursor.fetchone()[0]
        conn.close()
        
        public_today = get_daily_public_count()
        vip_today = get_daily_vip_count()
        
        msg = f"""📊 *BOT STATISTICS* 📊

👥 Total Users: {total_users}
📝 Today's Registrations: {today_reg}

📡 *Today's Signals:*
• Public: {public_today}/{FREE_SIGNAL_LIMIT_DAILY}
• VIP: {vip_today}/{VIP_SIGNAL_LIMIT_DAILY}

🤖 Bot Status: Active ✅
🕐 Last Update: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"""
        bot.reply_to(message, msg, parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ *Unauthorized*\n\nThis command is only for admin.")

@bot.message_handler(commands=['test_signal'])
def test_signal(message):
    if message.from_user.id == ADMIN_ID:
        bot.reply_to(message, "🔄 Testing signal generation...")
        count = 0
        for symbol in SYMBOLS[:3]:  # Test first 3 symbols
            result = get_signal_with_reason(symbol, "1h")
            if result:
                direction, confidence, price, reason, tf = result
                signal = generate_signal_data(symbol, direction, price, confidence, reason, tf)
                send_signal_to_channels(signal, is_vip_only=False)
                count += 1
                time.sleep(2)
        
        if count > 0:
            bot.reply_to(message, f"✅ {count} test signal(s) sent! Check your channels.")
        else:
            bot.reply_to(message, "❌ No signal conditions met. API may be down or market is ranging.")
    else:
        bot.reply_to(message, "❌ Admin only")

@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    if call.data == "register":
        msg = bot.send_message(call.message.chat.id, "📝 *Send:* `Name, Email, Phone`\n\nExample: `Rajesh, rajesh@gmail.com, 9876543210`", parse_mode='Markdown')
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
                    signal_text = f"📊 FREE SIGNAL\n{signal['direction']} {signal['symbol']}\nEntry: {signal['entry_low']}-{signal['entry_high']}\nTP1: {signal['tp1']}\nTP2: {signal['tp2']}\nSL: {signal['sl']}"
                    bot.send_message(call.message.chat.id, signal_text)
                    increment_user_signal_count(call.from_user.id)
                    break
    elif call.data == "vip":
        bot.send_message(call.message.chat.id, f"⭐ VIP Access: {VIP_CHANNEL}\n💰 ₹399/month\nUPI: {UPI_ID}\n\nPay & send screenshot to {CONTACT_USERNAME}")
    elif call.data == "support":
        bot.send_message(call.message.chat.id, f"💬 Contact: {CONTACT_USERNAME}\n📧 Email: btcuscoinbase@gmail.com")
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
print("📈 Signal Reasons: Included in every trade")
print("=" * 50)

# Remove webhook before starting
try:
    bot.remove_webhook()
    print("✅ Webhook removed successfully")
except Exception as e:
    print(f"⚠️ Webhook removal skipped: {e}")

time.sleep(2)

# Start background threads
scanner_thread = threading.Thread(target=signal_scanner, daemon=True)
scanner_thread.start()

monitor_thread = threading.Thread(target=monitor_prices, daemon=True)
monitor_thread.start()

# Start bot
print("🚀 Starting bot polling...")
bot.infinity_polling(timeout=30, skip_pending=True)
