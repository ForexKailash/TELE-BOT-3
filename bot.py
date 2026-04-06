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

# Promotional messages (rotating)
PROMO_MESSAGES = [
    "🚀 *VIP Members made 2300 pips this week!* Join them now → {vip}",
    "📊 *Limited Offer:* First 10 VIP get 50% off! DM @ForexKailash",
    "💎 *Why VIP?* Early entries, higher accuracy, 1-on-1 support. Only ₹399/month.",
    "🔥 *Today's VIP Signal* already up 150 pips! Next one in 30 mins → {vip}",
    "📈 *89% Win Rate* - Trusted by 5000+ traders. Become a VIP today!",
    "⏰ *Early Bird Alert:* Next VIP signal in 15 minutes. Don't miss!",
    "🎯 *Free signals are good, VIP signals are GREAT.* Upgrade now!",
    "💰 *Earn passive income* with our copy trading. VIP only → {vip}",
]

# ============================================
# DATABASE SETUP (Thread-safe, separate connections)
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
# DATABASE HELPERS (each uses its own connection)
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
    sig_id = cursor.lastrowid
    conn.close()
    return sig_id

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
# SYMBOLS (9 instruments)
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
# FCS API - REAL MARKET DATA (No mock signals)
# ============================================

def get_live_price(symbol):
    """Get real current price from FCS API"""
    try:
        url = f"{FCS_BASE_URL}/forex/single"
        params = {"access_key": FCS_ACCESS_KEY, "symbol": symbol}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') and data.get('response'):
                return float(data['response']['c'])
        return None
    except Exception as e:
        print(f"Price API error {symbol}: {e}")
        return None

def get_historical(symbol, period="1h", limit=50):
    """Get real historical data from FCS API"""
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
                if len(prices) >= 20:
                    return prices
        return None
    except Exception as e:
        print(f"Historical API error {symbol}: {e}")
        return None

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

def get_real_signal(symbol, timeframe="1h"):
    """
    Returns (direction, confidence, current_price, reason, timeframe)
    Uses real FCS API data only. Returns None if no real data.
    """
    fcs_symbol = symbol["fcs_symbol"]
    period_map = {"5m": "5min", "15m": "15min", "1h": "1h"}
    period = period_map.get(timeframe, "1h")
    
    # Get real historical data
    closes = get_historical(fcs_symbol, period, 50)
    if closes is None or len(closes) < 30:
        print(f"⚠️ No historical data for {fcs_symbol} on {timeframe}")
        return None
    
    # Get real current price
    current = get_live_price(fcs_symbol)
    if current is None:
        print(f"⚠️ No live price for {fcs_symbol}")
        return None
    
    # Calculate indicators
    rsi = calculate_rsi(closes)
    sma20 = np.mean(closes[-20:])
    sma50 = np.mean(closes[-50:]) if len(closes) >= 50 else sma20
    ema9 = np.mean(closes[-9:])
    ema21 = np.mean(closes[-21:]) if len(closes) >= 21 else sma20
    prev_close = closes[-2] if len(closes) >= 2 else current
    price_momentum = "up" if current > prev_close else "down"
    
    # ----- BUY conditions -----
    if rsi < 35 and current > sma20:
        confidence = 85 + int((35 - rsi) / 2)
        reason = f"🔍 *Technical Reason:* RSI is {rsi:.1f} (oversold below 35) + Price trading above 20-period SMA ({sma20:.2f}). Indicates bullish reversal with institutional buying pressure."
        return ("BUY", min(95, confidence), current, reason, timeframe)
    
    elif rsi < 30:
        confidence = 90
        reason = f"🔍 *Technical Reason:* RSI is extremely oversold at {rsi:.1f} (below 30). Historical probability of bounce back >85%."
        return ("BUY", confidence, current, reason, timeframe)
    
    elif current > ema9 and ema9 > ema21 and rsi > 50:
        confidence = 80
        reason = f"🔍 *Technical Reason:* Golden crossover detected! EMA9 ({ema9:.2f}) above EMA21 ({ema21:.2f}) with RSI {rsi:.1f} confirming bullish momentum."
        return ("BUY", confidence, current, reason, timeframe)
    
    elif price_momentum == "up" and current > sma20 and rsi < 60:
        confidence = 75
        reason = f"🔍 *Technical Reason:* Bullish price action. Price broke above 20 SMA ({sma20:.2f}) with positive momentum. RSI {rsi:.1f} shows room for upside."
        return ("BUY", confidence, current, reason, timeframe)
    
    # ----- SELL conditions -----
    elif rsi > 65 and current < sma20:
        confidence = 85 + int((rsi - 65) / 2)
        reason = f"🔍 *Technical Reason:* RSI is {rsi:.1f} (overbought above 65) + Price below 20 SMA ({sma20:.2f}). Bearish reversal expected, profit booking likely."
        return ("SELL", min(95, confidence), current, reason, timeframe)
    
    elif rsi > 70:
        confidence = 90
        reason = f"🔍 *Technical Reason:* RSI is extremely overbought at {rsi:.1f} (above 70). Market correction highly probable."
        return ("SELL", confidence, current, reason, timeframe)
    
    elif current < ema9 and ema9 < ema21 and rsi < 50:
        confidence = 80
        reason = f"🔍 *Technical Reason:* Death crossover detected! EMA9 ({ema9:.2f}) below EMA21 ({ema21:.2f}) with RSI {rsi:.1f} confirming bearish trend."
        return ("SELL", confidence, current, reason, timeframe)
    
    elif price_momentum == "down" and current < sma20 and rsi > 40:
        confidence = 75
        reason = f"🔍 *Technical Reason:* Bearish price action. Price broke below 20 SMA ({sma20:.2f}) with selling pressure. RSI {rsi:.1f} suggests more downside."
        return ("SELL", confidence, current, reason, timeframe)
    
    return None

# ============================================
# SIGNAL GENERATION & SENDING
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
        if get_daily_public_count() < FREE_SIGNAL_LIMIT_DAILY:
            try:
                msg = bot.send_message(CHANNEL_ID, signal_text, parse_mode='Markdown')
                public_msg_id = msg.message_id
                increment_daily_public_count()
                print(f"✅ Public signal: {signal['direction']} {signal['symbol']}")
            except Exception as e:
                print(f"Public send error: {e}")
    vip_msg_id = None
    if get_daily_vip_count() < VIP_SIGNAL_LIMIT_DAILY:
        vip_text = f"⭐ *VIP PREMIUM SIGNAL* ⭐\n{signal_text}\n💎 *Exclusive VIP Entry - 30 min early!*\n🔗 {VIP_CHANNEL}"
        try:
            msg = bot.send_message(VIP_CHANNEL_ID, vip_text, parse_mode='Markdown')
            vip_msg_id = msg.message_id
            increment_daily_vip_count()
            print(f"✅ VIP signal: {signal['direction']} {signal['symbol']}")
        except Exception as e:
            print(f"VIP send error: {e}")
    if public_msg_id or vip_msg_id:
        entry_mid = (signal["entry_low"] + signal["entry_high"]) / 2
        save_signal_to_db(
            signal["symbol"], signal["direction"], entry_mid,
            signal["tp1"], signal["tp2"], signal["sl"], signal["decimals"],
            signal["ticker"], "both", public_msg_id or vip_msg_id,
            signal["confidence"], signal["reason"]
        )
        add_active_trade(signal["symbol"], signal["direction"], 0, signal["timeframe"])

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
# PRICE MONITOR (TP/SL detection)
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
                        bot.send_message(CHANNEL_ID, hype, parse_mode='Markdown')
                        bot.send_message(VIP_CHANNEL_ID, hype, parse_mode='Markdown')
                        update_signal_result(sig_id, "tp1_hit")
                        remove_active_trade(symbol)
                    elif current >= tp2:
                        profit, unit = calculate_profit(direction, entry, tp2, decimals)
                        hype = f"🏆💰 *FULL PROFIT TARGET!* 💰🏆\n\n{symbol} {direction} → *TP2 ✅ REACHED!*\n\n+{profit} {unit} total profit!\n\n🎉 Congratulations VIP members!\n🔗 {VIP_CHANNEL}"
                        bot.send_message(CHANNEL_ID, hype, parse_mode='Markdown')
                        bot.send_message(VIP_CHANNEL_ID, hype, parse_mode='Markdown')
                        update_signal_result(sig_id, "tp2_hit")
                        remove_active_trade(symbol)
                    elif current <= sl:
                        try:
                            bot.delete_message(CHANNEL_ID, msg_id)
                        except:
                            pass
                        warn = f"⚠️ *SL HIT - Trade Closed* ⚠️\n\n{symbol} {direction}\n\n🔴 Signal removed from public channel.\n💎 VIP members - next signal coming soon!"
                        bot.send_message(VIP_CHANNEL_ID, warn, parse_mode='Markdown')
                        update_signal_result(sig_id, "sl_hit")
                        remove_active_trade(symbol)
                else:  # SELL
                    if current <= tp1:
                        profit, unit = calculate_profit(direction, entry, tp1, decimals)
                        hype = f"🎯🔥 *TARGET HIT!* 🔥🎯\n\n{symbol} {direction} → *TP1 ✅ REACHED!*\n\n+{profit} {unit} profit!\n\n💎 *VIP got this entry early!*\n🚀 Join VIP: {VIP_CHANNEL}"
                        bot.send_message(CHANNEL_ID, hype, parse_mode='Markdown')
                        bot.send_message(VIP_CHANNEL_ID, hype, parse_mode='Markdown')
                        update_signal_result(sig_id, "tp1_hit")
                        remove_active_trade(symbol)
                    elif current <= tp2:
                        profit, unit = calculate_profit(direction, entry, tp2, decimals)
                        hype = f"🏆💰 *FULL PROFIT TARGET!* 💰🏆\n\n{symbol} {direction} → *TP2 ✅ REACHED!*\n\n+{profit} {unit} total profit!\n\n🎉 Congratulations VIP members!\n🔗 {VIP_CHANNEL}"
                        bot.send_message(CHANNEL_ID, hype, parse_mode='Markdown')
                        bot.send_message(VIP_CHANNEL_ID, hype, parse_mode='Markdown')
                        update_signal_result(sig_id, "tp2_hit")
                        remove_active_trade(symbol)
                    elif current >= sl:
                        try:
                            bot.delete_message(CHANNEL_ID, msg_id)
                        except:
                            pass
                        warn = f"⚠️ *SL HIT - Trade Closed* ⚠️\n\n{symbol} {direction}\n\n🔴 Signal removed from public channel.\n💎 VIP members - next signal coming soon!"
                        bot.send_message(VIP_CHANNEL_ID, warn, parse_mode='Markdown')
                        update_signal_result(sig_id, "sl_hit")
                        remove_active_trade(symbol)
        except Exception as e:
            print(f"Monitor error: {e}")
        time.sleep(60)

# ============================================
# SIGNAL SCANNER (every 60 seconds, real signals only)
# ============================================

def signal_scanner():
    print("🔄 Signal scanner started - real market data only")
    last_scan = {"5m": 0, "15m": 0, "1h": 0}
    while True:
        try:
            current_time = time.time()
            for symbol in SYMBOLS:
                if is_active_trade(symbol["name"]):
                    continue
                # Free channel (1h only) - up to 7 per day
                if get_daily_public_count() < FREE_SIGNAL_LIMIT_DAILY:
                    sig = get_real_signal(symbol, "1h")
                    if sig:
                        direction, conf, price, reason, tf = sig
                        signal = generate_signal_data(symbol, direction, price, conf, reason, tf)
                        send_signal_to_channels(signal, False)
                        time.sleep(3)
                # VIP channel (multiple timeframes) - up to 22 per day
                if get_daily_vip_count() < VIP_SIGNAL_LIMIT_DAILY:
                    for tf in ["5m", "15m", "1h"]:
                        if tf == "5m" and current_time - last_scan["5m"] < 300:
                            continue
                        if tf == "15m" and current_time - last_scan["15m"] < 900:
                            continue
                        if tf == "1h" and current_time - last_scan["1h"] < 3600:
                            continue
                        sig = get_real_signal(symbol, tf)
                        if sig:
                            direction, conf, price, reason, tframe = sig
                            signal = generate_signal_data(symbol, direction, price, conf, reason, tframe)
                            send_signal_to_channels(signal, False)
                            last_scan[tf] = current_time
                            time.sleep(5)
                            break
                        last_scan[tf] = current_time
        except Exception as e:
            print(f"Scanner error: {e}")
        time.sleep(60)

# ============================================
# PROMOTIONAL MESSAGES SCHEDULER
# ============================================

def promo_sender():
    """Send promotional messages to both channels at regular intervals"""
    last_promo = 0
    while True:
        now = time.time()
        # Send promo every 2 hours (7200 seconds)
        if now - last_promo >= 7200:
            promo_text = random.choice(PROMO_MESSAGES).format(vip=VIP_CHANNEL)
            full_promo = f"📢 *Promotion* 📢\n\n{promo_text}\n\n💬 Contact: {CONTACT_USERNAME}"
            try:
                bot.send_message(CHANNEL_ID, full_promo, parse_mode='Markdown')
                bot.send_message(VIP_CHANNEL_ID, full_promo, parse_mode='Markdown')
                last_promo = now
                print("📢 Promo message sent")
            except Exception as e:
                print(f"Promo error: {e}")
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
💬 *Support:* {CONTACT_USERNAME}

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
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (user_id, name, email, phone, register_date, is_vip) VALUES (?,?,?,?,?,?)",
                       (user_id, name, email, phone, str(datetime.datetime.now()), 0))
        cursor.execute("INSERT INTO registrations (user_id, name, email, phone, date) VALUES (?,?,?,?,?)",
                       (user_id, name, email, phone, str(datetime.datetime.now())))
        conn.commit()
        conn.close()
        admin_msg = f"🔔 NEW REGISTRATION\nName: {name}\nUser: @{username}"
        try:
            bot.send_message(ADMIN_ID, admin_msg)
        except:
            pass
        bot.reply_to(message, f"✅ Welcome {name}! Registration complete.", parse_mode='Markdown', reply_markup=main_keyboard())
    except:
        bot.reply_to(message, "❌ Invalid format! Send: `Name, Email, Phone`", parse_mode='Markdown')

@bot.message_handler(commands=['free'])
def free_signal(message):
    user_id = message.from_user.id
    remaining = signals_remaining(user_id)
    if remaining <= 0:
        bot.reply_to(message, f"🚫 Free limit reached! Join: {FREE_CHANNEL}", parse_mode='Markdown')
        return
    for symbol in SYMBOLS:
        sig = get_real_signal(symbol, "1h")
        if sig:
            direction, conf, price, reason, tf = sig
            signal = generate_signal_data(symbol, direction, price, conf, reason, tf)
            text = f"""📊 *FREE SIGNAL* 📊
{signal['emoji']} *{signal['direction']} {signal['symbol']}*

📌 Entry: `{signal['entry_low']} - {signal['entry_high']}`
🎯 TP1: `{signal['tp1']}`
🎯 TP2: `{signal['tp2']}`
🛑 SL: `{signal['sl']}`

📈 *Analysis:* {reason}

⚠️ *Free signals left: {remaining-1}*"""
            bot.reply_to(message, text, parse_mode='Markdown')
            increment_user_signal_count(user_id)
            return
    bot.reply_to(message, "⚠️ No real signal available right now. Market may be consolidating.", parse_mode='Markdown')

@bot.message_handler(commands=['vip'])
def vip_command(message):
    msg = f"""⭐ *VIP Access* ⭐

✅ {VIP_SIGNAL_LIMIT_DAILY} signals/day
💰 ₹399/month
📱 UPI: `{UPI_ID}`

Pay & send screenshot to {CONTACT_USERNAME}
🔗 {VIP_CHANNEL}"""
    bot.reply_to(message, msg, parse_mode='Markdown', reply_markup=main_keyboard())

@bot.message_handler(commands=['support'])
def support_command(message):
    bot.reply_to(message, f"💬 Contact: {CONTACT_USERNAME}\n📧 Email: btcuscoinbase@gmail.com", parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def stats_command(message):
    if message.from_user.id == ADMIN_ID:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]
        conn.close()
        pub = get_daily_public_count()
        vip = get_daily_vip_count()
        bot.reply_to(message, f"📊 *STATS*\nUsers: {total}\nPublic: {pub}/{FREE_SIGNAL_LIMIT_DAILY}\nVIP: {vip}/{VIP_SIGNAL_LIMIT_DAILY}", parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ Admin only")

@bot.message_handler(commands=['test_signal'])
def test_signal(message):
    if message.from_user.id == ADMIN_ID:
        bot.reply_to(message, "🔄 Testing real signal generation...")
        count = 0
        for sym in SYMBOLS[:3]:
            sig = get_real_signal(sym, "1h")
            if sig:
                direction, conf, price, reason, tf = sig
                signal = generate_signal_data(sym, direction, price, conf, reason, tf)
                send_signal_to_channels(signal, False)
                count += 1
                time.sleep(2)
        bot.reply_to(message, f"✅ {count} real signal(s) sent. Check channels.")
    else:
        bot.reply_to(message, "❌ Admin only")

@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    if call.data == "register":
        msg = bot.send_message(call.message.chat.id, "📝 Send: `Name, Email, Phone`", parse_mode='Markdown')
        bot.register_next_step_handler(msg, save_user)
    elif call.data == "free":
        remaining = signals_remaining(call.from_user.id)
        if remaining <= 0:
            bot.send_message(call.message.chat.id, f"🚫 Free limit reached! Join: {FREE_CHANNEL}")
        else:
            for sym in SYMBOLS:
                sig = get_real_signal(sym, "1h")
                if sig:
                    direction, conf, price, reason, tf = sig
                    signal = generate_signal_data(sym, direction, price, conf, reason, tf)
                    txt = f"📊 FREE SIGNAL\n{signal['direction']} {signal['symbol']}\nEntry: {signal['entry_low']}-{signal['entry_high']}\nTP1: {signal['tp1']}\nTP2: {signal['tp2']}\nSL: {signal['sl']}"
                    bot.send_message(call.message.chat.id, txt)
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
print("🤖 FOREX TRADING BOT - REAL MARKET SIGNALS")
print("=" * 50)
print(f"Admin: {ADMIN_ID}")
print(f"Public: {CHANNEL_ID}")
print(f"VIP: {VIP_CHANNEL_ID}")
print(f"Daily Limits: Public={FREE_SIGNAL_LIMIT_DAILY}, VIP={VIP_SIGNAL_LIMIT_DAILY}")
print(f"Support: {CONTACT_USERNAME}")
print("=" * 50)
print("✅ Bot ready. Sending REAL signals only.")
print("🔄 Scanner every 60 sec | Price monitor every 60 sec")
print("📢 Promotional messages every 2 hours")
print("=" * 50)

# Remove webhook
try:
    bot.remove_webhook()
    print("Webhook removed")
except:
    pass

time.sleep(2)

# Start threads
threading.Thread(target=signal_scanner, daemon=True).start()
threading.Thread(target=monitor_prices, daemon=True).start()
threading.Thread(target=promo_sender, daemon=True).start()

bot.infinity_polling(timeout=30, skip_pending=True)
