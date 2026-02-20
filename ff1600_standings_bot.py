import os
import json
import asyncio
import requests
import discord
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

# ==================================================
# CONFIG
# ==================================================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
IRACING_COOKIE = os.getenv("IRACING_COOKIE")

# Motorsport UK FF1600 Trophy
SERIES_ID = 5941
CAR_CLASS_ID = 4016  # FF1600 car class (from the URL)
DIVISION_1 = 1
DIVISION_2 = 2

IRACING_COOKIE = "hubspotutk=e2317f449d4fc4f2f2588cba6bd5f4c2; messagesUtk=037bfa25bd77420daebe2d813e4e32c0; theme=light; _ga=GA1.1.158087617.1759084326; _ga_Y1Q7PHRDJ4=GS2.1.s1766182172$o3$g0$t1766182172$j60$l0$h0; __hs_do_not_track=yes; __hstc=187670007.e2317f449d4fc4f2f2588cba6bd5f4c2.1763503646131.1763503646131.1771449457162.2; __hssrc=1; iracing_ui=7utXH4c6aS41IbxhHvPD6dtUoA1ESyNxf7dSlT6xfRCjfLHzmfkrHVlAl6LpIOZimXbXMFIhwGq%2FEl75ECovfw%3D%3D; _ga_VRYGYR9B0P=GS2.1.s1771449456$o2$g1$t1771451227$j60$l0$h0; _ga_DCQ7B2BWPN=GS2.1.s1771449458$o2$g1$t1771453383$j60$l0$h0; AWSALB=xc14/o74nYKB418EmriOT2Rh1RExusmzSbVzu4y5FviBJsiNzIqowsjm1IBABg2HR/RFM7NY4Dbxmk98pkMeuXOShFlT5pPEUPv9UHCiRTsezQquzK73l1PXSV6t; AWSALBCORS=xc14/o74nYKB418EmriOT2Rh1RExusmzSbVzu4y5FviBJsiNzIqowsjm1IBABg2HR/RFM7NY4Dbxmk98pkMeuXOShFlT5pPEUPv9UHCiRTsezQquzK73l1PXSV6t"

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
    "Edward Buchanan": ":flag_us:",
    "Daniel Case2": ":flag_us:",
    "Jay M Lawrence": ":flag_au:",
    "Brett McBurnie": ":flag_au:",
    "Graham Rory Hunt": "🇬🇧",
    "Mark Mifsud": ":flag_mt:",
    "JW Lane": ":flag_vn:",
    "James P Becker": ":flag_gg:",
    "Razvan Florin Veina": ":flag_ro:",
    "Frankiie Dee": ":flag_us:",
    "Andre O Sousa": ":flag_br:",
    "Jay Wray": ":flag_br:",
    "Nedo Braun": ":flag_de:",
    "Alex Herte": ":flag_it:",
    "Michele Borghesani": ":flag_fi:",
    "Stephen Strudwick": "🇬🇧",
    "Rein Tiesing": ":flag_nl:",
    "Daniel Repetto": ":flag_ea:",
    "Rob C Johnson": "🇬🇧",
    "Tim M. Connolly": ":flag_au:",
    "Scott Meadows": ":flag_us:",
    "Greg Boyce": ":flag_us:",
    "Ned Worton": "🇬🇧",
    "Wayne Funston": ":flag_au:",
    "Nathan Young3": ":flag_us:",
    "Jiyun Chen": ":flag_us:",
    "Dalibor Cvitan": ":flag_hr:",
    "Erwin Paul": ":flag_de:",
    "Erika Prior": ":flag_ea:",
    "Mark Kerr2": ":flag_au:",
    "Guy Robertson": "🇬🇧",
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

    # Always use division=-1 (same as UI)
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

    # Step 1: Proxy
    proxy_resp = requests.get(proxy_url, headers=headers)
    proxy_data = proxy_resp.json()
    s3_link = proxy_data.get("link")

    # Step 2: Manifest
    manifest = requests.get(s3_link).json()

    chunk_info = manifest.get("chunk_info", {})
    base_url = chunk_info.get("base_download_url")
    chunk_files = chunk_info.get("chunk_file_names", [])

    all_drivers = []

    # Step 3: Download all chunks
    for chunk_file in chunk_files:
        chunk_url = base_url + chunk_file
        chunk_data = requests.get(chunk_url).json()
        all_drivers.extend(chunk_data)

    # Step 4: Filter divisions like UI does
    div1 = []
    div2 = []

    for entry in all_drivers:

        division = entry.get("division")
        rank = entry.get("season_rank", 9999)

        driver_data = {
            "name": entry.get("display_name", ""),
            "points": entry.get("points", 0),
            "rank": rank,
            "weeks": entry.get("weeks_counted", 0),
            "week_points": 0
        }

        # ✅ Weekly points (safe extraction)
        results = entry.get("results", [])
        if results:
            latest = results[-1]
            driver_data["week_points"] = latest.get("points", 0)

        # ✅ Correct division mapping
        if division == 0:
            div1.append(driver_data)

        elif division == 1:
            div2.append(driver_data)

    # Step 5: Sort AFTER loop (IMPORTANT)
    div1.sort(key=lambda x: x["rank"])
    div2.sort(key=lambda x: x["rank"])

    return div1[:20], div2[:20]

# ==================================================
# DRAW LICENSE BADGE
# ==================================================

def draw_license_badge(draw, x, y, license_class, license_sr, font):

    text = f"{license_class}{license_sr:.2f}"

    padding_x = 16
    padding_y = 6

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    bg_width = text_width + padding_x * 2

    colour = LICENSE_COLOURS.get(license_class, (120, 120, 120))

    draw.rounded_rectangle(
        [x, y, x + bg_width, y + padding_y * 2],
        radius=12,
        fill=colour
    )

    draw.text(
        (x + padding_x, y + padding_y),
        text,
        fill="white",
        font=font
    )

    return bg_width


# ==================================================
# GENERATE IMAGE
# ==================================================

def generate_image(div1, div2):

    # Limit to top 20 per division
    div1 = div1[:20]
    div2 = div2[:20]

    width = 1400
    row_height = 50
    header_height = 120

    total_rows = len(div1) + len(div2) + 4
    height = header_height + total_rows * row_height + 40

    img = Image.new("RGB", (width, height), (25, 25, 30))
    draw = ImageDraw.Draw(img)

    font = ImageFont.load_default()

    # Title
    draw.text((50, 30), "Motorsport UK FF1600 Trophy Championship", fill="white", font=font)

    y = header_height

    # ---------------- Division 1 ----------------
    draw.text((50, y), "Division 1", fill="white", font=font)
    y += row_height

    leader_points = div1[0]["points"] if div1 else 0

    for pos, driver in enumerate(div1, start=1):

        draw.text((60, y), str(pos), fill="white", font=font)
        draw.text((120, y), driver["name"], fill="white", font=font)
        draw.text((900, y), f"{driver['points']} pts", fill="white", font=font)

        gap = leader_points - driver["points"]
        gap_text = "-" if pos == 1 else f"-{gap}"

        draw.text((1100, y), gap_text, fill="white", font=font)

        y += row_height

    y += row_height

    # ---------------- Division 2 ----------------
    draw.text((50, y), "Division 2", fill="white", font=font)
    y += row_height

    leader_points = div2[0]["points"] if div2 else 0

    for pos, driver in enumerate(div2, start=1):

        draw.text((60, y), str(pos), fill="white", font=font)
        draw.text((120, y), driver["name"], fill="white", font=font)
        draw.text((900, y), f"{driver['points']} pts", fill="white", font=font)

        gap = leader_points - driver["points"]
        gap_text = "-" if pos == 1 else f"-{gap}"

        draw.text((1100, y), gap_text, fill="white", font=font)

        y += row_height

    filename = "ff1600_standings.png"
    img.save(filename)

    return filename


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

        lines.append(
            f"{i:>2}. {name_display} — {d['points']} pts ({gap_text}) | W:{d['weeks']}"
        )

    return "\n".join(lines)


async def post_standings():

    print("Starting bot...")

    div1, div2 = fetch_standings()

    print(f"Division 1 drivers: {len(div1)}")
    print(f"Division 2 drivers: {len(div2)}")

    intents = discord.Intents.default()
    bot = discord.Client(intents=intents)

    @bot.event
    async def on_ready():

        print(f"Logged in as {bot.user}")
        now = datetime.now()
        timestamp = now.strftime("%d/%m/%y at %H:%M")

        channel = bot.get_channel(CHANNEL_ID)
        if channel is None:
            channel = await bot.fetch_channel(CHANNEL_ID)

        div1_text = (
            "**🏁 FF1600 Championship Standings 🏁**\n\n"
            + format_division("Division 1", div1)
            + f"\n\n_Last updated - {timestamp}_"
        )

        div2_text = (
            format_division("Division 2", div2)
            + f"\n\n_Last updated - {timestamp}_"
        )

        global MESSAGE_ID_DIV1, MESSAGE_ID_DIV2

        try:
            # -------- DIVISION 1 --------
            if MESSAGE_ID_DIV1:
                print("Editing Division 1 message...")
                msg1 = await channel.fetch_message(MESSAGE_ID_DIV1)
                await msg1.edit(content=div1_text)
            else:
                print("Sending Division 1 message...")
                msg1 = await channel.send(div1_text)
                MESSAGE_ID_DIV1 = msg1.id
                print(f"Saved DIV1 ID: {MESSAGE_ID_DIV1}")

            # -------- DIVISION 2 --------
            if MESSAGE_ID_DIV2:
                print("Editing Division 2 message...")
                msg2 = await channel.fetch_message(MESSAGE_ID_DIV2)
                await msg2.edit(content=div2_text)
            else:
                print("Sending Division 2 message...")
                msg2 = await channel.send(div2_text)
                MESSAGE_ID_DIV2 = msg2.id
                print(f"Saved DIV2 ID: {MESSAGE_ID_DIV2}")

        except Exception as e:
            print("Error updating messages:", e)

        await bot.close()

    await bot.start(DISCORD_TOKEN)


# Run
if __name__ == "__main__":
    asyncio.run(post_standings())
