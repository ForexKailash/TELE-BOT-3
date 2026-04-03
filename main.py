import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yfinance as yf
import requests
import sqlite3
import threading
import time
import random
import logging
from datetime import datetime
from flask import Flask
from PIL import Image, ImageDraw, ImageFont
import io
import os

# ===================== HARDCODED CONFIGURATION =====================
BOT_TOKEN = "8653450456:AAER9w6Gjj5IWkyCs1taa01N-DdMFZqxt3E"
ADMIN_ID = 6253584826
PUBLIC_CHANNEL_ID = -1003807818260
VIP_CHANNEL_ID = -1003826269063
PUBLIC_LINK = "https://t.me/tradewithkailashh"
VIP_LINK = "https://t.me/+Snj0BVAwjDo3NTA1"
WEBSITE = "https://forexkailash.netlify.app"
COURSE_LINK = "https://forexkailash.netlify.app/course"
UPI = "kailashbhardwaj66-2@okicici"
CONTACT = "@forexkailash"
TWELVEDATA_API_KEY = "02ef5f7e644f43d18bbe5ae297d0666b"

# Trading pairs (same as before)
PAIRS = {
    "EURUSD": {"yf": "EURUSD=X", "td": "EUR/USD"},
    "GBPUSD": {"yf": "GBPUSD=X", "td": "GBP/USD"},
    "USDJPY": {"yf": "USDJPY=X", "td": "USD/JPY"},
    "AUDUSD": {"yf": "AUDUSD=X", "td": "AUD/USD"},
    "USDCAD": {"yf": "USDCAD=X", "td": "USD/CAD"},
    "XAUUSD": {"yf": "GC=F", "td": "XAU/USD"},
    "XAGUSD": {"yf": "SI=F", "td": "XAG/USD"},
    "USOIL": {"yf": "CL=F", "td": "WTI"},
    "BTCUSD": {"yf": "BTC-USD", "td": "BTC/USD"},
    "ETHUSD": {"yf": "ETH-USD", "td": "ETH/USD"},
    "NIFTY50": {"yf": "^NSEI", "td": "NIFTY50"},
    "SENSEX": {"yf": "^BSESN", "td": "SENSEX"},
    "NASDAQ": {"yf": "^IXIC", "td": "IXIC"},
    "DOWJONES": {"yf": "^DJI", "td": "DJI"}
}

# Promos (shortened for brevity, but you can keep full list)
PUBLIC_PROMOS = [
    "🔥🚀 JOIN VIP FOR HIGH ACCURACY SIGNALS! 🚀🔥\n\n✅ 20-25 SIGNALS DAILY\n✅ TP/SL WITH EVERY SIGNAL\n✅ MULTI ASSET COVERAGE\n👉 {vip_link}",
    "💰💎 STOP LOSING, START WINNING! 💎💰\nVIP MEMBERS GET EXACT ENTRY ZONE, 3 TPs, SL.\nJOIN NOW: {vip_link}"
]
VIP_PROMOS = [
    "🎓🚀 MASTER THE MARKETS WITH OUR COURSE! 🚀🎓\n✅ COMPLETE FOREX COURSE\n👉 {course_link}",
    "📚💰 FROM ZERO TO HERO 💰📚\nCOURSE INCLUDES INDICATORS MASTERY & RISK MANAGEMENT.\n{contact} FOR DETAILS!"
]

# ===================== LOGGING =====================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ===================== DATABASE =====================
db_lock = threading.Lock()

def init_db():
    with db_lock:
        conn = sqlite3.connect('trading_bot.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY, name TEXT, free_signals_used INTEGER DEFAULT 0, is_vip INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS signals
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      symbol TEXT, direction TEXT, entry REAL, tp1 REAL, tp2 REAL, tp3 REAL, sl REAL,
                      confidence INTEGER, holding_period TEXT, reason TEXT,
                      timestamp TEXT, status TEXT, is_public INTEGER,
                      chat_id INTEGER, message_id INTEGER,
                      tp1_hit INTEGER DEFAULT 0, tp2_hit INTEGER DEFAULT 0, tp3_hit INTEGER DEFAULT 0)''')
        conn.commit()
        conn.close()

init_db()

def db_execute(query, params=()):
    with db_lock:
        conn = sqlite3.connect('trading_bot.db', check_same_thread=False)
        c = conn.cursor()
        c.execute(query, params)
        conn.commit()
        last_id = c.lastrowid
        conn.close()
        return last_id

def db_fetch_one(query, params=()):
    with db_lock:
        conn = sqlite3.connect('trading_bot.db', check_same_thread=False)
        c = conn.cursor()
        c.execute(query, params)
        result = c.fetchone()
        conn.close()
        return result

def db_fetch_all(query, params=()):
    with db_lock:
        conn = sqlite3.connect('trading_bot.db', check_same_thread=False)
        c = conn.cursor()
        c.execute(query, params)
        result = c.fetchall()
        conn.close()
        return result

# ===================== INDICATORS & ANALYSIS =====================
def get_price_data(symbol):
    yf_symbol = PAIRS[symbol]["yf"]
    try:
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period="5d", interval="1h")
        if len(hist) >= 20:
            data = hist[['Open', 'High', 'Low', 'Close']].tail(100)
            current_price = hist['Close'].iloc[-1]
            return data, current_price
    except Exception as e:
        logger.error(f"YFinance failed for {symbol}: {e}")
    return None, None

def calculate_sma(data, period):
    if len(data) < period:
        return None
    return sum(data[-period:]) / period

def calculate_ema(data, period):
    if len(data) < period:
        return None
    k = 2 / (period + 1)
    ema = data[0]
    for price in data[1:]:
        ema = price * k + ema * (1 - k)
    return ema

def calculate_rsi(data, period=14):
    if len(data) < period + 1:
        return 50
    gains, losses = 0, 0
    for i in range(-period, 0):
        change = data[i] - data[i-1]
        if change > 0:
            gains += change
        else:
            losses += abs(change)
    if losses == 0:
        return 100
    rs = gains / losses
    return 100 - (100 / (1 + rs))

def analyze_symbol(symbol):
    data, current_price = get_price_data(symbol)
    if data is None or current_price is None or len(data) < 50:
        return 0, None, None, None, None, None, None, 0, "", "Insufficient data"
    
    closes = data['Close'].tolist()
    highs = data['High'].tolist()
    lows = data['Low'].tolist()
    
    sma20 = calculate_sma(closes, 20)
    sma50 = calculate_sma(closes, 50)
    ema20 = calculate_ema(closes, 20)
    rsi = calculate_rsi(closes, 14)
    
    direction = None
    score = 0
    if sma20 and sma50:
        if current_price > sma20 and sma20 > sma50:
            score += 30
            direction = "BUY"
        elif current_price < sma20 and sma20 < sma50:
            score += 30
            direction = "SELL"
    
    if direction == "BUY" and rsi < 30:
        score += 25
    elif direction == "SELL" and rsi > 70:
        score += 25
    else:
        score += 15
    
    if ema20:
        if direction == "BUY" and current_price > ema20:
            score += 15
        elif direction == "SELL" and current_price < ema20:
            score += 15
    
    if score < 40 or direction is None:
        return 0, None, None, None, None, None, None, 0, "", "Score below threshold"
    
    # ATR approximation
    atr = (max(highs[-14:]) - min(lows[-14:])) / 14
    if atr == 0:
        atr = current_price * 0.01
    
    entry = current_price
    if direction == "BUY":
        sl = entry - atr * 1.5
        tp1 = entry + atr * 1.5
        tp2 = entry + atr * 2.5
        tp3 = entry + atr * 4
    else:
        sl = entry + atr * 1.5
        tp1 = entry - atr * 1.5
        tp2 = entry - atr * 2.5
        tp3 = entry - atr * 4
    
    confidence = int(score)
    holding_period = "4-6 hours"
    reason = f"Trend: {direction}, RSI: {rsi:.1f}, Price vs SMA20/SMA50"
    
    return score, direction, round(entry, 4), round(tp1, 4), round(tp2, 4), round(tp3, 4), round(sl, 4), confidence, holding_period, reason

def generate_and_send_signal(symbol, is_public, chat_id):
    try:
        score, direction, entry, tp1, tp2, tp3, sl, confidence, holding_period, reason = analyze_symbol(symbol)
        if score < 40 or direction is None:
            return False
        
        signal_text = f"""🔔 *{symbol} SIGNAL* 🔔

*Direction:* {direction}
*Entry Zone:* {entry}
*TP1:* {tp1}
*TP2:* {tp2}
*TP3:* {tp3}
*SL:* {sl}
*Confidence:* {confidence}%
*Holding Period:* {holding_period}

*Analysis:* {reason}

#Signal #{symbol}"""
        
        bot_instance = telebot.TeleBot(BOT_TOKEN)
        msg = bot_instance.send_message(chat_id, signal_text, parse_mode='Markdown')
        
        db_execute("""INSERT INTO signals 
            (symbol, direction, entry, tp1, tp2, tp3, sl, confidence, holding_period, reason, 
             timestamp, status, is_public, chat_id, message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (symbol, direction, entry, tp1, tp2, tp3, sl, confidence, holding_period, reason,
             datetime.now().isoformat(), 'active', 1 if is_public else 0, chat_id, msg.message_id))
        return True
    except Exception as e:
        logger.error(f"Signal generation error: {e}")
        return False

def monitor_signals():
    while True:
        try:
            active = db_fetch_all("SELECT id, symbol, direction, tp1, tp2, tp3, sl, is_public, chat_id, message_id, tp1_hit, tp2_hit, tp3_hit FROM signals WHERE status='active'")
            for sig in active:
                sig_id, symbol, direction, tp1, tp2, tp3, sl, is_public, chat_id, msg_id, tp1_hit, tp2_hit, tp3_hit = sig
                _, current_price = get_price_data(symbol)
                if current_price is None:
                    continue
                bot_instance = telebot.TeleBot(BOT_TOKEN)
                if direction == "BUY":
                    if not tp1_hit and current_price >= tp1:
                        send_profit_message(bot_instance, chat_id, symbol, direction, tp1, "TP1")
                        db_execute("UPDATE signals SET tp1_hit=1 WHERE id=?", (sig_id,))
                    if not tp2_hit and current_price >= tp2:
                        send_profit_message(bot_instance, chat_id, symbol, direction, tp2, "TP2")
                        db_execute("UPDATE signals SET tp2_hit=1 WHERE id=?", (sig_id,))
                    if not tp3_hit and current_price >= tp3:
                        send_profit_message(bot_instance, chat_id, symbol, direction, tp3, "TP3")
                        db_execute("UPDATE signals SET tp3_hit=1 WHERE id=?", (sig_id,))
                    if current_price <= sl:
                        if is_public:
                            try:
                                bot_instance.delete_message(chat_id, msg_id)
                            except:
                                pass
                        db_execute("UPDATE signals SET status='sl_hit' WHERE id=?", (sig_id,))
                else:  # SELL
                    if not tp1_hit and current_price <= tp1:
                        send_profit_message(bot_instance, chat_id, symbol, direction, tp1, "TP1")
                        db_execute("UPDATE signals SET tp1_hit=1 WHERE id=?", (sig_id,))
                    if not tp2_hit and current_price <= tp2:
                        send_profit_message(bot_instance, chat_id, symbol, direction, tp2, "TP2")
                        db_execute("UPDATE signals SET tp2_hit=1 WHERE id=?", (sig_id,))
                    if not tp3_hit and current_price <= tp3:
                        send_profit_message(bot_instance, chat_id, symbol, direction, tp3, "TP3")
                        db_execute("UPDATE signals SET tp3_hit=1 WHERE id=?", (sig_id,))
                    if current_price >= sl:
                        if is_public:
                            try:
                                bot_instance.delete_message(chat_id, msg_id)
                            except:
                                pass
                        db_execute("UPDATE signals SET status='sl_hit' WHERE id=?", (sig_id,))
            time.sleep(180)
        except Exception as e:
            logger.error(f"Monitor error: {e}")
            time.sleep(60)

def send_profit_message(bot, chat_id, symbol, direction, price, tp_level):
    try:
        profit_text = f"✅ *PROFIT TARGET HIT* ✅\n\nSymbol: {symbol}\nDirection: {direction}\n{tp_level}: {price}\nProfit Achieved! 🎉"
        bot.send_message(chat_id, profit_text, parse_mode='Markdown')
        # Generate screenshot
        img = Image.new('RGB', (800, 400), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 30)
            small_font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        draw.text((50, 50), "KAILASH TRADING", fill=(255, 215, 0), font=font)
        draw.text((50, 120), f"Symbol: {symbol}", fill=(255,255,255), font=small_font)
        draw.text((50, 170), f"Direction: {direction}", fill=(255,255,255), font=small_font)
        draw.text((50, 220), f"Profit: {tp_level} Hit at {price}", fill=(0,255,0), font=small_font)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        bot.send_photo(chat_id, photo=img_bytes, caption="🎯 Profit Target Achieved!")
    except Exception as e:
        logger.error(f"Profit message error: {e}")

def schedule_signals():
    last_public = 0
    last_vip = 0
    last_day = datetime.now().day
    while True:
        try:
            now = datetime.now()
            if now.day != last_day:
                last_public = 0
                last_vip = 0
                last_day = now.day
            if last_public < 6:
                for sym in random.sample(list(PAIRS.keys()), min(3, len(PAIRS))):
                    if generate_and_send_signal(sym, True, PUBLIC_CHANNEL_ID):
                        last_public += 1
                        time.sleep(300)
                        if last_public >= 8:
                            break
            if last_vip < 20:
                for sym in random.sample(list(PAIRS.keys()), min(5, len(PAIRS))):
                    if generate_and_send_signal(sym, False, VIP_CHANNEL_ID):
                        last_vip += 1
                        time.sleep(900)
                        if last_vip >= 25:
                            break
            time.sleep(3600)
        except Exception as e:
            logger.error(f"Schedule error: {e}")
            time.sleep(300)

def send_promos():
    while True:
        try:
            bot_instance = telebot.TeleBot(BOT_TOKEN)
            public_promo = random.choice(PUBLIC_PROMOS).format(vip_link=VIP_LINK, contact=CONTACT, course_link=COURSE_LINK)
            bot_instance.send_message(PUBLIC_CHANNEL_ID, public_promo, parse_mode='Markdown')
            vip_promo = random.choice(VIP_PROMOS).format(course_link=COURSE_LINK, contact=CONTACT)
            bot_instance.send_message(VIP_CHANNEL_ID, vip_promo, parse_mode='Markdown')
            time.sleep(1800)
        except Exception as e:
            logger.error(f"Promo error: {e}")
            time.sleep(300)

# ===================== TELEGRAM BOT HANDLERS =====================
bot = telebot.TeleBot(BOT_TOKEN)

def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📝 Register", callback_data="register"),
        InlineKeyboardButton("💎 Join VIP", callback_data="vip"),
        InlineKeyboardButton("📢 Join Free Channel", callback_data="free_channel"),
        InlineKeyboardButton("🎁 Get Free Signal", callback_data="free_signal"),
        InlineKeyboardButton("🌐 Website", callback_data="website"),
        InlineKeyboardButton("🆘 Support", callback_data="support")
    )
    return kb

@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        bot.send_message(message.chat.id, 
            "🚀 *Welcome to KAILASH TRADING* 🚀\n\nGet accurate Forex, Commodities, Crypto & Indices signals.\n\nUse buttons below:",
            reply_markup=main_menu(), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Start error: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        if call.data == "register":
            user = db_fetch_one("SELECT * FROM users WHERE user_id=?", (call.from_user.id,))
            if not user:
                db_execute("INSERT INTO users (user_id, name) VALUES (?, ?)", (call.from_user.id, call.from_user.first_name))
                bot.answer_callback_query(call.id, "✅ Registration successful!")
                bot.edit_message_text("✅ Registered! Use /menu", call.message.chat.id, call.message.message_id)
            else:
                bot.answer_callback_query(call.id, "Already registered!")
        elif call.data == "vip":
            text = f"💎 *JOIN VIP* 💎\nUPI: `{UPI}`\nContact: {CONTACT}\nVIP Link: {VIP_LINK}"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        elif call.data == "free_channel":
            bot.edit_message_text(f"📢 Join free channel:\n{PUBLIC_LINK}", call.message.chat.id, call.message.message_id)
        elif call.data == "free_signal":
            user = db_fetch_one("SELECT free_signals_used FROM users WHERE user_id=?", (call.from_user.id,))
            if not user:
                bot.answer_callback_query(call.id, "Please /start and register first!")
                return
            used = user[0]
            if used >= 3:
                bot.edit_message_text(f"❌ FREE LIMIT ENDED ❌\nJoin VIP: {VIP_LINK}", call.message.chat.id, call.message.message_id)
                return
            for sym in random.sample(list(PAIRS.keys()), len(PAIRS)):
                score, direction, entry, tp1, tp2, tp3, sl, conf, hold, reason = analyze_symbol(sym)
                if score >= 40:
                    signal_text = f"🔔 *FREE SIGNAL* 🔔\n\nSymbol: {sym}\nDirection: {direction}\nEntry: {entry}\nTP1: {tp1}\nTP2: {tp2}\nTP3: {tp3}\nSL: {sl}\nConfidence: {conf}%\n{reason}"
                    bot.send_message(call.message.chat.id, signal_text, parse_mode='Markdown')
                    db_execute("UPDATE users SET free_signals_used = free_signals_used + 1 WHERE user_id=?", (call.from_user.id,))
                    bot.answer_callback_query(call.id, f"Signal sent! Remaining: {2-used}")
                    break
            else:
                bot.answer_callback_query(call.id, "No signal now, try later.")
        elif call.data == "website":
            bot.edit_message_text(f"🌐 {WEBSITE}\n📚 {COURSE_LINK}", call.message.chat.id, call.message.message_id)
        elif call.data == "support":
            bot.edit_message_text(f"🆘 {CONTACT}", call.message.chat.id, call.message.message_id)
    except Exception as e:
        logger.error(f"Callback error: {e}")
        bot.answer_callback_query(call.id, "Error, try again.")

@bot.message_handler(commands=['free'])
def free_signal_cmd(message):
    # same logic as callback free_signal
    user = db_fetch_one("SELECT free_signals_used FROM users WHERE user_id=?", (message.from_user.id,))
    if not user:
        bot.reply_to(message, "Please /start and register first!")
        return
    used = user[0]
    if used >= 3:
        bot.reply_to(message, f"❌ FREE LIMIT ENDED ❌\nJoin VIP: {VIP_LINK}")
        return
    for sym in random.sample(list(PAIRS.keys()), len(PAIRS)):
        score, direction, entry, tp1, tp2, tp3, sl, conf, hold, reason = analyze_symbol(sym)
        if score >= 40:
            signal_text = f"🔔 *FREE SIGNAL* 🔔\n\nSymbol: {sym}\nDirection: {direction}\nEntry: {entry}\nTP1: {tp1}\nTP2: {tp2}\nTP3: {tp3}\nSL: {sl}\nConfidence: {conf}%\n{reason}"
            bot.send_message(message.chat.id, signal_text, parse_mode='Markdown')
            db_execute("UPDATE users SET free_signals_used = free_signals_used + 1 WHERE user_id=?", (message.from_user.id,))
            break
    else:
        bot.reply_to(message, "No signal available now.")

@bot.message_handler(commands=['vip'])
def vip_cmd(message):
    bot.reply_to(message, f"💎 VIP Info:\nUPI: `{UPI}`\nContact: {CONTACT}\nVIP Link: {VIP_LINK}", parse_mode='Markdown')

@bot.message_handler(commands=['support'])
def support_cmd(message):
    bot.reply_to(message, f"🆘 Contact: {CONTACT}")

# ===================== FLASK SERVER (KEEP ALIVE) =====================
flask_app = Flask(__name__)

@flask_app.route('/')
def index():
    return "Bot is running with polling!"

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# ===================== MAIN =====================
if __name__ == "__main__":
    # Start background threads
    threading.Thread(target=schedule_signals, daemon=True).start()
    threading.Thread(target=monitor_signals, daemon=True).start()
    threading.Thread(target=send_promos, daemon=True).start()
    # Start Flask to keep Railway from timing out
    threading.Thread(target=run_flask, daemon=True).start()
    # Start polling (this will block)
    logger.info("Starting bot in polling mode...")
    bot.infinity_polling(timeout=60, skip_pending=True)
