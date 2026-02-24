print("SCRIPT STARTED")

from datetime import datetime, timedelta, timezone
import os
import json
import asyncio
import requests
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ==================================================
# CONFIG
# ==================================================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
IRACING_COOKIE = os.getenv("IRACING_COOKIE")
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

# Motorsport UK FF1600 Trophy
SERIES_ID = 5941
CAR_CLASS_ID = 4016  # FF1600 car class (from the URL)
DIVISION_1 = 1
DIVISION_2 = 2

CACHE_FILE = "driver_cache.json"
MESSAGE_ID_FILE = "message_id.txt"
MESSAGE_ID_DIV1 = 1474495668075757843
MESSAGE_ID_DIV2 = 1474495669107560458  # Will be filled after first run

HIGHLIGHT_NAMES = ["David Garrott","Philip Lindqvist"]

FLAG_CACHE = {
    "David Garrott": "🇬🇧",
    "Philip Lindqvist": "🇸🇪",
    "Jarno Markku": ":flag_fi:",
    "Ossi Turkia": ":flag_fi:",
    "Mikey Pollard": "🇬🇧",
    "Fredrik Sørlie": ":flag_no:",
    "Jake R Williams": ":wales:",
    "Aleksander Istad": ":flag_no:",
    "Edward Buchanan": ":flag_ca:",
    "Daniel Case2": ":flag_us:",
    "Jay M Lawrence": ":flag_au:",
    "Brett McBurnie": ":flag_au:",
    "Graham Rory Hunt": "🇬🇧",
    "Mark Mifsud": ":flag_mt:",
    "JW Lane": ":flag_vn:",
    "James P Becker": ":flag_gg:",
    "Razvan Florin Veina": ":flag_ro:",
    "Frankie Dee": ":flag_us:",
    "Andre O Sousa": ":flag_br:",
    "Jay Wray": ":flag_us:",
    "Nedo Braun": ":flag_de:",
    "Alex Herte": ":flag_ea:",
    "Michele Borghesani": ":flag_it:",
    "Stephen Strudwick": "🇬🇧",
    "Rein Tiesing": ":flag_nl:",
    "Daniel Repetto": ":flag_ea:",
    "Alex Moreno3": ":flag_ea:",
    "Rob C Johnson": ":england:",
    "Tim M. Connolly": ":flag_au:",
    "Scott Meadows": ":flag_us:",
    "Ryan Turcotte": ":flag_us:",
    "Greg Boyce": ":flag_us:",
    "Ned Worton": "🇬🇧",
    "Nick Aronson": "🇬🇧",
    "Matt Kendall": "🇬🇧",
    "Wayne Funston": ":flag_au:",
    "Nathan Young3": ":flag_us:",
    "Jiyun Chen": ":flag_us:",
    "Dalibor Cvitan": ":flag_hr:",
    "Erwin Paul": ":flag_de:",
    "Erika Prior": ":flag_ea:",
    "Mark Kerr2": ":flag_au:",
    "Guy Robertson": "🇬🇧",
    "Dan Willmott": "🇬🇧",
    "Todd P Martin": ":flag_ca:",
    "Ed Parise": ":flag_br:",
    "Sergey Khvostov": ":globe_with_meridians:",
    "MT Jones": ":globe_with_meridians:",
}

LICENSE_COLOURS = {
    "D": (255, 140, 0),
    "C": (255, 215, 0),
    "B": (34, 139, 34),
    "A": (30, 144, 255)
}

def get_license_emoji(lic):

    if lic == "A":
        return "🔵"
    elif lic == "B":
        return "🟢"
    elif lic == "C":
        return "🟡"
    elif lic == "D":
        return "🟠"
    else:
        return "⚪"


# ==================================================
# FETCH STANDINGS FROM iRACING API
# ==================================================

def fetch_division(division_number):

    proxy_url = (
        "https://members-ng.iracing.com/bff/pub/proxy/data/stats/season_driver_standings"
        f"?season_id={SERIES_ID}"
        f"&car_class_id={CAR_CLASS_ID}"
        "&race_week_num=-1"
        f"&division={division_number}"
    )

    headers = {
        "Cookie": IRACING_COOKIE,
        "User-Agent": "Mozilla/5.0"
    }

    # Step 1: Get proxy link
    response = requests.get(proxy_url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Proxy fetch failed: {response.status_code}")

    proxy_data = response.json()
    s3_link = proxy_data.get("link")

    # Step 2: Get manifest
    s3_link = proxy_data.get("link")

    if not s3_link:
        print("iRacing API did not return link. Possibly expired cookie.")
        return [], []  # Prevent crash

    manifest = requests.get(s3_link).json()

    chunk_info = manifest.get("chunk_info", {})
    base_url = chunk_info.get("base_download_url")
    chunk_files = chunk_info.get("chunk_file_names", [])

    drivers = []

    # Step 3: Download chunks
    for chunk_file in chunk_files:
        chunk_url = base_url + chunk_file
        chunk_data = requests.get(chunk_url).json()
        drivers.extend(chunk_data)

    return drivers


def fetch_standings():

    proxy_url = (
        "https://members-ng.iracing.com/bff/pub/proxy/data/stats/season_driver_standings"
        f"?season_id={SERIES_ID}"
        f"&car_class_id={CAR_CLASS_ID}"
        "&race_week_num=-1"
        "&division=-1"
    )

    headers = {
        "Cookie": IRACING_COOKIE,
        "User-Agent": "Mozilla/5.0"
    }

    print("FETCHING STANDINGS...")

    proxy_resp = requests.get(proxy_url, headers=headers)
    proxy_data = proxy_resp.json()
    s3_link = proxy_data.get("link")

    if not s3_link:
        raise Exception("iRacing did not return S3 link")

    manifest = requests.get(s3_link).json()

    chunk_info = manifest.get("chunk_info", {})
    base_url = chunk_info.get("base_download_url")
    chunk_files = chunk_info.get("chunk_file_names", [])

    all_drivers = []

    for chunk_file in chunk_files:
        chunk_url = base_url + chunk_file
        chunk_data = requests.get(chunk_url).json()
        all_drivers.extend(chunk_data)

    print("Fetching weekly data cache...")
    weekly_cache = {}

    for week in range(0, 12):
        weekly_cache[week] = fetch_week_points(week)

    div1 = []
    div2 = []

    for entry in all_drivers:

        division = entry.get("division")
        rank = entry.get("season_rank", 9999)

        driver_data = {
            "name": entry.get("display_name", ""),
            "points": entry.get("points", 0),
            "rank": rank,
            "weeks": entry.get("weeks_counted", 0)
        }

        weekly_scores = []

        for week in range(0, 12):
            week_data = weekly_cache.get(week, [])

            for entry_week in week_data:
                if entry_week.get("display_name") == driver_data["name"]:
                    weekly_scores.append(entry_week.get("points", 0))
                    break
            else:
                weekly_scores.append(0)

        driver_data["top_8_scores"] = sorted(weekly_scores, reverse=True)[:8]

        if division == 0:
            div1.append(driver_data)
        elif division == 1:
            div2.append(driver_data)

    div1.sort(key=lambda x: x["rank"])
    div2.sort(key=lambda x: x["rank"])

    print("STANDINGS FETCHED")

    return div1[:20], div2[:20]
    

def fetch_week_points(week_num):

    proxy_url = (
        "https://members-ng.iracing.com/bff/pub/proxy/data/stats/season_driver_standings"
        f"?season_id={SERIES_ID}"
        f"&car_class_id={CAR_CLASS_ID}"
        f"&race_week_num={week_num}"
        "&division=-1"
    )

    headers = {
        "Cookie": IRACING_COOKIE,
        "User-Agent": "Mozilla/5.0"
    }

    proxy_resp = requests.get(proxy_url, headers=headers)
    proxy_data = proxy_resp.json()

    s3_link = proxy_data.get("link")

    if not s3_link:
        return []

    manifest = requests.get(s3_link).json()

    chunk_info = manifest.get("chunk_info", {})
    base_url = chunk_info.get("base_download_url")
    chunk_files = chunk_info.get("chunk_file_names", [])

    week_drivers = []

    for chunk_file in chunk_files:
        chunk_url = base_url + chunk_file
        chunk_data = requests.get(chunk_url).json()
        week_drivers.extend(chunk_data)

    return week_drivers


# ==================================================
# DISCORD POSTING
# ==================================================

import discord
import asyncio

def format_division(title, drivers):

    lines = [f"**{title}**"]

    if not drivers:
        return f"**{title}**\nNo data."

    leader_points = drivers[0]["points"]

    for i, d in enumerate(drivers[:20], start=1):

        gap = leader_points - d["points"]
        gap_text = "-" if i == 1 else f"-{gap}"

        name = d["name"]
        flag = FLAG_CACHE.get(name, "")

        # 👽 Highlight logic
        if name in HIGHLIGHT_NAMES:
            name_display = f"👽 **{name}**"
        else:
            name_display = name

        # Add flag AFTER name
        if flag:
            name_display = f"{name_display} {flag}"

        # First line (no bold to avoid spacing issue)
        lines.append(f"{i:>2}. {name_display} — {d['points']} pts ({gap_text})")

        # Top 8 formatting
        top_scores = d.get("top_8_scores", [])
        top_scores_str = ", ".join(str(x) for x in top_scores)

        # Second line (directly underneath)
        lines.append(f"Weeks counted: {d['weeks']} | Top 8: {top_scores_str}")

        # Blank line between drivers
        lines.append("")

    return "\n".join(lines)


async def post_standings():

    print("POST_STANDINGS STARTED")

    # -------- FETCH --------
    try:
        div1, div2 = fetch_standings()
        print("DIV1 LENGTH:", len(div1))
        print("DIV2 LENGTH:", len(div2))
    except Exception as e:
        print(f"Error fetching standings: {e}")
        return

    # -------- FORMAT --------
    try:
        division1_text = format_division("Division 1", div1)
        division2_text = format_division("Division 2", div2)
        print("FORMAT COMPLETE")
    except Exception as e:
        print(f"Error formatting standings: {e}")
        return

    # -------- DISCORD UPDATE --------
    try:
        channel = bot.get_channel(CHANNEL_ID)

        if channel is None:
            print("ERROR: Channel not found.")
            return

        # ----- Division 1 -----
        async for message in channel.history(limit=50):
            if message.author == bot.user and "Division 1" in message.content:
                print("Editing Division 1 message...")
                await message.edit(content=division1_text)
                break
        else:
            print("Sending new Division 1 message...")
            await channel.send(division1_text)

        # ----- Division 2 -----
        async for message in channel.history(limit=50):
            if message.author == bot.user and "Division 2" in message.content:
                print("Editing Division 2 message...")
                await message.edit(content=division2_text)
                break
        else:
            print("Sending new Division 2 message...")
            await channel.send(division2_text)

        print("DISCORD UPDATE COMPLETE")

    except Exception as e:
        print(f"Error updating Discord: {e}")


# Run
import asyncio
from datetime import datetime, timedelta, UTC

async def scheduler():

    print("Container started — running initial update...")
    try:
        await post_standings()
    except Exception as e:
        print(f"Initial update failed: {e}")

    while True:
        now = datetime.now(timezone.utc)

        next_run = now.replace(minute=40, second=0, microsecond=0)

        if now.minute >= 40:
            next_run += timedelta(hours=1)

        wait_seconds = (next_run - now).total_seconds()

        print(f"Next run at {next_run}")
        print(f"Sleeping for {int(wait_seconds)} seconds")

        sleep_interval = 60  # check every minute

        while wait_seconds > 0:
            await asyncio.sleep(min(sleep_interval, wait_seconds))
              wait_seconds -= sleep_interval

        print("Heartbeat...")
        
        try:
            print("Updating standings...")
            await post_standings()
        except Exception as e:
            print(f"Scheduled update failed: {e}")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await post_standings()   # 👈 FORCE immediate run
    bot.loop.create_task(scheduler())


bot.run(DISCORD_TOKEN)



























