import base64
import html
import logging
import re
import urllib.parse
from bs4 import BeautifulSoup
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(level=logging.INFO)

# आपका Telegram Bot Token
BOT_TOKEN = "8871209884:AAEXvGyDDsIiQ1hg4ny1N4VQrPnDPSY2tDM"

# एक्टिव बेस डोमेन
BASE_URL = "https://vegamovies.im"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
        " (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    )
}

CACHE = {}


def fetch_soup(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200:
            return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        logging.error(f"Error fetching {url}: {e}")
    return None


def extract_movie_cards(soup):
    results = []
    if not soup:
        return results

    articles = soup.find_all("article")
    for art in articles[:8]:
        title_el = art.find(["h2", "h3"])
        link_el = art.find("a")
        if title_el and link_el:
            title = title_el.get_text(strip=True)
            link = link_el.get("href")
            short_title = title[:50] + ("..." if len(title) > 50 else "")
            results.append((short_title, link))
    return results


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ होमपेज से लेटेस्ट मूवीज लोड हो रही हैं...")
    soup = fetch_soup(BASE_URL)
    cards = extract_movie_cards(soup)

    if not cards:
        await update.message.reply_text(
            "⚠️ मूवीज लोड नहीं हो सकीं। कृपया मूवी का नाम लिखकर सर्च करें।"
        )
        return

    keyboard = []
    for title, link in cards:
        cache_id = str(abs(hash(link)))[:10]
        CACHE[cache_id] = link
        keyboard.append(
            [InlineKeyboardButton(f"🎬 {title}", callback_data=f"sel_{cache_id}")]
        )

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🔥 **VegaMovies लेटेस्ट अपडेट्स**\n\nनीचे से मूवी चुनें या नाम लिखकर सर्च करें:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    search_url = f"{BASE_URL}/?s={urllib.parse.quote(query)}"
    await update.message.reply_text(f"🔍 '{query}' सर्च किया जा रहा है...")

    soup = fetch_soup(search_url)
    cards = extract_movie_cards(soup)

    if not cards:
        await update.message.reply_text(
            "❌ कोई मूवी नहीं मिली! सही स्पेलिंग लिखकर दोबारा भेजें।"
        )
        return

    keyboard = []
    for title, link in cards:
        cache_id = str(abs(hash(link)))[:10]
        CACHE[cache_id] = link
        keyboard.append(
            [InlineKeyboardButton(f"🎬 {title}", callback_data=f"sel_{cache_id}")]
        )

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎯 **सर्च परिणाम:**", reply_markup=reply_markup, parse_mode="Markdown"
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("sel_"):
        cache_id = data.replace("sel_", "")
        movie_url = CACHE.get(cache_id)

        if not movie_url:
            await query.edit_message_text("सत्र समाप्त हो गया, दोबारा सर्च करें।")
            return

        await query.edit_message_text(
            "⚙️ मूवी की क्वालिटी, भाषा और लिंक्स निकाले जा रहे हैं..."
        )
        soup = fetch_soup(movie_url)
        if not soup:
            await query.edit_message_text("डिटेल्स लोड नहीं हो सकीं।")
            return

        content_text = soup.get_text()
        audio_info = "उपलब्ध नहीं"
        sub_info = "उपलब्ध नहीं"

        audio_match = re.search(
            r"(?:Audio|Language|भाषा)\s*:\s*([^\n\r]+)", content_text, re.IGNORECASE
        )
        if audio_match:
            audio_info = audio_match.group(1).strip()[:80]

        sub_match = re.search(
            r"(?:Subtitles?|Subs)\s*:\s*([^\n\r]+)", content_text, re.IGNORECASE
        )
        if sub_match:
            sub_info = sub_match.group(1).strip()[:80]

        download_buttons = []
        links = soup.find_all("a", href=True)

        for a in links:
            href = a["href"]
            txt = a.get_text().strip()
            full_txt = f"{txt} {href}"

            match = re.search(r"(480p|720p|1080p|2160p|4k)", full_txt, re.IGNORECASE)
            if match and ("download" in full_txt.lower() or "v-cloud" in href or "fast" in href.lower() or "drive" in href.lower()):
                quality = match.group(1).upper()
                vlc_scheme = f"vlc-x-callback://x-callback-url/stream?url={urllib.parse.quote(href)}"
                download_buttons.append([
                    InlineKeyboardButton(
                        f"▶️ Watch {quality} in VLC", url=vlc_scheme
                    ),
                    InlineKeyboardButton(f"⬇️ Download {quality}", url=href),
                ])

        if not download_buttons:
            for a in links:
                if "download" in a.get_text().lower() and len(download_buttons) < 3:
                    h = a["href"]
                    v_url = f"vlc-x-callback://x-callback-url/stream?url={urllib.parse.quote(h)}"
                    download_buttons.append([
                        InlineKeyboardButton("▶️ Watch in VLC", url=v_url),
                        InlineKeyboardButton("⬇️ Download", url=h),
                    ])

        caption = (
            f"🎬 **मूवी डिटेल्स**\n\n"
            f"🔊 **ऑडियो/भाषा:** `{audio_info}`\n"
            f"📝 **सबटाइटल:** `{sub_info}`\n\n"
            f"👇 नीचे से अपनी क्वालिटी चुनें:"
        )

        reply_markup = InlineKeyboardMarkup(download_buttons)
        await query.edit_message_text(
            caption, reply_markup=reply_markup, parse_mode="Markdown"
        )


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), handle_search)
    )
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()


if __name__ == "__main__":
    main()
