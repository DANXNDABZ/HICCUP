import discord
from discord.ext import commands
from flask import Flask, jsonify
import aiosqlite
import threading
import random
import time
import asyncio
import os

# Flask setup for the dashboard
app = Flask(__name__)

# SQLite database file
DATABASE_FILE = "economy.db"

# Configure intents
intents = discord.Intents.default()  # Start with default intents
intents.members = True               # Enable member-related events
intents.messages = True              # Enable message-related events
intents.message_content = True       # Enable message content access (required for non-slash commands)

# Discord bot setup
bot = commands.Bot(command_prefix="!", intents=intents)

# Shop items pool for weekly rotation
SHOP_ITEMS_POOL = [
    {"name": "Health Potion", "price": 100},
    {"name": "Mana Potion", "price": 120},
    {"name": "Loot Crate", "price": 500},
    {"name": "XP Booster", "price": 800},
    {"name": "Golden Sword", "price": 1500},
    {"name": "Dragon Armor", "price": 2000},
    {"name": "Mysterious Scroll", "price": 400},
    {"name": "Resurrection Stone", "price": 1000}
]

# Helper function to initialize the database
async def initialize_database():
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS economy (
                user_id TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shop (
                item_name TEXT PRIMARY KEY,
                price INTEGER NOT NULL,
                added_on TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                user_id TEXT,
                achievement_name TEXT,
                PRIMARY KEY (user_id, achievement_name)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bounty (
                user_id TEXT PRIMARY KEY,
                total_bounty INTEGER DEFAULT 0
            )
        """)
        await db.commit()

# Rotate shop items weekly
async def rotate_shop():
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("DELETE FROM shop")
        selected_items = random.sample(SHOP_ITEMS_POOL, 3)
        for item in selected_items:
            await db.execute(
                "INSERT INTO shop (item_name, price, added_on) VALUES (?, ?, ?)",
                (item["name"], item["price"], time.strftime("%Y-%m-%d"))
            )
        await db.commit()
        print("Shop items rotated!")

# Schedule shop rotation
async def schedule_shop_rotation():
    while True:
        await rotate_shop()
        await asyncio.sleep(604800)  # 604,800 seconds = 1 week

# Helper functions for database interaction
async def get_balance(user_id):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("SELECT balance FROM economy WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
    return result[0] if result else 0

async def update_balance(user_id, new_balance):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("""
            INSERT INTO economy (user_id, balance)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET balance = ?
        """, (user_id, new_balance, new_balance))
        await db.commit()

async def get_shop_items():
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("SELECT item_name, price FROM shop") as cursor:
            return await cursor.fetchall()

# Discord bot commands
@bot.command(name="shop")
async def shop(ctx):
    items = await get_shop_items()

    if not items:
        await ctx.send("The shop is currently empty.")
        return

    embed = discord.Embed(
        title="🛒 Weekly Shop",
        description="Here are the items available this week:",
        color=discord.Color.green()
    )
    for item_name, price in items:
        embed.add_field(name=item_name, value=f"Price: {price} Hoolicoins", inline=False)

    await ctx.send(embed=embed)

@bot.command(name="buy")
async def buy(ctx, *, item_name: str):
    user_id = str(ctx.author.id)
    item_name = item_name.lower()
    balance = await get_balance(user_id)

    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("SELECT price FROM shop WHERE LOWER(item_name) = ?", (item_name,)) as cursor:
            result = await cursor.fetchone()

    if not result:
        await ctx.send(f"The item `{item_name}` is not available in the shop.")
        return

    price = result[0]
    if balance < price:
        await ctx.send("You do not have enough Hoolicoins to buy this item.")
        return

    await update_balance(user_id, balance - price)
    await ctx.send(f"You have purchased `{item_name}` for {price} Hoolicoins!")

@bot.command(name="leaderboard")
async def leaderboard(ctx, limit: int = 10):
    if limit < 1 or limit > 50:
        await ctx.send("Please specify a limit between 1 and 50.")
        return

    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("SELECT user_id, balance FROM economy ORDER BY balance DESC LIMIT ?", (limit,)) as cursor:
            leaderboard = await cursor.fetchall()

    if not leaderboard:
        await ctx.send("No users found in the leaderboard.")
        return

    embed = discord.Embed(
        title="🏆 Economy Leaderboard",
        description=f"Top {limit} richest users:",
        color=discord.Color.gold()
    )
    for rank, (user_id, balance) in enumerate(leaderboard, start=1):
        user = await bot.fetch_user(user_id)
        embed.add_field(name=f"{rank}. {user.display_name}", value=f"{balance} Hoolicoins", inline=False)

    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await initialize_database()
    print("Database initialized.")
    bot.loop.create_task(schedule_shop_rotation())

# Flask routes for the dashboard
@app.route('/')
def home():
    return "<h1>Welcome to the Bot Dashboard</h1>"

@app.route('/shop')
async def shop_items():
    items = await get_shop_items()
    return jsonify({"shop": [{"item_name": item[0], "price": item[1]} for item in items]})

# Run Flask in a separate thread
def run_dashboard():
    app.run(debug=True, use_reloader=False, port=int(os.getenv("PORT", 5000)))

dashboard_thread = threading.Thread(target=run_dashboard)
dashboard_thread.start()

# Run the Discord bot
bot.run(os.getenv("YOUR_BOT_TOKEN"))