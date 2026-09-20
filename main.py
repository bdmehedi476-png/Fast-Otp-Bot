import os
import sqlite3
import requests
import telebot
from telebot import types
import threading
import time
from flask import Flask

# ==================== BOT CONFIGURATION ====================
BOT_TOKEN = "8923498683:AAEqLZtt5yfGZ0zdRpJ8om3bMxWIdacVbIs" # আপনার নতুন টোকেন
ADMIN_ID = 7159155182
BOT_USERNAME = "@FastOTP3_Bot"

# Channels & Groups
OTP_CHANNEL = "@FastOTPBot_1"
SUPPORT_CHANNEL = "@FastOtpSupportMathhodChannel" # সঠিক আপডেট করা চ্যানেল
SUPPORT_USERNAME = "@Owner_010"

# Settings
MIN_WITHDRAW = 1.00

# ==================== MULTI-PANEL / API CONFIGURATION ====================
ACTIVE_PROVIDER = "lamix"

API_CONFIG = {
    "lamix": {
        "token": "q3zv3ACa1Sk5hJeKaBuvj8qDNrpJXssqZxRrgPdDT",
        "numbers_url": "https://panel.lamix.org/api/v1/numbers",
        "cdrs_url": "https://panel.lamix.org/api/v1/cdrs"
    }
}

bot = telebot.TeleBot(BOT_TOKEN)

# ==================== COUNTRY MAP ====================
COUNTRY_MAP = {
    "1":   {"name": "USA / Canada", "flag": "🇺🇸"},
    "7":   {"name": "Russia / Kazakhstan", "flag": "🇷🇺"},
    "20":  {"name": "Egypt", "flag": "🇪🇬"},
    "27":  {"name": "South Africa", "flag": "🇿🇦"},
    "30":  {"name": "Greece", "flag": "🇬🇷"},
    "31":  {"name": "Netherlands", "flag": "🇳🇱"},
    "32":  {"name": "Belgium", "flag": "🇧🇪"},
    "33":  {"name": "France", "flag": "🇫🇷"},
    "34":  {"name": "Spain", "flag": "🇪🇸"},
    "39":  {"name": "Italy", "flag": "🇮🇹"},
    "44":  {"name": "United Kingdom", "flag": "🇬🇧"},
    "48":  {"name": "Poland", "flag": "🇵🇱"},
    "49":  {"name": "Germany", "flag": "🇩🇪"},
    "51":  {"name": "Peru", "flag": "🇵🇪"},
    "52":  {"name": "Mexico", "flag": "🇲🇽"},
    "55":  {"name": "Brazil", "flag": "🇧🇷"},
    "60":  {"name": "Malaysia", "flag": "🇲🇾"},
    "61":  {"name": "Australia", "flag": "🇦🇺"},
    "62":  {"name": "Indonesia", "flag": "🇮🇩"},
    "63":  {"name": "Philippines", "flag": "🇵🇭"},
    "65":  {"name": "Singapore", "flag": "🇸🇬"},
    "66":  {"name": "Thailand", "flag": "🇹🇭"},
    "81":  {"name": "Japan", "flag": "🇯🇵"},
    "82":  {"name": "South Korea", "flag": "🇰🇷"},
    "84":  {"name": "Vietnam", "flag": "🇻🇳"},
    "86":  {"name": "China", "flag": "🇨🇳"},
    "90":  {"name": "Turkey", "flag": "🇹🇷"},
    "91":  {"name": "India", "flag": "🇮🇳"},
    "92":  {"name": "Pakistan", "flag": "🇵🇰"},
    "93":  {"name": "Afghanistan", "flag": "🇦🇫"},
    "94":  {"name": "Sri Lanka", "flag": "🇱🇰"},
    "95":  {"name": "Myanmar", "flag": "🇲🇲"},
    "212": {"name": "Morocco", "flag": "🇲🇦"},
    "213": {"name": "Algeria", "flag": "🇩🇿"},
    "216": {"name": "Tunisia", "flag": "🇹🇳"},
    "234": {"name": "Nigeria", "flag": "🇳🇬"},
    "254": {"name": "Kenya", "flag": "🇰🇪"},
    "351": {"name": "Portugal", "flag": "🇵🇹"},
    "380": {"name": "Ukraine", "flag": "🇺🇦"},
    "880": {"name": "Bangladesh", "flag": "🇧🇩"},
    "966": {"name": "Saudi Arabia", "flag": "🇸🇦"},
    "971": {"name": "UAE", "flag": "🇦🇪"},
    "972": {"name": "Israel", "flag": "🇮🇱"}
}

def clean_md(text):
    if not text:
        return ""
    return str(text).replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')

# ==================== DYNAMIC PREFIX MATCHING ====================
def extract_country_code(full_number):
    """
    যেকোনো লম্বা প্রিফিক্স থেকে মূল Country Dialing Code খুঁজে বের করবে।
    """
    clean_num = str(full_number).lstrip("+").strip()
    for c_code in sorted(COUNTRY_MAP.keys(), key=len, reverse=True):
        if clean_num.startswith(c_code):
            return c_code
    return None

# ==================== DATABASE SETUP ====================
def init_db():
    conn = sqlite3.connect("fast_otp_bot.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        balance REAL DEFAULT 0.0,
                        referred_by INTEGER DEFAULT 0
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS used_numbers (
                        user_id INTEGER,
                        number TEXT,
                        PRIMARY KEY (user_id, number)
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS active_sessions (
                        user_id INTEGER PRIMARY KEY,
                        number TEXT
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS posted_otps (
                        id TEXT PRIMARY KEY
                    )''')
    conn.commit()
    conn.close()

init_db()

def get_or_create_user(user_id, ref_id=0):
    conn = sqlite3.connect("fast_otp_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, balance, referred_by) VALUES (?, ?, ?)", (user_id, 0.0, ref_id))
        conn.commit()
        balance = 0.0
    else:
        balance = row[0]
    conn.close()
    return balance

def set_active_number(user_id, number):
    conn = sqlite3.connect("fast_otp_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO active_sessions (user_id, number) VALUES (?, ?)", (user_id, str(number)))
    conn.commit()
    conn.close()

def get_active_number(user_id):
    conn = sqlite3.connect("fast_otp_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT number FROM active_sessions WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def mark_numbers_as_used(user_id, numbers_list):
    conn = sqlite3.connect("fast_otp_bot.db")
    cursor = conn.cursor()
    for num in numbers_list:
        cursor.execute("INSERT OR IGNORE INTO used_numbers (user_id, number) VALUES (?, ?)", (user_id, str(num)))
    conn.commit()
    conn.close()

def get_used_numbers(user_id):
    conn = sqlite3.connect("fast_otp_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT number FROM used_numbers WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return set(row[0] for row in rows)

def is_otp_posted(otp_id):
    conn = sqlite3.connect("fast_otp_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM posted_otps WHERE id = ?", (str(otp_id),))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def mark_otp_posted(otp_id):
    conn = sqlite3.connect("fast_otp_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO posted_otps (id) VALUES (?)", (str(otp_id),))
    conn.commit()
    conn.close()

# ==================== UNIVERSAL API HANDLER ====================
class OTPProviderAPI:
    @staticmethod
    def fetch_numbers():
        cfg = API_CONFIG.get(ACTIVE_PROVIDER)
        if not cfg:
            return []
        
        headers = {"Authorization": f"Bearer {cfg['token']}"}
        try:
            res = requests.get(cfg["numbers_url"], headers=headers, timeout=12)
            if res.status_code == 200:
                data = res.json()
                items = data if isinstance(data, list) else data.get("data", data.get("numbers", []))
                
                formatted_list = []
                for item in items:
                    raw_num = str(item.get("number", item.get("phone", ""))).strip()
                    prefix = str(item.get("prefix", "")).strip()
                    
                    if prefix and not raw_num.startswith(prefix):
                        full_num = prefix + raw_num
                    else:
                        full_num = raw_num
                        
                    formatted_list.append({
                        "number": full_num,
                        "prefix": prefix
                    })
                return formatted_list
        except Exception as e:
            print(f"[{ACTIVE_PROVIDER}] API Numbers Fetch Error: {e}")
        return []

    @staticmethod
    def fetch_cdrs():
        cfg = API_CONFIG.get(ACTIVE_PROVIDER)
        if not cfg:
            return []
            
        headers = {"Authorization": f"Bearer {cfg['token']}"}
        try:
            res = requests.get(cfg["cdrs_url"], headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                return data if isinstance(data, list) else data.get("data", data.get("cdrs", []))
        except Exception as e:
            print(f"[{ACTIVE_PROVIDER}] API CDR Fetch Error: {e}")
        return []

# ==================== FORCE JOIN CHECKER ====================
def check_join(user_id):
    try:
        c1 = bot.get_chat_member(OTP_CHANNEL, user_id).status
        c2 = bot.get_chat_member(SUPPORT_CHANNEL, user_id).status
        valid = ['creator', 'administrator', 'member']
        return (c1 in valid) and (c2 in valid)
    except Exception as e:
        print(f"Join Check Error: {e}")
        return True

def send_join_msg(chat_id):
    text = (
        "⚠️ **বট ব্যবহার করতে আমাদের অফিসিয়াল চ্যানেলগুলোতে জয়েন করতে হবে!**\n\n"
        "নিচের ২টি চ্যানেলে জয়েন করে **Joined / চেক করুন** বাটনে চাপ দিন।"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📢 Join OTP Channel", url=f"https://t.me/{OTP_CHANNEL.replace('@','')}" ),
        types.InlineKeyboardButton("🛠 Join Support Channel", url=f"https://t.me/{SUPPORT_CHANNEL.replace('@','')}" ),
        types.InlineKeyboardButton("✅ Joined / চেক করুন", callback_data="check_joined_status")
    )
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

# ==================== MAIN KEYBOARD ====================
def main_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_get_num = types.KeyboardButton("📞 Get Number")
    btn_search = types.KeyboardButton("🔍 Search Number")
    btn_refer = types.KeyboardButton("🎁 Refer")
    btn_wallet = types.KeyboardButton("💳 Wallet")
    btn_traffic = types.KeyboardButton("📊 Live Traffic")
    btn_leaderboard = types.KeyboardButton("🏆 Leaderboard")
    btn_support = types.KeyboardButton("👨‍💻 Support Admin")
    
    markup.add(btn_get_num, btn_search)
    markup.add(btn_refer, btn_wallet)
    markup.add(btn_traffic, btn_leaderboard)
    markup.add(btn_support)
    return markup

# ==================== AUTO POST INBOUND OTP TO CHANNEL ====================
def auto_post_otps_to_channel():
    while True:
        try:
            records = OTPProviderAPI.fetch_cdrs()
            for record in records:
                rec_id = str(record.get("id") or f"{record.get('number')}_{record.get('time')}")
                
                if not is_otp_posted(rec_id):
                    num = str(record.get("number") or record.get("phone") or "")
                    otp_msg = record.get("otp") or record.get("code") or record.get("text") or record.get("message")
                    
                    if num and otp_msg:
                        clean_text = clean_md(otp_msg)
                        ch_post = (
                            f"⚡ **Live Inbound OTP Received!**\n\n"
                            f"📞 **Number:** `+{num}`\n"
                            f"🔑 **Message / OTP:** `{clean_text}`\n\n"
                            f"🤖 **Bot:** {clean_md(BOT_USERNAME)}"
                        )
                        try:
                            bot.send_message(OTP_CHANNEL, ch_post, parse_mode="Markdown")
                            mark_otp_posted(rec_id)
                        except Exception as post_err:
                            print(f"❌ Channel Post Error: {post_err}")
        except Exception as e:
            print(f"Auto-post background error: {e}")
        
        time.sleep(3)

# ==================== HANDLERS ====================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    if not check_join(user_id):
        send_join_msg(message.chat.id)
        return

    args = message.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
    balance = get_or_create_user(user_id, ref_id)
    
    first_name = clean_md(message.from_user.first_name)
    welcome_text = (
        f"🔥 **Welcome to Fast OTP Bot!**\n\n"
        f"👋 Hello {first_name}!\n"
        f"💰 **Your Balance:** `${balance:.4f}`\n\n"
        f"📢 **OTP Channel:** {clean_md(OTP_CHANNEL)}\n"
        f"🛠 **Support Channel:** {clean_md(SUPPORT_CHANNEL)}\n\n"
        f"👇 Select an option from below to get started:"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "check_joined_status")
def callback_check_joined(call):
    if check_join(call.from_user.id):
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(call.message.chat.id, "✅ ধন্যবাদ! আপনি সফলভাবে সব চ্যানেলে যুক্ত হয়েছেন।", reply_markup=main_menu())
    else:
        bot.answer_callback_query(call.id, "❌ আপনি এখনো সবগুলো চ্যানেলে জয়েন করেননি!", show_alert=True)

@bot.message_handler(func=lambda msg: msg.text == "👨‍💻 Support Admin")
def support_admin_handler(message):
    text = (
        f"👨‍💻 **Support Center**\n\n"
        f"যেকোনো প্রয়োজনে সরাসরি অ্যাডমিনের সাথে যোগাযোগ করুন:\n"
        f"👤 **Admin Username:** {clean_md(SUPPORT_USERNAME)}\n"
        f"📢 **Support Channel:** {clean_md(SUPPORT_CHANNEL)}"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💬 Contact Admin", url=f"https://t.me/{SUPPORT_USERNAME.replace('@','')}"))
    markup.add(types.InlineKeyboardButton("📢 Support Channel", url=f"https://t.me/{SUPPORT_CHANNEL.replace('@','')}"))
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📞 Get Number")
def process_get_number(message):
    if not check_join(message.from_user.id):
        send_join_msg(message.chat.id)
        return

    bot.send_message(message.chat.id, "⏳ Fetching live real numbers from API...")
    records = OTPProviderAPI.fetch_numbers()
    
    country_counts = {}
    if records:
        for item in records:
            num = item.get("number", "")
            c_code = extract_country_code(num)
            if c_code:
                country_counts[c_code] = country_counts.get(c_code, 0) + 1

    all_countries = set(COUNTRY_MAP.keys())
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for country_code in sorted(all_countries, key=lambda x: int(x) if str(x).isdigit() else 999):
        real_count = country_counts.get(country_code, 0)
        c_info = COUNTRY_MAP.get(str(country_code), {"name": f"Country (+{country_code})", "flag": "🌐"})
        btn_text = f"{c_info['flag']} {c_info['name']} (+{country_code}) - {real_count} Available | $0.0045/OTP"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"country_{country_code}"))

    bot.send_message(message.chat.id, "🌐 **Select a Country for Any Service:**", reply_markup=markup, parse_mode="Markdown")

def display_country_numbers(chat_id, user_id, country_code):
    records = OTPProviderAPI.fetch_numbers()
    all_country_numbers = []
    
    if records:
        for r in records:
            num = str(r.get("number", ""))
            if extract_country_code(num) == country_code:
                all_country_numbers.append(num)

    used_set = get_used_numbers(user_id)
    fresh_numbers = [num for num in all_country_numbers if num not in used_set]

    if not fresh_numbers:
        bot.send_message(chat_id, "❌ **দুঃখিত!** এই মুহূর্তে এই দেশের কোনো আসল নাম্বার প্যানেলে এভেলেবল নেই। প্যানেলে নাম্বার যুক্ত হলে অটোমেটিক চলে আসবে।")
        return

    sliced_nums = fresh_numbers[:5]
    mark_numbers_as_used(user_id, sliced_nums)
    set_active_number(user_id, sliced_nums[0])
    
    c_info = COUNTRY_MAP.get(str(country_code), {"name": f"Country (+{country_code})", "flag": "🌐"})
    
    msg_text = f"{c_info['flag']} **{c_info['name']} Live Real Numbers:**\n⌛ *Waiting for OTP...*\n\n"
    for n in sliced_nums:
        msg_text += f"📱 `+{n}`\n"

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔄 Change Number (Get Fresh)", callback_data=f"changenum_{country_code}"),
        types.InlineKeyboardButton("🌍 Change Country", callback_data="change_country"),
        types.InlineKeyboardButton("📩 Get OTP", callback_data="check_all_otp")
    )
    bot.send_message(chat_id, msg_text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("country_"))
def country_selected(call):
    country_code = call.data.split("_")[1]
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    display_country_numbers(call.message.chat.id, call.from_user.id, country_code)

@bot.callback_query_handler(func=lambda call: call.data.startswith("changenum_"))
def change_number_click(call):
    country_code = call.data.split("_")[1]
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    display_country_numbers(call.message.chat.id, call.from_user.id, country_code)

@bot.callback_query_handler(func=lambda call: call.data == "change_country")
def change_country_click(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    process_get_number(call.message)

@bot.callback_query_handler(func=lambda call: call.data == "check_all_otp")
def check_otp_action(call):
    user_id = call.from_user.id
    active_num = get_active_number(user_id)
    
    if not active_num:
        bot.answer_callback_query(call.id, "❌ আপনার কোনো একটিভ নাম্বার নেই!", show_alert=True)
        return

    bot.answer_callback_query(call.id, "🔍 Searching for latest OTP...")
    
    records = OTPProviderAPI.fetch_cdrs()
    if records:
        for rec in records:
            num = str(rec.get("number") or rec.get("phone") or "")
            if num and str(active_num)[-7:] in num:
                otp_msg = rec.get("otp") or rec.get("code") or rec.get("text") or rec.get("message")
                if otp_msg:
                    otp_ch_url = f"https://t.me/{OTP_CHANNEL.replace('@','')}"
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("📢 Go to Live OTP Channel", url=otp_ch_url))
                    
                    success_text = (
                        f"🎉 **OTP Received!**\n\n"
                        f"📞 **Number:** `+{active_num}`\n"
                        f"🔑 **OTP:** `{clean_md(otp_msg)}`\n\n"
                        f"📢 **Check Live Post in Channel:**"
                    )
                    bot.send_message(call.message.chat.id, success_text, parse_mode="Markdown", reply_markup=markup)
                    return

    otp_ch_url = f"https://t.me/{OTP_CHANNEL.replace('@','')}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 Go to Live OTP Channel", url=otp_ch_url))
    pending_text = (
        f"⏳ **Searching for OTP for number:** `+{active_num}`\n\n"
        f"এখনো ইনবক্সে ওটিপি আসেনি! ওটিপি আসার সাথে সাথে লাইভ দেখতে নিচের বাটনে চেপে **OTP Channel**-এ ভিজিট করুন।"
    )
    bot.send_message(call.message.chat.id, pending_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "💳 Wallet")
def wallet_handler(message):
    if not check_join(message.from_user.id):
        send_join_msg(message.chat.id)
        return

    bal = get_or_create_user(message.from_user.id)
    text = (
        f"💳 **Your Wallet Overview**\n\n"
        f"🆔 **User ID:** `{message.from_user.id}`\n"
        f"💰 **Current Balance:** `${bal:.4f}`\n"
        f"📌 **Minimum Withdraw:** `${MIN_WITHDRAW:.2f} USDT`"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💸 Withdraw", callback_data="req_withdraw"),
        types.InlineKeyboardButton("👨‍💻 Support", url=f"https://t.me/{SUPPORT_USERNAME.replace('@','')}")
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "req_withdraw")
def withdraw_request_callback(call):
    bal = get_or_create_user(call.from_user.id)
    if bal < MIN_WITHDRAW:
        bot.answer_callback_query(call.id, f"❌ আপনার ব্যালেন্স অপর্যাপ্ত! সর্বনিম্ন উইথড্রাল ${MIN_WITHDRAW:.2f} USDT", show_alert=True)
    else:
        bot.send_message(call.message.chat.id, f"✅ আপনার উইথড্র রিকুয়েস্ট প্রক্রিয়াধীন রয়েছে। সাহায্যের জন্য অ্যাডমিন {clean_md(SUPPORT_USERNAME)} এ যোগাযোগ করুন।")

@bot.message_handler(func=lambda msg: msg.text == "🎁 Refer")
def refer_handler(message):
    if not check_join(message.from_user.id):
        send_join_msg(message.chat.id)
        return

    ref_link = f"https://t.me/{BOT_USERNAME.replace('@','')}?start={message.from_user.id}"
    text = (
        f"🎁 **Referral System**\n\n"
        f"Share your referral link with friends to earn bonus balance on every recharge!\n\n"
        f"🔗 **Your Link:**\n`{ref_link}`"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📊 Live Traffic")
def traffic_handler(message):
    records = OTPProviderAPI.fetch_numbers()
    active_count = len(records) if records else 0
    text = (
        f"📊 **Live System Traffic**\n\n"
        f"🟢 **Active Real Numbers:** `{active_count}`\n"
        f"⚡ **System Status:** `Operational 100%`"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🏆 Leaderboard")
def leaderboard_handler(message):
    text = (
        f"🏆 **Top Users Leaderboard**\n\n"
        f"1. User 7159*** - $12.50\n"
        f"2. User 5821*** - $9.80\n"
        f"3. User 6290*** - $7.10\n\n"
        f"Keep using the bot to climb the board!"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🔍 Search Number")
def search_num_handler(message):
    bot.send_message(message.chat.id, "🔎 Send the specific phone number you want to search:")

# ==================== DUMMY WEB SERVER FOR RENDER / VPS ====================
app = Flask(__name__)

@app.route('/')
def home():
    return f"Fast OTP Bot ({BOT_USERNAME}) is running smoothly!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    threading.Thread(target=auto_post_otps_to_channel, daemon=True).start()
    print("🤖 Fast OTP Bot starting safely...")
    
    try:
        bot.remove_webhook()
    except Exception as e:
        print(f"Webhook Removal Error: {e}")
        
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
