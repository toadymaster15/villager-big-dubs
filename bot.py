import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
import json
import os
from config import TOKEN, CHECK_INTERVAL, DATA_FILE

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Load saved data
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        tracked_items = json.load(f)
else:
    tracked_items = {}  # {user_id: [{"url": "...", "last_price": 12.99}]}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(tracked_items, f, indent=2)

# --- Price Fetching ---
def get_price(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        # Example for Amazon (adjust for other sites)
        price_whole = soup.find("span", {"class": "a-price-whole"})
        price_fraction = soup.find("span", {"class": "a-price-fraction"})

        if price_whole and price_fraction:
            price_str = price_whole.text.replace(",", "").replace(".", "").strip() + "." + price_fraction.text.strip()
            return float(price_str)
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return None

# --- Commands ---
@bot.command()
async def track(ctx, action: str, url: str = None):
    user_id = str(ctx.author.id)

    if action == "add" and url:
        if user_id not in tracked_items:
            tracked_items[user_id] = []
        tracked_items[user_id].append({"url": url, "last_price": None})
        save_data()
        await ctx.send(f"✅ Added tracking for {url}")

    elif action == "list":
        if user_id not in tracked_items or not tracked_items[user_id]:
            await ctx.send("You are not tracking any items.")
        else:
            msg = "\n".join([item["url"] for item in tracked_items[user_id]])
            await ctx.send(f"📋 You are tracking:\n{msg}")

    elif action == "remove" and url:
        if user_id in tracked_items:
            before = len(tracked_items[user_id])
            tracked_items[user_id] = [item for item in tracked_items[user_id] if item["url"] != url]
            after = len(tracked_items[user_id])
            save_data()
            if before > after:
                await ctx.send(f"❌ Removed {url}")
            else:
                await ctx.send("URL not found in your tracked items.")
        else:
            await ctx.send("You are not tracking anything.")

    else:
        await ctx.send("Usage: !track add <url> | !track list | !track remove <url>")

# --- Background Task ---
@tasks.loop(minutes=CHECK_INTERVAL)
async def check_prices():
    for user_id, items in tracked_items.items():
        try:
            user = await bot.fetch_user(int(user_id))
            for item in items:
                url = item["url"]
                price = get_price(url)
                if price is None:
                    continue
                if item["last_price"] is None:
                    item["last_price"] = price
                    save_data()
                    continue
                if price < item["last_price"]:
                    item["last_price"] = price
                    save_data()
                    await user.send(f"📉 Price drop detected!\n{url}\nNow: ${price:.2f}")
        except Exception as e:
            print(f"Error checking prices for user {user_id}: {e}")

@bot.event
async def on_ready():
    print(f"✅ Bot logged in as {bot.user}")
    if not check_prices.is_running():
        check_prices.start()

if TOKEN is None:
    print("❌ ERROR: DISCORD_BOT_TOKEN not found in environment variables!")
    print("Please set your bot token in the environment or .env file")
else:
    bot.run(TOKEN)
