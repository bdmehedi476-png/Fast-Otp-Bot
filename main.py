import os
import threading
import time
import telebot
import requests
import sqlite3
from flask import Flask

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8923498683:AAHlHA8-GASExZDVnuR_lBORSaVvIhiqK5o"
ADMIN_ID = 7159155182

OTP_CHANNEL = "@FastOTPBot_1"
SUPPORT_CHANNEL = "@FastOtpSupportMathhodChannel"
SUPPORT_USERNAME = "@Owner_010"

# Lamix API Credentials
LAMIX_API_TOKEN = "q3zv3ACa1Sk5hJeKaBuvj8qDNrpJXssqZxRrgPdDT"

# Settings
MIN_WITHDRAW = 1.00

bot = telebot.TeleBot(BOT_TOKEN)

# Fallback names & flags for standard country codes
DEFAULT_COUNTRY_INFO = {
    "1": {"name": "USA/Canada", "flag": "🇺🇸"},
    "7": {"name": "Russia", "flag": "🇷🇺"},
    "20": {"name": "Egypt", "flag": "🇪🇬"},
    "27": {"name": "South Africa", "flag": "🇿🇦"},
    "31": {"name": "Netherlands", "flag": "🇳🇱"},
    "32": {"name": "Belgium", "flag": "🇧🇪"},
    "33": {"name": "France", "flag": "🇫🇷"},
    "34": {"name": "Spain", "flag": "🇪🇸"},
    "39": {"name": "Italy", "flag": "🇮🇹"},
    "40": {"name": "Romania", "flag": "🇷🇴"},
    "44": {"name": "UK", "flag": "🇬🇧"},
    "46": {"name": "Sweden", "flag": "🇸🇪"},
    "48": {"name": "Poland", "flag": "🇵🇱"},
    "49": {"name": "Germany", "flag": "🇩🇪"},
    "51": {"name": "Peru", "flag": "🇵🇪"},
    "52": {"name": "Mexico", "flag": "🇲🇽"},
    "54": {"name": "Argentina", "flag": "🇦🇷"},
    "55": {"name": "Brazil", "flag": "🇧🇷"},
    "57": {"name": "Colombia", "flag": "🇨🇴"},
    "60": {"name": "Malaysia", "flag": "🇲🇾"},
    "61": {"name": "Australia", "flag": "🇦🇺"},
    "62": {"name": "Indonesia", "flag": "🇮🇩"},
    "63": {"name": "Philippines", "flag": "🇵🇭"},
    "66": {"name": "Thailand", "flag": "🇹🇭"},
    "81": {"name": "Japan", "flag": "🇯🇵"},
    "84": {"name": "Vietnam", "flag": "🇻🇳"},
    "86": {"name": "China", "flag": "🇨🇳"},
    "90": {"name": "Turkey", "flag": "🇹🇷"},
    "91": {"name": "India", "flag": "🇮🇳"},
    "92": {"name": "Pakistan", "flag": "🇵🇰"},
    "93": {"name": "Afghanistan", "flag": "🇦🇫"},
    "94": {"name": "Sri Lanka", "flag": "🇱🇰"},
    "95": {"name": "Myanmar", "flag": "🇲🇲"},
    "98": {"name": "Iran", "flag": "🇮🇷"},
    "212": {"name": "Morocco", "flag": "🇲🇦"},
    "213": {"name": "Algeria", "flag": "🇩🇿"},
    "234": {"name": "Nigeria", "flag": "🇳🇬"},
    "254": {"name": "Kenya", "flag": "🇰🇪"},
    "351": {"name": "Portugal", "flag": "🇵🇹"},
    "380": {"name": "Ukraine", "flag": "🇺🇦"},
    "852": {"name": "Hong Kong", "flag": "🇭🇰"},
    "880": {"name": "Bangladesh", "flag": "🇧🇩"},
    "966": {"name": "Saudi Arabia", "flag": "🇸🇦"},
    "971": {"name": "UAE", "flag": "🇦🇪"},
    "972": {"name": "Israel", "flag": "🇮🇱"}
}

# ==================== DATABASE SETUP ====================
def init_db():
    conn = sqlite3.connect("fast_otp_bot.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        balance REAL DEFAULT 0.0,
                        referred_by INTEGER DEFAULT 0
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_states (
                        user_id INTEGER PRIMARY KEY,
                        selected_prefix TEXT
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS used_numbers (
                        user_id INTEGER,
                        number TEXT,
                        PRIMARY KEY (user_id, number)
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS active_sessions (
                        user_id INTEGER PRIMARY KEY,
                        number TEXT,
                        country_code TEXT
                    )''')
    conn.commit()
    conn.close()

init_db()

def get_user(user_id, referred_by=0):
    conn = sqlite3.connect("fast_otp_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, balance, referred_by FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id, balance, referred_by) VALUES (?, ?, ?)", 
                       (user_id, 0.0, referred_by))
        conn.commit()
        user = (user_id, 0.0, referred_by)
    conn.close()
    return user

# ==================== API HELPERS ====================
def fetch_lamix_numbers():
    try:
        headers = {"Authorization": f"Bearer {LAMIX_API_TOKEN}"}
        response = requests.get("https://panel.lamix.org/api/v1/numbers", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("data", data.get("numbers", []))
        return []
    except Exception as e:
        print(f"API Error: {e}")
        return []

def fetch_lamix_cdrs():
    try:
        headers = {"Authorization": f"Bearer {LAMIX_API_TOKEN}"}
        response = requests.get("https://panel.lamix.org/api/v1/cdrs", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("data", data.get("cdrs", []))
        return []
    except Exception as e:
        print(f"CDR Error: {e}")
        return []

# ==================== TELEGRAM INTERFACE ====================
@bot.message_handler(commands=['start'])
def start_command(message):
    args = message.text.split()
    referred_by = 0
    if len(args) > 1:
        try:
            ref_id = int(args[1])
            if ref_id != message.from_user.id:
                referred_by = ref_id
        except ValueError:
            pass

    user = get_user(message.from_user.id, referred_by)
    name = message.from_user.first_name

    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("📞 Get Number", callback_data="get_number"),
        telebot.types.InlineKeyboardButton("💼 Balance & Ref", callback_data="balance_menu")
    )
    markup.add(
        telebot.types.InlineKeyboardButton("📢 Support Channel", url=f"https://t.me/{SUPPORT_CHANNEL.lstrip('@')}"),
        telebot.types.InlineKeyboardButton("💬 Contact Admin", url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}")
    )

    text = (
        f"🔥 Welcome to Fast OTP Bot!\n\n"
        f"👋 Hello {name}!\n"
        f"💰 Your Balance: {user[1]:.4f}\n\n"
        f"📢 OTP Channel: {OTP_CHANNEL}\n"
        f"🛠 Support Channel: {SUPPORT_CHANNEL}\n\n"
        f"👇 Select an option from below to get started:"
    )
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    if call.data == "get_number":
        numbers = fetch_lamix_numbers()
        if not numbers:
            bot.answer_callback_query(call.id, "No numbers available right now. Try again later.", show_alert=True)
            return

        country_counts = {}
        for item in numbers:
            prefix = str(item.get("prefix", item.get("country_code", "Unknown")))
            price = item.get("price", 0.005)
            if prefix not in country_counts:
                country_counts[prefix] = {"count": 0, "price": price}
            country_counts[prefix]["count"] += 1

        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        for prefix, info in country_counts.items():
            c_info = DEFAULT_COUNTRY_INFO.get(prefix, {"name": f"Country +{prefix}", "flag": "🌍"})
            btn_text = f"{c_info['flag']} {c_info['name']} (+{prefix}) - {info['count']} Available | ${info['price']:.4f}/OTP"
            markup.add(telebot.types.InlineKeyboardButton(btn_text, callback_data=f"sel_country_{prefix}"))

        markup.add(telebot.types.InlineKeyboardButton("« Back to Menu", callback_data="main_menu"))
        bot.edit_message_text("🌍 Select a Country (Auto-updated from Panel):", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("sel_country_"):
        prefix = call.data.split("_")[2]
        numbers = fetch_lamix_numbers()

        available_nums = [n for n in numbers if str(n.get("prefix", n.get("country_code", ""))) == prefix]
        if not available_nums:
            bot.answer_callback_query(call.id, "No numbers available for this country right now.", show_alert=True)
            return

        selected_item = available_nums[0]
        phone_number = selected_item.get("number", selected_item.get("phone", ""))

        conn = sqlite3.connect("fast_otp_bot.db")
        cursor = conn.cursor()
        cursor.execute("REPLACE INTO active_sessions (user_id, number, country_code) VALUES (?, ?, ?)", (user_id, phone_number, prefix))
        conn.commit()
        conn.close()

        c_info = DEFAULT_COUNTRY_INFO.get(prefix, {"name": f"Country +{prefix}", "flag": "🌍"})
        text = (
            f"✅ Number Generated Successfully!\n\n"
            f"🌍 Country: {c_info['flag']} {c_info['name']}\n"
            f"📱 Number: {phone_number}\n\n"
            f"⏳ Waiting for OTP... (Auto-refreshing)"
        )
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("❌ Cancel / New Number", callback_data="get_number"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "balance_menu":
        user = get_user(user_id)
        ref_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        text = (
            f"💼 Account & Referral Info\n\n"
            f"💰 Balance: {user[1]:.4f}\n"
            f"🔗 Referral Link:\n{ref_link}\n\n"
            f"Share this link with your friends to earn rewards!"
        )
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("« Back", callback_data="main_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "main_menu":
        user = get_user(user_id)
        name = call.from_user.first_name
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            telebot.types.InlineKeyboardButton("📞 Get Number", callback_data="get_number"),
            telebot.types.InlineKeyboardButton("💼 Balance & Ref", callback_data="balance_menu")
        )
        markup.add(
            telebot.types.InlineKeyboardButton("📢 Support Channel", url=f"https://t.me/{SUPPORT_CHANNEL.lstrip('@')}"),
            telebot.types.InlineKeyboardButton("💬 Contact Admin", url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}")
        )
        text = (
            f"🔥 Welcome to Fast OTP Bot!\n\n"
            f"👋 Hello {name}!\n"
            f"💰 Your Balance: {user[1]:.4f}\n\n"
            f"👇 Select an option from below to get started:"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# ==================== BACKGROUND CDR / OTP CHECKER ====================
def background_otp_checker():
    seen_cdrs = set()
    while True:
        try:
            cdrs = fetch_lamix_cdrs()
            for cdr in cdrs:
                cdr_id = cdr.get("id", cdr.get("sms_id", str(cdr)))
                if cdr_id in seen_cdrs:
                    continue
                seen_cdrs.add(cdr_id)

                number = cdr.get("number", cdr.get("phone", ""))
                otp_code = cdr.get("otp", cdr.get("code", cdr.get("text", "")))
                service = cdr.get("service", cdr.get("app", "Unknown"))

                if number and otp_code:
                    msg = (
                        f"🔔 New OTP Received!\n\n"
                        f"📱 Number: {number}\n"
                        f"🏷 Service: {service}\n"
                        f"🔑 OTP Code: {otp_code}"
                    )
                    try:
                        bot.send_message(OTP_CHANNEL, msg)
                    except Exception as e:
                        print(f"Error posting to channel: {e}")
        except Exception as e:
            print(f"Background worker error: {e}")
        time.sleep(5)

# Start background thread for OTP checking
threading.Thread(target=background_otp_checker, daemon=True).start()

# ==================== DUMMY WEB SERVER FOR RENDER FREE PORT ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    print("Bot is running with Web Port Binding...")
    try:
        bot.remove_webhook()
    except Exception as e:
        print(f"Webhook remove error: {e}")
        
    bot.infinity_polling()
