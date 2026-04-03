import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yfinance as yf
import requests
import sqlite3
import threading
import time
import random
import logging
import traceback
from datetime import datetime, timedelta
from collections import deque
from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont
import io
import os
import sys

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
WEBHOOK_URL = "https://tele-bot-2-production.up.railway.app/webhook"

# Trading pairs with Yahoo Finance and TwelveData symbols
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

# Promo messages (30 unique for public, 15 for VIP)
PUBLIC_PROMOS = [
    "🔥🚀 JOIN VIP FOR HIGH ACCURACY SIGNALS! 🚀🔥\n\n✅ 20-25 SIGNALS DAILY\n✅ TP/SL WITH EVERY SIGNAL\n✅ MULTI ASSET COVERAGE (FOREX, COMMODITIES, CRYPTO, INDICES)\n✅ 85%+ ACCURACY\n✅ DETAILED MARKET ANALYSIS\n\n👉 CLICK: {vip_link}",
    "💰💎 STOP LOSING, START WINNING! 💎💰\n\nVIP MEMBERS GET:\n🎯 EXACT ENTRY ZONE\n🎯 3 TAKE PROFITS\n🎯 STOP LOSS INCLUDED\n🎯 REAL-TIME UPDATES\n\nJOIN NOW: {vip_link}",
    "📊⚡ LIMITED TIME OFFER ⚡📊\n\nVIP CHANNEL FEATURES:\n• 20-25 PROFESSIONAL SIGNALS/DAY\n• ADVANCED TECHNICAL ANALYSIS\n• RISK MANAGEMENT INCLUDED\n• 24/7 SUPPORT\n\n{contact} TO UPGRADE!",
    "🏆📈 WORLD CLASS TRADING SIGNALS 📈🏆\n\nVIP EXPERIENCE:\n🔹 FOREX + COMMODITIES + CRYPTO\n🔹 INSTANT TP/SL ALERTS\n🔹 MARKET STRUCTURE BREAKDOWNS\n🔹 CONSISTENT PROFITS\n\n{contact} FOR VIP ACCESS",
    "🎯💯 90% ACCURACY RECORD! 💯🎯\n\nVIP SIGNALS GIVE YOU:\n✅ REAL-TIME BUY/SELL\n✅ MULTIPLE TIME FRAMES\n✅ PROFESSIONAL RISK REWARD\n✅ DAILY PROFIT TARGETS\n\nJOIN: {vip_link}",
    "🔥💪 BECOME A PROFESSIONAL TRADER 💪🔥\n\nVIP BENEFITS:\n• 20+ SIGNALS DAILY\n• COMPLETE TP/SL STRATEGY\n• COMMODITY & CRYPTO COVERAGE\n• LIVE SUPPORT\n\n{contact} TO JOIN VIP!",
    "💰📊 STOP GUESSING, START TRENDING 📊💰\n\nVIP CHANNEL OFFERS:\n🎯 ACCURATE ENTRY/EXIT\n🎯 HOLDING PERIOD\n🎯 MARKET SENTIMENT\n🎯 RISK REWARD RATIO\n\n{contact} FOR VIP MEMBERSHIP",
    "⚡🚨 LIMITED VIP SLOTS! 🚨⚡\n\nGET ACCESS TO:\n✔️ INSTANT SIGNAL NOTIFICATIONS\n✔️ MULTI-PAIR COVERAGE\n✔️ WEEKEND MARKET OUTLOOK\n✔️ PERSONAL MENTORING\n\n{contact} NOW!",
    "🏦📉 SMART MONEY STRATEGIES 📉🏦\n\nVIP MEMBERS RECEIVE:\n🔹 INSTITUTIONAL GRADE ANALYSIS\n🔹 ENTRY ZONE + 3 TP'S\n🔹 STOP LOSS PROTECTION\n🔹 DAILY RECAP VIDEOS\n\n{vip_link}",
    "📈🎓 TURN $100 INTO $1000 🎓📈\n\nVIP SIGNALS:\n✅ HIGH PROBABILITY SETUPS\n✅ 1:2 RISK REWARD MINIMUM\n✅ TREND CONFIRMATION\n✅ MOMENTUM INDICATORS\n\n{contact} TO START!",
    "🚀💸 CRYPTO + FOREX COMBO 💸🚀\n\nVIP ADVANTAGE:\n• BTC, ETH, XAU, OIL, EURUSD, ETC\n• 20-25 SIGNALS/DAY\n• TP1, TP2, TP3 HIT RATIO\n• LIVE MONITORING\n\nJOIN {vip_link}",
    "🔥✅ VERIFIED PROFITS ✅🔥\n\nVIP FEATURES:\n✅ SIGNALS WITH CONFIDENCE %\n✅ STRUCTURAL ANALYSIS\n✅ SUPPORT/RESISTANCE LEVELS\n✅ MOMENTUM FILTERS\n\n{contact} FOR VIP",
    "💎🎯 3 TAKE PROFITS EVERY SIGNAL 🎯💎\n\nVIP EXPERIENCE:\n🔹 ENTRY ZONE, TP1, TP2, TP3\n🔹 TRAILING STOP LOSS\n🔹 MARKET STRUCTURE BREAKS\n🔹 REAL-TIME ALERTS\n\n{vip_link}",
    "📊⚡ ACCURACY GUARANTEED ⚡📊\n\nVIP SERVICE INCLUDES:\n🎯 20-25 SIGNALS/DAY\n🎯 RISK REWARD CALCULATED\n🎯 TREND STRENGTH METER\n🎯 DAILY MARKET REPORT\n\n{contact} TO JOIN!",
    "🏆💰 JOIN 5000+ SUCCESSFUL TRADERS 💰🏆\n\nVIP SIGNALS:\n✅ MULTI ASSET (FOREX, COMMODITIES, INDICES)\n✅ TP/SL FOR EVERY TRADE\n✅ 85%+ WIN RATE\n✅ 24/7 SUPPORT\n\n{vip_link}",
    "🔥🚨 LAST CHANCE 🚨🔥\n\nVIP BENEFITS:\n• INSTANT ALERTS\n• COMPLETE ANALYSIS REASON\n• HOLDING PERIOD GUIDANCE\n• PRIVATE COMMUNITY\n\n{contact} TO JOIN VIP",
    "💎📈 PROFESSIONAL TRADING EDGE 📈💎\n\nVIP MEMBERS GET:\n✅ ENTRY ZONE + 3 PROFIT TARGETS\n✅ STOP LOSS PROTECTION\n✅ CONFIDENCE LEVEL\n✅ DETAILED RATIONALE\n\n{vip_link}",
    "⚡🎯 100% NON-REPAINTING SIGNALS 🎯⚡\n\nVIP ADVANTAGE:\n🔹 REAL MARKET STRUCTURE\n🔹 ORDER FLOW ANALYSIS\n🔹 HIGH ACCURACY SETUPS\n🔹 FAST EXECUTION\n\n{contact} FOR VIP!",
    "🔥📉 BEAT THE MARKET 📉🔥\n\nVIP FEATURES:\n✔️ 20-25 SIGNALS DAILY\n✔️ FOREX, COMMODITIES, CRYPTO, INDICES\n✔️ TP/SL WITH RATIO\n✔️ PROFESSIONAL SUPPORT\n\n{vip_link}",
    "💰🔔 NEVER MISS A TRADE 🔔💰\n\nVIP CHANNEL:\n🎯 INSTANT NOTIFICATIONS\n🎯 PREMIUM ANALYSIS\n🎯 SCALPING + SWING SETUPS\n🎯 WEEKLY PERFORMANCE REPORT\n\n{contact} TO JOIN!",
    "📊🚨 HIGH PROBABILITY SETUPS 🚨📊\n\nVIP SIGNALS INCLUDE:\n✅ BUY/SELL WITH ENTRY ZONE\n✅ 3 TAKE PROFIT LEVELS\n✅ STOP LOSS MANDATORY\n✅ CONFIDENCE SCORE\n\n{vip_link}",
    "🔥💵 MAKE MONEY WHILE YOU SLEEP 💵🔥\n\nVIP ADVANTAGE:\n• 20+ SIGNALS/DAY\n• AUTO TP/SL MONITORING\n• MARKET INSIGHTS\n• PRIVATE VIP GROUP\n\n{contact} FOR VIP!",
    "🏆📈 TRADE LIKE A PRO 📈🏆\n\nVIP MEMBERSHIP INCLUDES:\n✅ INSTITUTIONAL GRADE SIGNALS\n✅ MULTI TIME FRAME CONFIRMATION\n✅ EXACT ENTRY/EXIT\n✅ DAILY PROFIT PROJECTIONS\n\n{vip_link}",
    "⚡💰 LIMITED OFFER 💰⚡\n\nVIP BENEFITS:\n🔹 FOREX, GOLD, OIL, CRYPTO, INDICES\n🔹 TP1, TP2, TP3 STRATEGY\n🔹 RISK MANAGEMENT TIPS\n🔹 24/7 SUPPORT\n\n{contact} TO UPGRADE",
    "🔥✅ 3 FREE SIGNALS ON JOIN ✅🔥\n\nVIP CHANNEL OFFERS:\n✅ 20-25 ACCURATE SIGNALS\n✅ REAL-TIME UPDATES\n✅ COMPLETE TP/SL\n✅ PRIVATE ANALYSIS\n\n{vip_link}",
    "💎📊 ADVANCED TECHNICAL ANALYSIS 📊💎\n\nVIP FEATURES:\n🎯 SMA, RSI, MACD, MARKET STRUCTURE\n🎯 SUPPORT/RESISTANCE ZONES\n🎯 TREND STRENGTH METER\n🎯 MOMENTUM FILTER\n\n{contact} TO JOIN!",
    "🚀🔥 CRYPTO MASTERY 🔥🚀\n\nVIP SIGNALS:\n• BTCUSD, ETHUSD + MORE\n• ENTRY ZONE + 3 TPS\n• STOP LOSS INCLUDED\n• HIGH ACCURACY\n\n{vip_link}",
    "🏦💰 FOREX DOMINATION 💰🏦\n\nVIP ADVANTAGE:\n✅ EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD\n✅ ALL SIGNALS WITH TP/SL\n✅ MARKET STRUCTURE ANALYSIS\n✅ DAILY PROFIT TARGETS\n\n{contact} FOR VIP",
    "📈⚡ SMART MONEY SIGNALS ⚡📈\n\nVIP MEMBERS GET:\n🔹 INSTANT BUY/SELL ALERTS\n🔹 3 TAKE PROFITS\n🔹 STOP LOSS PROTECTION\n🔹 HOLDING PERIOD\n\n{vip_link}",
    "🔥🎯 85% WIN RATE GUARANTEED 🎯🔥\n\nVIP SERVICE:\n✅ 20-25 SIGNALS DAILY\n✅ MULTI ASSET COVERAGE\n✅ DETAILED ANALYSIS REASON\n✅ LIVE SUPPORT\n\n{contact} TO JOIN!"
]

VIP_PROMOS = [
    "🎓🚀 MASTER THE MARKETS WITH OUR COURSE! 🚀🎓\n\n✅ COMPLETE FOREX COURSE\n✅ ADVANCED TECHNICAL ANALYSIS\n✅ RISK MANAGEMENT STRATEGIES\n✅ LIVE TRADING SESSIONS\n\n👉 {course_link}",
    "📚💰 FROM ZERO TO HERO 💰📚\n\nCOURSE INCLUDES:\n🎯 CANDLESTICK PATTERNS\n🎯 INDICATORS MASTERY\n🎯 MARKET STRUCTURE\n🎯 PSYCHOLOGY & MONEY MANAGEMENT\n\n{contact} FOR DETAILS!",
    "🏆📈 BECOME A PROFESSIONAL TRADER 📈🏆\n\nLEARN:\n✅ SMA, RSI, MACD, EMA\n✅ SUPPORT/RESISTANCE\n✅ TREND STRENGTH ANALYSIS\n✅ SIGNAL GENERATION\n\n{course_link}",
    "💎🎯 PRO TRADING STRATEGIES 🎯💎\n\nCOURSE HIGHLIGHTS:\n🔹 SCALPING, DAY TRADING, SWING\n🔹 MULTI TIME FRAME ANALYSIS\n🔹 RISK REWARD CALCULATION\n🔹 BACKTESTING METHODS\n\n{contact} TO ENROLL!",
    "🔥📚 LEARN TO TRADE LIKE A PRO 📚🔥\n\nWHAT YOU GET:\n✅ 10+ MODULES\n✅ VIDEO TUTORIALS\n✅ LIVE EXAMPLES\n✅ CERTIFICATE UPON COMPLETION\n\n{course_link}",
    "💰💡 SECRETS OF SUCCESSFUL TRADERS 💡💰\n\nCOURSE INCLUDES:\n🎯 ENTRY ZONE IDENTIFICATION\n🎯 TP/SL PLACEMENT\n🎯 HOLDING PERIOD OPTIMIZATION\n🎯 CONFIDENCE SCORING\n\n{contact} NOW!",
    "📊⚡ COMPLETE TRADING BLUEPRINT ⚡📊\n\nLEARN:\n✅ FOREX, COMMODITIES, CRYPTO, INDICES\n✅ FUNDAMENTAL + TECHNICAL ANALYSIS\n✅ TRADING PSYCHOLOGY\n✅ JOURNALING & REVIEW\n\n{course_link}",
    "🏆🎓 CERTIFIED FOREX TRADER 🎓🏆\n\nCOURSE BENEFITS:\n🔹 SELF PACED LEARNING\n🔹 LIFETIME ACCESS\n🔹 COMMUNITY SUPPORT\n🔹 REGULAR UPDATES\n\n{contact} FOR INFO!",
    "🔥💵 TURN $500 INTO $5000 💵🔥\n\nCOURSE MODULES:\n✅ RISK MANAGEMENT\n✅ POSITION SIZING\n✅ TRADE MANAGEMENT\n✅ PROFIT TAKING STRATEGIES\n\n{course_link}",
    "📈🚀 ACCELERATE YOUR TRADING 🚀📈\n\nCOURSE FEATURES:\n🎯 INDICATORS MASTERY\n🎯 MARKET STRUCTURE BREAKS\n🎯 MOMENTUM CONFIRMATION\n🎯 LIVE TRADE EXAMPLES\n\n{contact} TO JOIN!",
    "💎📊 ADVANCED PRICE ACTION 📊💎\n\nLEARN:\n✅ SUPPORT & RESISTANCE PRO\n✅ TRENDLINES & CHANNELS\n✅ REVERSAL PATTERNS\n✅ BREAKOUT STRATEGIES\n\n{course_link}",
    "⚡🎯 30 DAYS PROFESSIONAL COURSE 🎯⚡\n\nCOURSE INCLUDES:\n🔹 DAILY LIVE SESSIONS\n🔹 HOMEWORK ASSIGNMENTS\n🔹 ONE ON ONE MENTORING\n🔹 TRADING PLAN DEVELOPMENT\n\n{contact} TO ENROLL!",
    "🏦💰 INSTITUTIONAL TRADING SECRETS 💰🏦\n\nCOURSE HIGHLIGHTS:\n✅ ORDER FLOW ANALYSIS\n✅ SMART MONEY CONCEPTS\n✅ LIQUIDITY GRABS\n✅ MARKET MANIPULATION\n\n{course_link}",
    "🔥📉 MASTER RISK REWARD 📉🔥\n\nLEARN:\n🎯 1:2, 1:3 RATIOS\n🎯 STOP LOSS PLACEMENT\n🎯 TRAILING STOPS\n🎯 PARTIAL PROFIT TAKING\n\n{contact} FOR COURSE!",
    "💎🎯 TRADE ANY MARKET WITH CONFIDENCE 🎯💎\n\nCOURSE OUTCOME:\n✅ CONSISTENT PROFITS\n✅ EMOTIONAL CONTROL\n✅ DISCIPLINED APPROACH\n✅ FINANCIAL FREEDOM\n\n{course_link}"
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

def db_fetch_all(query, params=()):
    with db_lock:
        conn = sqlite3.connect('trading_bot.db', check_same_thread=False)
        c = conn.cursor()
        c.execute(query, params)
        result = c.fetchall()
        conn.close()
        return result

def db_fetch_one(query, params=()):
    with db_lock:
        conn = sqlite3.connect('trading_bot.db', check_same_thread=False)
        c = conn.cursor()
        c.execute(query, params)
        result = c.fetchone()
        conn.close()
        return result

# ===================== HELPER FUNCTIONS =====================
def get_price_data(symbol):
    """Fetch last 100 candles and current price with fallback"""
    yf_symbol = PAIRS[symbol]["yf"]
    td_symbol = PAIRS[symbol]["td"]
    # Try Yahoo Finance first
    try:
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period="5d", interval="1h")
        if len(hist) >= 20:
            data = hist[['Open', 'High', 'Low', 'Close']].tail(100)
            current_price = hist['Close'].iloc[-1]
            return data, current_price
    except Exception as e:
        logger.error(f"YFinance failed for {symbol}: {e}")
    
    # Fallback to TwelveData
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={td_symbol}&interval=1h&outputsize=100&apikey={TWELVEDATA_API_KEY}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        json_data = resp.json()
        if 'values' in json_data:
            values = json_data['values']
            if values:
                current_price = float(values[0]['close'])
                data_list = []
                for v in reversed(values[-100:]):
                    data_list.append({
                        'Open': float(v['open']),
                        'High': float(v['high']),
                        'Low': float(v['low']),
                        'Close': float(v['close'])
                    })
                # Return as list for compatibility (will be handled by analysis functions)
                return data_list, current_price
    except Exception as e:
        logger.error(f"TwelveData failed for {symbol}: {e}")
    
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
    gains = 0
    losses = 0
    for i in range(-period, 0):
        change = data[i] - data[i-1]
        if change > 0:
            gains += change
        else:
            losses += abs(change)
    if losses == 0:
        return 100
    rs = gains / losses
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(data, fast=12, slow=26, signal=9):
    if len(data) < slow + signal:
        return None, None, None
    ema_fast = calculate_ema(data, fast)
    ema_slow = calculate_ema(data, slow)
    if ema_fast is None or ema_slow is None:
        return None, None, None
    macd_line = ema_fast - ema_slow
    # Get signal line by EMA of macd_line (need series)
    macd_series = []
    for i in range(slow, len(data)):
        ef = calculate_ema(data[:i+1], fast)
        es = calculate_ema(data[:i+1], slow)
        if ef and es:
            macd_series.append(ef - es)
    if len(macd_series) < signal:
        return macd_line, None, None
    signal_line = calculate_ema(macd_series, signal)
    histogram = macd_line - signal_line if signal_line else 0
    return macd_line, signal_line, histogram

def find_support_resistance(data):
    # data can be list of dicts or DataFrame
    if hasattr(data, 'iloc'):  # DataFrame
        highs = [data['High'].iloc[i] for i in range(-50, 0)]
        lows = [data['Low'].iloc[i] for i in range(-50, 0)]
    else:  # list of dicts
        highs = [c['High'] for c in data[-50:]]
        lows = [c['Low'] for c in data[-50:]]
    resistance = max(highs)
    support = min(lows)
    return support, resistance

def analyze_symbol(symbol):
    """Returns (score, direction, entry, tp1, tp2, tp3, sl, confidence, holding_period, reason)"""
    data, current_price = get_price_data(symbol)
    if data is None or current_price is None or len(data) < 50:
        return 0, None, None, None, None, None, None, 0, "", "Insufficient data"
    
    # Extract closes based on data type
    if hasattr(data, 'iloc'):  # DataFrame
        closes = data['Close'].tolist()
        highs = data['High'].tolist()
        lows = data['Low'].tolist()
    else:  # list of dicts
        closes = [c['Close'] for c in data]
        highs = [c['High'] for c in data]
        lows = [c['Low'] for c in data]
    
    sma20 = calculate_sma(closes, 20)
    sma50 = calculate_sma(closes, 50)
    ema20 = calculate_ema(closes, 20)
    rsi = calculate_rsi(closes, 14)
    macd_line, signal_line, hist = calculate_macd(closes)
    
    support, resistance = find_support_resistance(data)
    
    # Trend strength
    trend_strength = 0
    direction = None
    if sma20 and sma50:
        if current_price > sma20 and sma20 > sma50:
            trend_strength += 30
            direction = "BUY"
        elif current_price < sma20 and sma20 < sma50:
            trend_strength += 30
            direction = "SELL"
    
    # RSI
    if rsi < 30:
        if direction == "BUY":
            trend_strength += 25
        else:
            trend_strength += 10
    elif rsi > 70:
        if direction == "SELL":
            trend_strength += 25
        else:
            trend_strength += 10
    else:
        trend_strength += 15
    
    # MACD
    if hist and hist > 0 and direction == "BUY":
        trend_strength += 20
    elif hist and hist < 0 and direction == "SELL":
        trend_strength += 20
    
    # Momentum confirmation
    if ema20 and current_price > ema20 and direction == "BUY":
        trend_strength += 15
    elif ema20 and current_price < ema20 and direction == "SELL":
        trend_strength += 15
    
    # Support/Resistance
    if direction == "BUY" and current_price <= support * 1.01:
        trend_strength += 10
    elif direction == "SELL" and current_price >= resistance * 0.99:
        trend_strength += 10
    
    score = min(100, trend_strength)
    if score < 40 or direction is None:
        return score, None, None, None, None, None, None, 0, "", "Score below threshold"
    
    # Calculate ATR for SL/TP
    atr = 0
    for i in range(1, min(14, len(closes))):
        tr = max(highs[-i] - lows[-i], abs(highs[-i] - closes[-i-1]), abs(lows[-i] - closes[-i-1]))
        atr += tr
    atr = atr / 14 if atr > 0 else current_price * 0.01
    
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
    reason = f"Trend: {direction}, RSI: {rsi:.1f}, MACD: {'Bullish' if hist>0 else 'Bearish'}, Price vs SMA20/SMA50"
    
    return score, direction, round(entry, 4), round(tp1, 4), round(tp2, 4), round(tp3, 4), round(sl, 4), confidence, holding_period, reason

# ===================== SIGNAL GENERATION =====================
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
        
        # Save to DB
        signal_id = db_execute("""INSERT INTO signals 
            (symbol, direction, entry, tp1, tp2, tp3, sl, confidence, holding_period, reason, 
             timestamp, status, is_public, chat_id, message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (symbol, direction, entry, tp1, tp2, tp3, sl, confidence, holding_period, reason,
             datetime.now().isoformat(), 'active', 1 if is_public else 0, chat_id, msg.message_id))
        return True
    except Exception as e:
        logger.error(f"Error generating signal for {symbol}: {e}")
        return False

# ===================== MONITOR SYSTEM =====================
def monitor_signals():
    while True:
        try:
            active_signals = db_fetch_all("SELECT id, symbol, direction, entry, tp1, tp2, tp3, sl, is_public, chat_id, message_id, tp1_hit, tp2_hit, tp3_hit FROM signals WHERE status='active'")
            for sig in active_signals:
                sig_id, symbol, direction, entry, tp1, tp2, tp3, sl, is_public, chat_id, msg_id, tp1_hit, tp2_hit, tp3_hit = sig
                _, current_price = get_price_data(symbol)
                if current_price is None:
                    continue
                
                bot_instance = telebot.TeleBot(BOT_TOKEN)
                # Check TP hits
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
                    # Check SL
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
            time.sleep(180)  # 3 minutes
        except Exception as e:
            logger.error(f"Monitor error: {e}")
            time.sleep(60)

def send_profit_message(bot, chat_id, symbol, direction, price, tp_level):
    try:
        profit_text = f"✅ *PROFIT TARGET HIT* ✅\n\nSymbol: {symbol}\nDirection: {direction}\n{tp_level}: {price}\nProfit Achieved! 🎉"
        bot.send_message(chat_id, profit_text, parse_mode='Markdown')
        # Generate and send screenshot
        img = Image.new('RGB', (800, 400), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 30)
            small_font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        draw.text((50, 50), f"KAILASH TRADING", fill=(255, 215, 0), font=font)
        draw.text((50, 120), f"Symbol: {symbol}", fill=(255, 255, 255), font=small_font)
        draw.text((50, 170), f"Direction: {direction}", fill=(255, 255, 255), font=small_font)
        draw.text((50, 220), f"Profit: {tp_level} Hit at {price}", fill=(0, 255, 0), font=small_font)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        bot.send_photo(chat_id, photo=img_bytes, caption="🎯 Profit Target Achieved!")
    except Exception as e:
        logger.error(f"Error sending profit message: {e}")

# ===================== SCHEDULED SIGNALS =====================
last_public_signals = 0
last_vip_signals = 0
last_reset_day = datetime.now().day

def schedule_signals():
    global last_public_signals, last_vip_signals, last_reset_day
    while True:
        try:
            # Reset daily counters
            now = datetime.now()
            if now.day != last_reset_day:
                last_public_signals = 0
                last_vip_signals = 0
                last_reset_day = now.day
            
            # Generate public signals (6-8 per day)
            if last_public_signals < 6:
                symbols = list(PAIRS.keys())
                random.shuffle(symbols)
                for sym in symbols:
                    if generate_and_send_signal(sym, True, PUBLIC_CHANNEL_ID):
                        last_public_signals += 1
                        time.sleep(300)  # 5 min between signals
                        if last_public_signals >= 8:
                            break
            
            # Generate VIP signals (20-25 per day)
            if last_vip_signals < 20:
                symbols = list(PAIRS.keys())
                random.shuffle(symbols)
                for sym in symbols:
                    if generate_and_send_signal(sym, False, VIP_CHANNEL_ID):
                        last_vip_signals += 1
                        time.sleep(900)  # 15 min between VIP signals
                        if last_vip_signals >= 25:
                            break
            
            time.sleep(3600)  # Check every hour
        except Exception as e:
            logger.error(f"Schedule error: {e}")
            time.sleep(300)

# ===================== PROMO SYSTEM =====================
def send_promos():
    while True:
        try:
            bot_instance = telebot.TeleBot(BOT_TOKEN)
            # Public channel promo
            public_promo = random.choice(PUBLIC_PROMOS).format(vip_link=VIP_LINK, contact=CONTACT, course_link=COURSE_LINK)
            bot_instance.send_message(PUBLIC_CHANNEL_ID, public_promo, parse_mode='Markdown')
            # VIP channel promo
            vip_promo = random.choice(VIP_PROMOS).format(course_link=COURSE_LINK, contact=CONTACT)
            bot_instance.send_message(VIP_CHANNEL_ID, vip_promo, parse_mode='Markdown')
            time.sleep(1800)  # 30 minutes
        except Exception as e:
            logger.error(f"Promo error: {e}")
            time.sleep(300)

# ===================== TELEGRAM BOT HANDLERS =====================
bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

def main_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📝 Register", callback_data="register"),
        InlineKeyboardButton("💎 Join VIP", callback_data="vip"),
        InlineKeyboardButton("📢 Join Free Channel", callback_data="free_channel"),
        InlineKeyboardButton("🎁 Get Free Signal", callback_data="free_signal"),
        InlineKeyboardButton("🌐 Website", callback_data="website"),
        InlineKeyboardButton("🆘 Support", callback_data="support")
    )
    return keyboard

@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        bot.send_message(message.chat.id, 
                         f"🚀 *Welcome to KAILASH TRADING* 🚀\n\nGet accurate Forex, Commodities, Crypto & Indices signals with high accuracy.\n\nUse the buttons below to get started:",
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
                bot.edit_message_text("✅ You are now registered! Use /menu to access features.", call.message.chat.id, call.message.message_id)
            else:
                bot.answer_callback_query(call.id, "Already registered!")
        elif call.data == "vip":
            text = f"💎 *JOIN VIP CHANNEL* 💎\n\nUPI: `{UPI}`\nContact: {CONTACT}\nVIP Link: {VIP_LINK}\n\nAfter payment, send screenshot to {CONTACT} for access."
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        elif call.data == "free_channel":
            bot.edit_message_text(f"📢 Join our free channel for daily updates:\n{PUBLIC_LINK}", call.message.chat.id, call.message.message_id)
        elif call.data == "free_signal":
            user = db_fetch_one("SELECT free_signals_used FROM users WHERE user_id=?", (call.from_user.id,))
            if not user:
                bot.answer_callback_query(call.id, "Please /start and register first!")
                return
            used = user[0]
            if used >= 3:
                bot.edit_message_text(f"❌ FREE LIMIT ENDED ❌\n\nJoin VIP for more signals: {VIP_LINK}\n\nJoin our free channel: {PUBLIC_LINK}", call.message.chat.id, call.message.message_id)
                return
            # Generate a random signal for user
            symbols = list(PAIRS.keys())
            random.shuffle(symbols)
            for sym in symbols:
                score, direction, entry, tp1, tp2, tp3, sl, confidence, holding, reason = analyze_symbol(sym)
                if score >= 40 and direction:
                    signal_text = f"🔔 *FREE SIGNAL* 🔔\n\nSymbol: {sym}\nDirection: {direction}\nEntry: {entry}\nTP1: {tp1}\nTP2: {tp2}\nTP3: {tp3}\nSL: {sl}\nConfidence: {confidence}%\nHolding: {holding}\n\n{reason}"
                    bot.send_message(call.message.chat.id, signal_text, parse_mode='Markdown')
                    db_execute("UPDATE users SET free_signals_used = free_signals_used + 1 WHERE user_id=?", (call.from_user.id,))
                    bot.answer_callback_query(call.id, "Signal sent! Remaining free signals: " + str(2-used))
                    break
            else:
                bot.answer_callback_query(call.id, "No signal available now. Try again later.")
        elif call.data == "website":
            bot.edit_message_text(f"🌐 Website: {WEBSITE}\n📚 Course: {COURSE_LINK}", call.message.chat.id, call.message.message_id)
        elif call.data == "support":
            bot.edit_message_text(f"🆘 Support: {CONTACT}", call.message.chat.id, call.message.message_id)
    except Exception as e:
        logger.error(f"Callback error: {e}")
        bot.answer_callback_query(call.id, "Error occurred. Try again.")

@bot.message_handler(commands=['free'])
def free_signal_cmd(message):
    try:
        user = db_fetch_one("SELECT free_signals_used FROM users WHERE user_id=?", (message.from_user.id,))
        if not user:
            bot.reply_to(message, "Please /start and register first!")
            return
        used = user[0]
        if used >= 3:
            bot.reply_to(message, f"❌ FREE LIMIT ENDED ❌\n\nJoin VIP: {VIP_LINK}\nFree Channel: {PUBLIC_LINK}")
            return
        symbols = list(PAIRS.keys())
        random.shuffle(symbols)
        for sym in symbols:
            score, direction, entry, tp1, tp2, tp3, sl, confidence, holding, reason = analyze_symbol(sym)
            if score >= 40 and direction:
                signal_text = f"🔔 *FREE SIGNAL* 🔔\n\nSymbol: {sym}\nDirection: {direction}\nEntry: {entry}\nTP1: {tp1}\nTP2: {tp2}\nTP3: {tp3}\nSL: {sl}\nConfidence: {confidence}%\nHolding: {holding}\n\n{reason}"
                bot.send_message(message.chat.id, signal_text, parse_mode='Markdown')
                db_execute("UPDATE users SET free_signals_used = free_signals_used + 1 WHERE user_id=?", (message.from_user.id,))
                break
        else:
            bot.reply_to(message, "No signal available now.")
    except Exception as e:
        logger.error(f"Free command error: {e}")

@bot.message_handler(commands=['vip'])
def vip_cmd(message):
    bot.reply_to(message, f"💎 VIP Info:\nUPI: `{UPI}`\nContact: {CONTACT}\nVIP Link: {VIP_LINK}", parse_mode='Markdown')

@bot.message_handler(commands=['support'])
def support_cmd(message):
    bot.reply_to(message, f"🆘 Contact: {CONTACT}")

# ===================== FLASK WEBHOOK =====================
flask_app = Flask(__name__)

@flask_app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return jsonify({'status': 'ok'})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'status': 'error'}), 500

@flask_app.route('/', methods=['GET'])
def index():
    return "Bot is running!"

def run_webhook():
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook set to {WEBHOOK_URL}")
        flask_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        # Fallback to polling
        logger.info("Falling back to polling mode")
        bot.polling(none_stop=True, interval=1)

# ===================== MAIN =====================
def main():
    # Start background threads
    threading.Thread(target=schedule_signals, daemon=True).start()
    threading.Thread(target=monitor_signals, daemon=True).start()
    threading.Thread(target=send_promos, daemon=True).start()
    
    # Start Flask webhook
    run_webhook()

if __name__ == "__main__":
    main()
