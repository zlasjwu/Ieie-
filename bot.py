import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

API_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'  # Замените на токен от BotFather
CRYPTO_BOT_TOKEN = '378363:AAOJ1rgAF1MBdKlZQopR5R9iTVWvocxKctT'
REKVIZITY = '@nazark100'
ADMIN_ID = 123456789  # Замените на свой Telegram user_id

# Настройка
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# БД
conn = sqlite3.connect("store.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER,
    name TEXT,
    price REAL
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_id INTEGER,
    payment_method TEXT,
    proof TEXT,
    status TEXT
);
""")

conn.commit()

def seed_data():
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        categories = ['Standoff', 'Black Russia', 'Brawl Stars']
        for name in categories:
            cursor.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()

        cursor.execute("SELECT id FROM categories WHERE name = 'Standoff'")
        standoff_id = cursor.fetchone()[0]
        cursor.execute("INSERT INTO products (category_id, name, price) VALUES (?, ?, ?)", (standoff_id, '1000 Gold', 5.0))

        cursor.execute("SELECT id FROM categories WHERE name = 'Black Russia'")
        black_id = cursor.fetchone()[0]
        cursor.execute("INSERT INTO products (category_id, name, price) VALUES (?, ?, ?)", (black_id, 'Premium Account', 3.5))

        cursor.execute("SELECT id FROM categories WHERE name = 'Brawl Stars'")
        brawl_id = cursor.fetchone()[0]
        cursor.execute("INSERT INTO products (category_id, name, price) VALUES (?, ?, ?)", (brawl_id, 'Mega Box', 4.5))

        conn.commit()

seed_data()

class OrderState(StatesGroup):
    choosing_payment = State()
    waiting_proof = State()

@router.message(F.text == "/start")
async def start(message: types.Message):
    kb = InlineKeyboardBuilder()
    cursor.execute("SELECT * FROM categories")
    for row in cursor.fetchall():
        kb.button(text=row[1], callback_data=f"cat_{row[0]}")
    await message.answer("Добро пожаловать! Выберите категорию:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("cat_"))
async def show_products(callback: types.CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    cursor.execute("SELECT id, name, price FROM products WHERE category_id=?", (cat_id,))
    products = cursor.fetchall()
    kb = InlineKeyboardBuilder()
    for pid, name, price in products:
        kb.button(text=f"{name} - ${price}", callback_data=f"buy_{pid}")
    await callback.message.edit_text("Выберите товар:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("buy_"))
async def buy_product(callback: types.CallbackQuery, state: FSMContext):
    prod_id = int(callback.data.split("_")[1])
    await state.update_data(product_id=prod_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="Оплата вручную", callback_data="pay_manual")
    kb.button(text="Оплата криптой", url=f"https://t.me/CryptoBot?start={CRYPTO_BOT_TOKEN}")
    await callback.message.edit_text("Выберите способ оплаты:", reply_markup=kb.as_markup())
    await state.set_state(OrderState.waiting_proof)

@router.message(OrderState.waiting_proof)
async def get_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    prod_id = data['product_id']
    cursor.execute("INSERT INTO orders (user_id, product_id, payment_method, proof, status) VALUES (?, ?, ?, ?, ?)",
                   (message.from_user.id, prod_id, "manual", message.text, "pending"))
    conn.commit()
    await message.answer("Ваш чек отправлен администратору. Ожидайте подтверждение.")
    await state.clear()

@router.message(F.text == "/admin")
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Нет доступа.")
    cursor.execute("SELECT o.id, u.username, p.name, o.proof FROM orders o JOIN products p ON o.product_id = p.id LEFT JOIN users u ON o.user_id = u.id WHERE o.status = 'pending'")
    rows = cursor.fetchall()
    if not rows:
        return await message.answer("Нет новых заказов.")
    for oid, username, pname, proof in rows:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить", callback_data=f"approve_{oid}")]
        ])
        await message.answer(f"Заказ #{oid}
Пользователь: @{username}
Товар: {pname}
Чек: {proof}", reply_markup=kb)

@router.callback_query(F.data.startswith("approve_"))
async def approve(callback: types.CallbackQuery):
    oid = int(callback.data.split("_")[1])
    cursor.execute("UPDATE orders SET status = 'approved' WHERE id=?", (oid,))
    conn.commit()
    await callback.message.edit_text("Заказ подтвержден.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
