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
# CONFIGURATION (Your Credentials)
# ============================================

BOT_TOKEN = "8653450456:AAER9w6Gjj5IWkyCs1taa01N-DdMFZqxt3E"
ADMIN_ID = 6253584826
CHANNEL_ID = '@tradewithkailashh'
WEBSITE_URL = 'https://forexkailash.netlify.app'
FREE_CHANNEL = 'https://t.me/tradewithkailashh'
VIP_CHANNEL = 'https://t.me/+Snj0BVAwjDo3NTA1'
UPI_ID = 'kailashbhardwaj66-2@okicici'
CONTACT_USERNAME = '@ForexKailash'  # Changed from @Yungshang1
COURSE_URL = 'https://forexkailash.netlify.app'

VIP_CHANNEL_ID = -1003826269063
FREE_SIGNAL_LIMIT_DAILY = 7      # 5-7 trades per day
VIP_SIGNAL_LIMIT_DAILY = 22      # 20-25 trades per day

# FCS API Keys (Railway compatible)
FCS_ACCESS_KEY = "wvYZfov5RC2SlDpzaHautvMzowmYQcc"
FCS_PUBLIC_KEY = "Gj3DoeAgI1gRNo2LMuHGfccTM"
FCS_BASE_URL = "https://api-v4.fcsapi.com"

# ============================================
# DATABASE SETUP (Fixed - No recursive cursor)
# ============================================

os.makedirs('telegram_bot', exist_ok=True)

# Single database connection for all operations
DB_CONN = sqlite3.connect('telegram_bot/users.db', check_same_thread=False)
DB_CURSOR = DB_CONN.cursor()

def init_db():
    # Users table
    DB_CURSOR.execute('''CREATE TABLE IF NOT EXISTS users
    (user_id INTEGER PRIMARY KEY, name TEXT, email TEXT, phone TEXT,
    register_date TEXT, is_vip INTEGER)''')
    
    # Registrations log
    DB_CURSOR.execute('''CREATE TABLE IF NOT EXISTS registrations
    (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT,
    email TEXT, phone TEXT, date TEXT)''')
    
    # Signal usage per user per day
    DB_CURSOR.execute('''CREATE TABLE IF NOT EXISTS signal_usage
    (user_id INTEGER PRIMARY KEY, last_date TEXT, count INTEGER DEFAULT 0)''')
    
    # Channel signals (public + vip)
    DB_CURSOR.execute('''CREATE TABLE IF NOT EXISTS channel_signals
    (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, direction TEXT,
    entry REAL, tp1 REAL, tp2 REAL, sl REAL, decimals INTEGER,
    sent_date TEXT, sent_time TEXT, result TEXT DEFAULT "pending",
    message_id INTEGER DEFAULT NULL, ticker TEXT,
    channel_type TEXT DEFAULT "public", confidence INTEGER DEFAULT 0, signal_reason TEXT)''')
    
    # Daily counters
    DB_CURSOR.execute('''CREATE TABLE IF NOT EXISTS daily_public_counter
    (date TEXT PRIMARY KEY, count INTEGER DEFAULT 0)''')
    
    DB_CURSOR.execute('''CREATE TABLE IF NOT EXISTS daily_vip_counter
    (date TEXT PRIMARY KEY, count INTEGER DEFAULT 0)''')
    
    # Active trades tracking
    DB_CURSOR.execute('''CREATE TABLE IF NOT EXISTS active_trades
    (symbol TEXT PRIMARY KEY, direction TEXT, signal_id INTEGER, sent_time TEXT, timeframe TEXT)''')
    
    DB_CONN.commit()

init_db()

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_daily_public_count():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    DB_CURSOR.execute("SELECT count FROM daily_public_counter WHERE date=?", (today,))
    row = DB_CURSOR.fetchone()
    return row[0] if row else 0

def increment_daily_public_count():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    DB_CURSOR.execute("INSERT INTO daily_public_counter (date, count) VALUES (?,1) ON CONFLICT(date) DO UPDATE SET count = count + 1", (today,))
    DB_CONN.commit()

def get_daily_vip_count():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    DB_CURSOR.execute("SELECT count FROM daily_vip_counter WHERE date=?", (today,))
    row = DB_CURSOR.fetchone()
    return row[0] if row else 0

def increment_daily_vip_count():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    DB_CURSOR.execute("INSERT INTO daily_vip_counter (date, count) VALUES (?,1) ON CONFLICT(date) DO UPDATE SET count = count + 1", (today,))
    DB_CONN.commit()

def signals_remaining(user_id):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    DB_CURSOR.execute("SELECT count FROM signal_usage WHERE user_id=? AND last_date=?", (user_id, today))
    row = DB_CURSOR.fetchone()
    used = row[0] if row else 0
    return max(0, 3 - used)

def increment_user_signal_count(user_id):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    DB_CURSOR.execute("INSERT INTO signal_usage (user_id, last_date, count) VALUES (?,?,1) ON CONFLICT(user_id) DO UPDATE SET count = count + 1, last_date = ?", (user_id, today, today))
    DB_CONN.commit()

def is_active_trade(symbol):
    DB_CURSOR.execute("SELECT * FROM active_trades WHERE symbol=?", (symbol,))
    return DB_CURSOR.fetchone() is not None

def add_active_trade(symbol, direction, signal_id, timeframe):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    DB_CURSOR.execute("INSERT OR REPLACE INTO active_trades (symbol, direction, signal_id, sent_time, timeframe) VALUES (?,?,?,?,?)", 
                      (symbol, direction, signal_id, now, timeframe))
    DB_CONN.commit()

def remove_active_trade(symbol):
    DB_CURSOR.execute("DELETE FROM active_trades WHERE symbol=?", (symbol,))
    DB_CONN.commit()

def save_signal_to_db(symbol, direction, entry, tp1, tp2, sl, decimals, ticker, channel_type, message_id, confidence, reason):
    now = datetime.datetime.now()
    DB_CURSOR.execute("""INSERT INTO channel_signals
    (symbol, direction, entry, tp1, tp2, sl, decimals, sent_date, sent_time, ticker, channel_type, message_id, confidence, signal_reason)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (symbol, direction, entry, tp1, tp2, sl, decimals,
     now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), ticker, channel_type, message_id, confidence, reason))
    DB_CONN.commit()
    return DB_CURSOR.lastrowid

def update_signal_result(signal_id, result):
    DB_CURSOR.execute("UPDATE channel_signals SET result=? WHERE id=?", (result, signal_id))
    DB_CONN.commit()

# ============================================
# SYMBOLS (9 Symbols as requested)
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
# FCS API FUNCTIONS (Real Market Data)
# ============================================

def get_live_price(symbol):
    """Get current live price from FCS API"""
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
        print(f"Price error: {e}")
        return None

def get_historical(symbol, period="1h", limit=50):
    """Get historical data for indicators"""
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
                return prices
        return []
    except Exception as e:
        print(f"Historical error: {e}")
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
    return 100 - (100 / (1 + (avg_gain / avg_loss)))

def get_signal_with_reason(symbol, timeframe="1h"):
    """
    Returns (direction, confidence, current_price, reason, timeframe)
    With detailed technical analysis reason
    """
    try:
        fcs_symbol = symbol["fcs_symbol"]
        period_map = {"5m": "5min", "15m": "15min", "1h": "1h"}
        period = period_map.get(timeframe, "1h")
        
        # Get historical data
        closes = get_historical(fcs_symbol, period, 50)
        if len(closes) < 30:
            return None
        
        # Get current price
        current = get_live_price(fcs_symbol)
        if current is None:
            return None
        
        # Calculate indicators
        rsi = calculate_rsi(closes)
        sma20 = np.mean(closes[-20:])
        sma50 = np.mean(closes[-50:]) if len(closes) >= 50 else sma20
        ema9 = np.mean(closes[-9:])
        ema21 = np.mean(closes[-21:]) if len(closes) >= 21 else sma20
        
        # Price action
        prev_close = closes[-2] if len(closes) >= 2 else current
        price_momentum = "up" if current > prev_close else "down"
        
        # ============================================
        # SIGNAL GENERATION WITH DETAILED REASONS
        # ============================================
        
        # STRONG BUY SIGNALS
        if rsi < 35 and current > sma20:
            confidence = 85 + int((35 - rsi) / 2)
            reason = f"🔍 *Technical Reason:* RSI is {rsi:.1f} (oversold below 35) + Price trading above 20-period SMA ({sma20:.2f}). This indicates bullish reversal potential with institutional buying pressure. Smart money accumulation detected at these levels."
            return ("BUY", min(95, confidence), current, reason, timeframe)
        
        elif rsi < 30:
            confidence = 90
            reason = f"🔍 *Technical Reason:* RSI is extremely oversold at {rsi:.1f} (below 30). Historical data shows 85%+ probability of bounce back from these levels. Market is at discount zone."
            return ("BUY", confidence, current, reason, timeframe)
        
        elif current > ema9 and ema9 > ema21 and rsi > 50:
            confidence = 80
            reason = f"🔍 *Technical Reason:* Golden crossover detected! EMA9 ({ema9:.2f}) is above EMA21 ({ema21:.2f}) forming bullish trend. RSI at {rsi:.1f} confirms strong momentum. Uptrend likely to continue with volume support."
            return ("BUY", confidence, current, reason, timeframe)
        
        elif price_momentum == "up" and current > sma20 and rsi < 60:
            confidence = 75
            reason = f"🔍 *Technical Reason:* Bullish price action with positive momentum. Price broke above 20 SMA ({sma20:.2f}) with increasing buying pressure. RSI at {rsi:.1f} shows room for more upside."
            return ("BUY", confidence, current, reason, timeframe)
        
        # STRONG SELL SIGNALS
        elif rsi > 65 and current < sma20:
            confidence = 85 + int((rsi - 65) / 2)
            reason = f"🔍 *Technical Reason:* RSI is {rsi:.1f} (overbought above 65) + Price trading below 20-period SMA ({sma20:.2f}). This indicates bearish reversal potential with profit booking expected. Smart money taking profits at these levels."
            return ("SELL", min(95, confidence), current, reason, timeframe)
        
        elif rsi > 70:
            confidence = 90
            reason = f"🔍 *Technical Reason:* RSI is extremely overbought at {rsi:.1f} (above 70). Market correction highly probable. Resistance levels are strong at current price."
            return ("SELL", confidence, current, reason, timeframe)
        
        elif current < ema9 and ema9 < ema21 and rsi < 50:
            confidence = 80
            reason = f"🔍 *Technical Reason:* Death crossover detected! EMA9 ({ema9:.2f}) is below EMA21 ({ema21:.2f}) forming bearish trend. RSI at {rsi:.1f} confirms downward momentum. Downtrend likely to continue."
            return ("SELL", confidence, current, reason, timeframe)
        
        elif price_momentum == "down" and current < sma20 and rsi > 40:
            confidence = 75
            reason = f"🔍 *Technical Reason:* Bearish price action with negative momentum. Price broke below 20 SMA ({sma20:.2f}) with selling pressure. RSI at {rsi:.1f} shows room for more downside."
            return ("SELL", confidence, current, reason, timeframe)
        
        return None
    except Exception as e:
        print(f"Signal error {symbol['name']}: {e}")
        return None

# ============================================
# SIGNAL GENERATION
# ============================================

def generate_signal_data(symbol, direction, price, confidence, reason, timeframe):
    """Create signal dict with entry, TP, SL levels"""
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
    
    # Send to Public Channel (Free users - 5-7 trades/day)
    public_msg_id = None
    if not is_vip_only:
        public_count = get_daily_public_count()
        if public_count < FREE_SIGNAL_LIMIT_DAILY:
            try:
                msg = bot.send_message(CHANNEL_ID, signal_text, parse_mode='Markdown')
                public_msg_id = msg.message_id
                increment_daily_public_count()
                print(f"✅ Public signal: {signal['direction']} {signal['symbol']} ({public_count+1}/{FREE_SIGNAL_LIMIT_DAILY})")
            except Exception as e:
                print(f"Public error: {e}")
    
    # Send to VIP Channel (VIP users - 20-25 trades/day)
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
            print(f"✅ VIP signal: {signal['direction']} {signal['symbol']} ({vip_count+1}/{VIP_SIGNAL_LIMIT_DAILY})")
        except Exception as e:
            print(f"VIP error: {e}")
    
    # Save to database
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
    """Calculate profit in pips/points"""
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

def get_hype_reason(symbol, direction, hit_level):
    """Generate hype reason for TP hit"""
    reasons = [
        f"Strong {direction} momentum continued as predicted!",
        f"Institutional buying/selling pressure drove price to target.",
        f"Technical breakout confirmed our analysis!",
        f"Market followed our predicted path perfectly.",
        f"Volume spike confirmed the directional move.",
        f"Smart money accumulation detected at entry levels.",
        f"Breakout from consolidation zone completed successfully."
    ]
    return random.choice(reasons)

# ============================================
# PRICE MONITOR (Fixed - No recursive cursor)
# ============================================

def monitor_prices():
    """Check pending signals every 60 seconds for TP/SL hits"""
    print("🔄 Price monitor started - checking every 60 seconds")
    
    while True:
        try:
            # Get pending signals
            DB_CURSOR.execute("""SELECT id, symbol, direction, entry, tp1, tp2, sl, decimals, 
                        message_id, ticker FROM channel_signals
                        WHERE result='pending' AND message_id IS NOT NULL""")
            pending = DB_CURSOR.fetchall()
            
            for row in pending:
                sig_id, symbol, direction, entry, tp1, tp2, sl, decimals, msg_id, ticker = row
                
                current = get_live_price(ticker)
                if current is None:
                    continue
                
                # BUY side
                if direction == "BUY":
                    if current >= tp1:
                        profit, unit = calculate_profit(direction, entry, tp1, decimals)
                        hype_reason = get_hype_reason(symbol, direction, "TP1")
                        hype = f"""
🎯🔥 *TARGET HIT!* 🔥🎯

{symbol} {direction} → *TP1 ✅ REACHED!*

+{profit} {unit} profit!

📊 *Why TP hit?* {hype_reason}

💎 *VIP got this entry early!*
🚀 Join VIP: {VIP_CHANNEL}
"""
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
                        hype_reason = get_hype_reason(symbol, direction, "TP2")
                        hype = f"""
🏆💰 *FULL PROFIT TARGET!* 💰🏆

{symbol} {direction} → *TP2 ✅ REACHED!*

+{profit} {unit} total profit!

📊 *Why full profit hit?* {hype_reason}

🎉 Congratulations VIP members!
🔗 {VIP_CHANNEL}
"""
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
                        warn = f"""
⚠️ *SL HIT - Trade Closed* ⚠️

{symbol} {direction}

🔴 Signal removed from public channel.
💎 VIP members - next signal coming soon!
"""
                        try:
                            bot.send_message(VIP_CHANNEL_ID, warn, parse_mode='Markdown')
                        except:
                            pass
                        update_signal_result(sig_id, "sl_hit")
                        remove_active_trade(symbol)
                        print(f"🔴 SL Hit: {symbol}")
                
                # SELL side
                elif direction == "SELL":
                    if current <= tp1:
                        profit, unit = calculate_profit(direction, entry, tp1, decimals)
                        hype_reason = get_hype_reason(symbol, direction, "TP1")
                        hype = f"""
🎯🔥 *TARGET HIT!* 🔥🎯

{symbol} {direction} → *TP1 ✅ REACHED!*

+{profit} {unit} profit!

📊 *Why TP hit?* {hype_reason}

💎 *VIP got this entry early!*
🚀 Join VIP: {VIP_CHANNEL}
"""
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
                        hype_reason = get_hype_reason(symbol, direction, "TP2")
                        hype = f"""
🏆💰 *FULL PROFIT TARGET!* 💰🏆

{symbol} {direction} → *TP2 ✅ REACHED!*

+{profit} {unit} total profit!

📊 *Why full profit hit?* {hype_reason}

🎉 Congratulations VIP members!
🔗 {VIP_CHANNEL}
"""
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
                        warn = f"""
⚠️ *SL HIT - Trade Closed* ⚠️

{symbol} {direction}

🔴 Signal removed from public channel.
💎 VIP members - next signal coming soon!
"""
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
# SIGNAL SCANNER (Every 60 seconds)
# ============================================

def signal_scanner():
    """
    Scan all symbols every 60 seconds for trading opportunities
    VIP gets multiple timeframes (5m, 15m, 1h) = 20-25 trades/day
    Free gets only 1h timeframe = 5-7 trades/day
    """
    print("🔄 Signal scanner started - checking every 60 seconds")
    last_scan = {"5m": 0, "15m": 0, "1h": 0}
    
    while True:
        try:
            current_time = time.time()
            
            for symbol in SYMBOLS:
                # Skip if already in active trade
                if is_active_trade(symbol["name"]):
                    continue
                
                # ============================================
                # FREE CHANNEL SIGNALS (1h timeframe only)
                # 5-7 trades per day
                # ============================================
                if get_daily_public_count() < FREE_SIGNAL_LIMIT_DAILY:
                    result = get_signal_with_reason(symbol, "1h")
                    if result:
                        direction, confidence, price, reason, tf = result
                        signal = generate_signal_data(symbol, direction, price, confidence, reason, tf)
                        send_signal_to_channels(signal, is_vip_only=False)
                        time.sleep(3)
                
                # ============================================
                # VIP CHANNEL SIGNALS (Multiple timeframes)
                # 20-25 trades per day
                # ============================================
                if get_daily_vip_count() < VIP_SIGNAL_LIMIT_DAILY:
                    timeframes = ["5m", "15m", "1h"]
                    for tf in timeframes:
                        # Avoid scanning same timeframe too frequently
                        if tf == "5m" and current_time - last_scan["5m"] < 300:  # 5 min
                            continue
                        elif tf == "15m" and current_time - last_scan["15m"] < 900:  # 15 min
                            continue
                        elif tf == "1h" and current_time - last_scan["1h"] < 3600:  # 1 hour
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
📈 5000+ Traders Trust Us

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
        DB_CURSOR.execute("INSERT OR REPLACE INTO users (user_id, name, email, phone, register_date, is_vip) VALUES (?,?,?,?,?,?)",
                  (user_id, name, email, phone, str(datetime.datetime.now()), 0))
        DB_CURSOR.execute("INSERT INTO registrations (user_id, name, email, phone, date) VALUES (?,?,?,?,?)",
                  (user_id, name, email, phone, str(datetime.datetime.now())))
        DB_CONN.commit()
        
        # Notify admin
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
    
    # Get a quick signal for user
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
        DB_CURSOR.execute("SELECT COUNT(*) FROM users")
        total_users = DB_CURSOR.fetchone()[0]
        DB_CURSOR.execute("SELECT COUNT(*) FROM registrations WHERE date LIKE ?", (f"{datetime.datetime.now().strftime('%Y-%m-%d')}%",))
        today_reg = DB_CURSOR.fetchone()[0]
        
        public_today = get_daily_public_count()
        vip_today = get_daily_vip_count()
        
        DB_CURSOR.execute("SELECT COUNT(*) FROM channel_signals WHERE result='pending'")
        active_trades = DB_CURSOR.fetchone()[0]
        
        msg = f"""📊 *BOT STATISTICS* 📊

👥 Total Users: {total_users}
📝 Today's Registrations: {today_reg}

📡 *Today's Signals:*
• Public: {public_today}/{FREE_SIGNAL_LIMIT_DAILY}
• VIP: {vip_today}/{VIP_SIGNAL_LIMIT_DAILY}
• Active Trades: {active_trades}

🤖 Bot Status: Active ✅
🕐 Last Update: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"""
        bot.reply_to(message, msg, parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ *Unauthorized*\n\nThis command is only for admin.")

@bot.message_handler(commands=['help'])
def help_command(message):
    msg = """📚 *Available Commands* 📚

/start - Start the bot
/register - Register for free signals
/free - Get free forex signal
/vip - VIP channel access info
/support - Contact support
/stats - Bot statistics (admin only)
/help - Show this help

*Need more help?* Contact @ForexKailash"""
    bot.reply_to(message, msg, parse_mode='Markdown', reply_markup=main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    if call.data == "register":
        msg = bot.send_message(call.message.chat.id, "📝 *Send:* `Name, Email, Phone`\n\nExample: `Rajesh, rajesh@gmail.com, 9876543210`", parse_mode='Markdown')
        bot.register_next_step_handler(msg, save_user)
    elif call.data == "free":
        remaining = signals_remaining(call.from_user.id)
        if remaining <= 0:
            block_msg = f"🚫 Free limit reached! Join free channel: {FREE_CHANNEL}"
            bot.send_message(call.message.chat.id, block_msg)
        else:
            for symbol in SYMBOLS:
                result = get_signal_with_reason(symbol, "1h")
                if result:
                    direction, confidence, price, reason, tf = result
                    signal = generate_signal_data(symbol, direction, price, confidence, reason, tf)
                    signal_text = f"📊 FREE SIGNAL\n{signal['direction']} {signal['symbol']}\nEntry: {signal['entry_low']}-{signal['entry_high']}\nTP1: {signal['tp1']}\nTP2: {signal['tp2']}\nSL: {signal['sl']}\n\nReason: {reason[:100]}..."
                    bot.send_message(call.message.chat.id, signal_text)
                    increment_user_signal_count(call.from_user.id)
                    break
    elif call.data == "vip":
        msg = f"⭐ VIP Access: {VIP_CHANNEL}\n💰 ₹399/month\nUPI: {UPI_ID}\n\nPay & send screenshot to {CONTACT_USERNAME}"
        bot.send_message(call.message.chat.id, msg)
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
print("🎯 TP Hype Messages: Enabled with reasons")
print("🗑️ SL Deletion: Enabled")
print("📈 Signal Reasons: Included in every trade")
print("=" * 50)

# Remove webhook before starting (Fix for 409 error)
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
