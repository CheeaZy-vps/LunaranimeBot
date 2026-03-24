#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Coded by aqil.almara - t.me/prudentscitus

# Imports
import os
import re
import sys
import html
import json
import time
import logging
import requests
from pathlib import Path
from typing import Optional, Union, Dict, Any, List
from urllib.parse import quote
from requests.exceptions import HTTPError, ConnectionError, ReadTimeout
try: from json.decoder import JSONDecodeError
except ImportError: JSONDecodeError = ValueError

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import KeyboardButton, ReplyKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    CallbackQueryHandler,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    JobQueue
)
from telegram.error import TelegramError

import ApiLunaranime

# Bot Token (use environment variable for security)
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_FILE = Path('.LunaranimeBot.db.json')
ADMIN_USER_ID = [1308147558]
DELETE_DELAY = 30  # detik
BOT_DATABASE = {}
if DB_FILE.exists():
    BOT_DATABASE = json.loads(DB_FILE.read_bytes().decode('utf-8'))

MESSAGES = {
    # Welcome & Main Menu
    "welcome": """👋 <b>Welcome {user_mention}! {lang}</b>\n🆔 <code>{user_id}</code>\n\n🔥 <b>Lunaranime Bot</b>\nSearch and discover your favorite manga instantly!\n\n👇 Tap <b>'🔍 Search Manga'</b> and enter a title to begin.""",

    "main_menu": """🏠 <b>Main Menu</b>\n\nPlease select an option:""",

    # Search Mode
    "search_mode": """🔍 <b>Search Mode Activated</b>\n\n📝 <b>Enter manga title below</b>\n\n✨ <b>Examples:</b>\n<code>one piece</code>\n<code>jujutsu kaisen</code>\n<code>demon slayer</code>\n\n⏳ Bot will automatically search results.""",
    "broadcast_mode": """<b>Broadcast Mode Activated</b>\n\n📝 <b>Enter message below</b>\n""",

    "searching": """🔍 <b>Searching</b> <code>{query}</code>...\n⏳ Please wait a moment.""",

    "search_success": """✅ <b>Search Results</b> for <code>{search_query}</code>""",

    "search_total": """📊 <b>Found {total} manga</b> | Page {page} of {total_pages}""",

    "no_results": """❌ <b>No results found</b> for <code>{search_query}</code>""",

    "search_suggestions": """💡 <b>Suggestions:</b>\n• One Piece\n• Naruto\n• Demon Slayer\n• Attack on Titan""",

    # Library
    "my_library": """📚 <b>Your Library</b>\n\n📖 Saved manga collection:""",
    "library_empty": """📚 <b>Your Library</b>\n\n📭 No manga saved yet.\n\n💡 Search and add manga to your library!""",

    # Manga Detail
    "manga_detail_title": """📖 <b>{title}</b>""",
    "manga_author": """✍️ <b>Author:</b> {author}""",
    "manga_artist": """🎨 <b>Artist:</b> {artist}""",
    "manga_genre": """🎭 <b>Genres:</b> {genres}""",
    "manga_status": """📊 <b>Status:</b> {status}""",
    "manga_languages": """🗣️ <b>Languages:</b> {langs}""",
    "manga_description": """📄 <b>Description:</b>\n{description}""",

    # Errors & Status
    "manga_not_found": """❌ <b>Manga not found</b>""",

    "unknown_menu": """❓ <b>Invalid option selected</b>""",

    "error_occurred": """❌ <b>An error occurred</b>\nPlease try again shortly.""",

    "api_error": """⚠️ <b>Service temporarily unavailable</b>\nPlease try again in a few moments.""",

    "search_error": """💥 <b>Search failed</b>\n{error}""",

    "privacy_not_available": """📄 <b>Privacy Policy</b>\n\nPrivacy policy documentation is currently unavailable.""",

    # Buttons & Actions
    "added_to_library": """✅ Added to your library""",
    "removed_from_library": """✅ Removed from library""",
    "already_in_library": """✅ Already in your library"""
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    force=True
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Determine if running on Windows
isWin = os.name == 'nt'
if isWin: __import__('colorama').init(autoreset=True)

# Terminal width function
def term_c(): return os.get_terminal_size().columns - isWin

# Simplified UI Colors
class UIColor:
    COLORS = {
        'black': '\x1b[0;30m',
        'orange': '\x1b[38;5;130m',
        'turquoise': '\x1b[38;5;50m',
        'smoothgreen': '\x1b[38;5;42m'
    }

    @classmethod
    def print_colored(cls, *values, sep=' ', end='\n', file=sys.stdout, flush=False, clr=False):
        cls.clear_line()
        prefix, suffix = '\x1b[0;1;39;49m', '\x1b[0;1;39;49m'
        if not isinstance(file, type(sys.stdout)): clr = True
        colored_values = [f"{prefix}{cls.placeholders(v, clr)}{suffix}" for v in values]
        print(*colored_values, sep=sep, end=end, flush=flush)

    @classmethod
    def placeholders(cls, raw_value: str, clr=False):
        raw_value = str(raw_value)
        for kc, vc in reversed(re.findall(r'(\?([\dbo]{1,3})`?)', raw_value)):
            if vc in 'bo':
                raw_value = raw_value.replace(kc, {'b': '\x1b[0;30m', 'o': '\x1b[38;5;130m'}.get(vc, ''))
            raw_value = raw_value.replace(kc, '' if clr else f'\x1b[{vc}m')
        return raw_value.replace('`', '')

    @classmethod
    def set_title(cls, title: str): sys.stdout.write(f'\x1b]2;{title}\a'); sys.stdout.flush()

    @classmethod
    def clear_screen(cls): os.system('cls' if isWin else 'clear')

    @classmethod
    def clear_line(cls, mode=2): print(f'\x1b[{mode}K', end='\r', flush=True)

    @classmethod
    def exit_with_msg(cls, msg: str): cls.print_colored(msg); sys.exit(1)

# Aliases for backward compatibility
printn = UIColor.print_colored

def format_languages(translated_languages: str) -> str:
    """Format translated_languages JSON string"""
    try:
        langs = json.loads(translated_languages or f"[]")
        if langs:
            lang_flags = {
                'id': '🇮🇩', 'en': '🇺🇸', 'ko': '🇰🇷',
                'jp': '🇯🇵', 'th': '🇹🇭', 'vi': '🇻🇳'
            }
            return ' '.join(lang_flags.get(lang, '🌐') for lang in langs[:3])
        return '🌐'
    except: return '🌐'

def get_read_url(slug: str) -> str:
    """Generate read URL from slug"""
    if slug: return f"https://lunaranime.ru/manga/{quote(slug)}"
    return "https://lunaranime.ru/manga"

class UserState:
    """Centralized user state management"""

    def __init__(self, context):
        self.context = context

    def get_search_results(self) -> dict:
        return self.context.user_data.get('search_results', {})

    def set_search_result(self, search_query: str, results: dict) -> None:
        self.context.user_data.update({
            'search_query': search_query,
            'search_results': results
        })

    @staticmethod
    def set_search_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        context.user_data.update({
            'state': 'search',
            'search_query': '',
            'search_results': {},
            'search_page': 1,
            'search_mode': True,
            "message_id": query.message.message_id,
            "chat_id": query.message.chat_id,
            "user_id": query.from_user.id
        })

    @staticmethod
    def get_state(context: ContextTypes.DEFAULT_TYPE) -> str:
        return context.user_data.get('state', 'idle')

    @staticmethod
    def clear_search(context: ContextTypes.DEFAULT_TYPE):
        context.user_data.update({
            'state': 'idle',
            'search_query': '',
            'search_results': {},
            'search_mode': False
        })

class MessageManager:
    @staticmethod
    async def send_temp(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str,
                       reply_markup=None, parse_mode='HTML', delay=DELETE_DELAY):
        """Send temporary message"""
        message = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            protect_content=True,
            disable_web_page_preview=True
        )

        # Schedule deletion
        context.job_queue.run_once(
            MessageManager._delete_message,
            when=delay,
            data={'chat_id': chat_id, 'message_id': message.message_id},
            name=f"del_{message.message_id}"
        )
        return message

    @staticmethod
    async def _delete_message(context: ContextTypes.DEFAULT_TYPE):
        """Internal delete callback"""
        job = context.job
        data = job.data

        try: await context.bot.delete_message(**data)
        except Exception as e: logger.debug(f"Delete failed (normal): {e}")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button presses."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # Handle manga selection dari hasil search
    if (
        data.startswith('manga_')
        or data.startswith('addlibrary_')
        or data.startswith('remlibrary_')
    ):
        slug = data.split('_')[1]
        results = context.user_data.get('search_results', {}).get('manga', [])

        chapters_index, lang = 0, None
        if data.count(':'):
            slug, chapters_index = slug.split(':')
            chapters_index = int(chapters_index)
        if data.count('/'):
            slug, lang = slug.split('/')

        if manga := next((m for m in results if m.get('slug') == slug), None):
            manga_data = {
                'title': manga.get('title', 'Unknown'),
                'author': manga.get('author', 'Unknown'),
                'artist': manga.get('artist', 'Unknown'),
                'genres': json.loads(manga.get('genres', '[]')),
                'status': manga.get('publication_status', 'Unknown'),
                'langs': manga.get('translated_languages'),
                'read_url': get_read_url(slug),
                'description': manga.get('description', 'No description')
            }
            response, keyboard = manga_detail(data, slug, manga_data, str(user_id), chapters_index, lang)
            keyboard.extend([[
                InlineKeyboardButton("🔍 Searched", callback_data='search_results'),
                InlineKeyboardButton("🏠 Menu", callback_data='main_menu')
            ]])

        elif manga_data := BOT_DATABASE.get(str(user_id), {}).get('Library', {}).get(slug):
            response, keyboard = manga_detail(data, slug, manga_data, str(user_id), chapters_index, lang)
            keyboard.extend([[
                InlineKeyboardButton("📚 My Library", callback_data='user_library'),
                InlineKeyboardButton("🏠 Menu", callback_data='main_menu')
            ]])

        else:
            response = MESSAGES["manga_not_found"]
            keyboard = [[InlineKeyboardButton("🏠 Menu", callback_data='main_menu')]]

    elif data == 'search_results':
        # Kembali ke hasil pencarian (butuh implementasi lebih lanjut)
        context.user_data['search_mode'] = False
        response, keyboard = search_results(
            context.user_data.get('search_query'),
            context.user_data.get('search_results', {})
        )

    elif data.startswith('user_'):
        user_id = int(data.split('_')[1])

    else:
        response = MESSAGES["unknown_menu"]
        return await main_menu_handler(update, context)

    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(
            text=response,
            reply_markup=reply_markup,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    except Exception as e: printn(f"?91`{e}")

def manga_detail(data: str, slug: str, manga_data: dict, user_id: str, chapters_index: int=0, lang=None) -> tuple[str, list]:
    """Generate manga detail response and keyboard"""
    # Library actions
    if data.startswith('addlibrary_'):
        BOT_DATABASE[user_id]['Library'][slug] = manga_data
        status_msg = MESSAGES["added_to_library"]

    elif data.startswith('remlibrary_'):
        if BOT_DATABASE.get(user_id, {}).get('Library', {}).get(slug):
            del BOT_DATABASE[user_id]['Library'][slug]
            status_msg = MESSAGES["removed_from_library"]

    # Library button
    readlist_btn = InlineKeyboardButton("✚ Add to Library", callback_data=f'addlibrary_{slug}')
    if BOT_DATABASE.get(user_id, {}).get('Library', {}).get(slug):
        readlist_btn = InlineKeyboardButton("✅ In Library", callback_data=f'remlibrary_{slug}')

    # Professional manga detail
    response = "\n\n".join([
        MESSAGES["manga_detail_title"].format(title=manga_data['title']),
        MESSAGES["manga_author"].format(author=manga_data['author']),
        MESSAGES["manga_artist"].format(artist=manga_data['artist']),
        MESSAGES["manga_genre"].format(genres=', '.join(manga_data['genres'])),
        MESSAGES["manga_status"].format(status=manga_data['status'].upper()),
        MESSAGES["manga_languages"].format(langs=format_languages(manga_data['langs'])),
        MESSAGES["manga_description"].format(description=manga_data['description'])
    ])


    buttons = []
    chapters_data = ApiLunaranime.get_chapters(slug)
    chapters = chapters_data['data']
    langs = list(chapters.keys())
    if not lang: lang = langs[0]

    for chapter in list(reversed(chapters.get(lang, [])))[chapters_index:chapters_index+15]:
        buttons.append(
            InlineKeyboardButton(f"Chapter {chapter['chapter_number']}", web_app={"url": f"https://lunaranime.ru/manga/{slug}/{chapter['chapter_number']}?lang={lang}"})
        )

    keyboard = [
        [readlist_btn, InlineKeyboardButton("🌐 Read Online", web_app={"url": manga_data['read_url']})],
        [
            InlineKeyboardButton("◀️", callback_data=f'manga_{slug}:{max(chapters_index-15, 0)}'),
            InlineKeyboardButton(format_languages(f"[\"{lang}\"]"), callback_data=f'manga_{slug}/{langs[(langs.index(lang)+1) %len(langs)]}'),
            InlineKeyboardButton("▶️", callback_data=f'manga_{slug}:{min(chapters_index+15, 15 * (chapters_data.get("count", 0)//15))}')
        ]
    ]
    chunk_size = 3
    keyboard.extend([buttons[i:i+chunk_size] for i in range(0, len(buttons), chunk_size)])
    return response, keyboard

def search_results(search_query: str, results: dict) -> tuple[str, list]:
    """Generate search results response and keyboard"""
    manga_list: List[Dict[str, Any]] = results.get('manga', [])
    total = results.get('total', 0)
    page = results.get('page', 1)
    total_pages = results.get('total_pages', 1)

    if not manga_list:
        response = f"{MESSAGES['no_results']}\n\n{MESSAGES['search_suggestions']}"
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data='main_menu')]]
        return response, keyboard

    responses = [
        f"{MESSAGES['search_success'].format(search_query=search_query)}",
        f"{MESSAGES['search_total'].format(total=total, page=page, total_pages=total_pages)}\n"
    ]

    buttons = []
    for index, manga in enumerate(manga_list, start=1):
        slug = manga.get('slug', '')
        title = html.escape(manga.get('title', 'Unknown'), quote=True)
        langs = format_languages(manga.get('translated_languages', ''))

        responses.append(f"{index:0>2}). <b>{title} {langs}</b>")
        buttons.append(
            InlineKeyboardButton(f"{index}", callback_data=f"manga_{slug}")
        )

    chunk_size = 5
    keyboard = [buttons[i:i+chunk_size] for i in range(0, len(buttons), chunk_size)]

    response = "\n".join(responses)

    if total_pages > 1:
        keyboard.extend([[
            InlineKeyboardButton("◀️ Page", callback_data='prevpage'),
            InlineKeyboardButton("▶️ Page", callback_data='nextpage'),
        ]])

    keyboard.extend([[
        InlineKeyboardButton("🔍 Search", callback_data='search_mode'),
        InlineKeyboardButton("🏠 Menu", callback_data='main_menu')
    ]])

    return response, keyboard

# GLOBAL ERROR HANDLER
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler"""
    logger.error(f"Update {update} caused error {context.error}")

    if update and hasattr(update, 'callback_query') and update.callback_query:
        try:
            await update.callback_query.answer(
                MESSAGES["error_occurred"],
                show_alert=True
            )
        except: pass

async def cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    """Auto cleanup"""
    if context.user_data.get("state") == "search":
        context.user_data.clear()
        logger.info("Auto cleanup job")

async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except: pass

    context.user_data.update({
        'state': 'broadcast',
        'broadcast_mode': True,
        "message_id": query.message.message_id,
        "chat_id": query.message.chat_id,
        "user_id": query.from_user.id
    })

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data='main_menu')]])
    await query.edit_message_text(
        text=MESSAGES["broadcast_mode"],
        reply_markup=reply_markup,
        parse_mode='HTML',
        disable_web_page_preview=True
    )

    message = "Pesan broadcast default!"

    # await context.bot.send_message(
    #     chat_id=query.message.chat_id,
    #     text=response,
    #     reply_markup=reply_markup,
    #     parse_mode='HTML',
    #     disable_web_page_preview=True
    # )

async def notify_user_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except: pass

    response = "List user:"

    buttons = []
    for user_id, data in BOT_DATABASE.items():
        if int(user_id) in ADMIN_USER_ID: continue
        buttons.append(InlineKeyboardButton(f"@{data['User']['username']}", callback_data=f"user_{user_id}"))

    chunk_size = 2
    keyboard = [buttons[i:i+chunk_size] for i in range(0, len(buttons), chunk_size)]
    keyboard.extend([[InlineKeyboardButton("🏠 Menu", callback_data='main_menu')]])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=response,
        reply_markup=reply_markup,
        parse_mode='HTML',
        disable_web_page_preview=True
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command /start"""
    context.user_data.clear()

    user = update.effective_user
    user_id = str(user.id)
    if not BOT_DATABASE.get(user_id):
        BOT_DATABASE.update({
            user_id: {
                'User': {
                    'first_name': user.first_name,
                    'username': user.username,
                    'is_bot': user.is_bot,
                    'language_code': user.language_code
                },
                'Library': {}
            }
        })

    await update.message.reply_html(
        MESSAGES["welcome"].format(user_mention=user.mention_html(), lang=format_languages(f"[\"{user.language_code}\"]"), user_id=user_id),
        reply_markup=await main_menu_keyboard(update),
        protect_content=True,
        disable_web_page_preview=True
    )

async def privacy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Privacy policy handler"""
    query = update.callback_query
    await query.answer()

    try: response = Path('privacy-policy.html').read_text(encoding='utf-8')
    except: response = MESSAGES["privacy_not_available"]

    keyboard = [
        [
            InlineKeyboardButton("🏠 Menu", callback_data='main_menu'),
            InlineKeyboardButton("💬 Contact", url='https://t.me/ShenZhiiyi')
        ]
    ]

    await query.edit_message_text(
        text=response,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML',
        disable_web_page_preview=True
    )

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, start_mode=False):
    """Menu utama"""
    query = update.callback_query
    try: await query.answer()
    except: pass

    context.user_data.clear()

    reply_markup = await main_menu_keyboard(update)
    if start_mode: return reply_markup

    await query.edit_message_text(
        text=MESSAGES["main_menu"],
        reply_markup=reply_markup,
        parse_mode='HTML',
        disable_web_page_preview=True
    )

async def main_menu_keyboard(update: Update) -> InlineKeyboardMarkup:
    """Generate main menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("🔍 Search Manga", callback_data='search_mode'),
            InlineKeyboardButton("📚 My Library", callback_data='user_library')
        ],
        [InlineKeyboardButton("📄 Privacy Policy", callback_data='privacy')]
    ]
    if update.effective_user.id in ADMIN_USER_ID:
        keyboard.insert(1, [
            InlineKeyboardButton("Broadcast", callback_data='broadcast_mode'),
            InlineKeyboardButton("Notify User", callback_data='notify_user')
        ])
        keyboard.insert(2, [
            InlineKeyboardButton("Source Code", callback_data='source_code')
        ])
    return InlineKeyboardMarkup(keyboard)

async def user_library_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    readlist = BOT_DATABASE.get(user_id, {}).get('Library')

    if not readlist:
        keyboard = [[InlineKeyboardButton("🔍 Search Manga", callback_data='search_mode')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=MESSAGES["library_empty"],
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return

    responses = [MESSAGES["my_library"]]
    index = 1
    buttons = []

    for slug, data in readlist.items():
        responses.append(f"{index:0>2}). <b>{html.escape(data.get('title', 'Unknown'), quote=True)} {format_languages(data['langs'])}</b>")
        buttons.append(
            InlineKeyboardButton(f"{index}", callback_data=f"manga_{slug}")
        )
        index += 1

    chunk_size = 5
    keyboard = [buttons[i:i+chunk_size] for i in range(0, len(buttons), chunk_size)]
    response = "\n".join(responses)

    keyboard.extend([[InlineKeyboardButton("🏠 Menu", callback_data='main_menu')]])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=response,
        reply_markup=reply_markup,
        parse_mode='HTML',
        disable_web_page_preview=True
    )

async def search_mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aktifkan search mode"""
    query = update.callback_query
    await query.answer()

    context.user_data.update({
        'state': 'search',
        'search_query': '',
        'search_results': {},
        'search_page': 1,
        'search_mode': True,
        "message_id": query.message.message_id,
        "chat_id": query.message.chat_id,
        "user_id": query.from_user.id
    })

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data='main_menu')]])
    await query.edit_message_text(
        text=MESSAGES["search_mode"],
        reply_markup=reply_markup,
        parse_mode='HTML',
        disable_web_page_preview=True
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Proses pesan search"""
    message = update.message
    search_query = message.text.strip()
    user_data = context.user_data
    chat_id = user_data.get("chat_id")
    message_id = user_data.get("message_id")

    # Hapus pesan user
    try: await update.message.delete()
    except TelegramError: pass

    if user_data.get("state") not in ["search", "broadcast"]:
        return

    if user_data.get("state") == "broadcast":
        success_count = 0
        for user_id in BOT_DATABASE.keys():
            if int(user_id) in ADMIN_USER_ID: continue
            try:
                await context.bot.send_message(chat_id=int(user_id), text=update.message.text, protect_content=True, disable_web_page_preview=True)
                success_count += 1
            except: continue

        reply_markup = await main_menu_keyboard(update)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=MESSAGES["main_menu"],
            reply_markup=reply_markup,
            parse_mode='HTML',
            disable_web_page_preview=True
        )

        await MessageManager.send_temp(
            context,
            update.effective_chat.id,
            f"📤 Broadcast terkirim ke {success_count} user",
            delay=10
        )

    if user_data.get("state") == "search":
        try:
            # Kirim loading message
            loading_msg = await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=MESSAGES["searching"].format(query=search_query),
                parse_mode='HTML',
                disable_web_page_preview=True
            )

            # Search manga
            results = ApiLunaranime.search_manga(query=search_query)
            ApiLunaranime.save_to_json(results)

            if results and results.get('message') == 'success':
                response, keyboard = search_results(search_query, results)
                context.user_data.update({
                    'search_query': search_query,
                    'search_results': results
                })

            else:
                response = MESSAGES["api_error"]
                keyboard = [[
                    InlineKeyboardButton("🔍 Search", callback_data='search_mode'),
                    InlineKeyboardButton("🏠 Menu", callback_data='main_menu')
                ]]

        except Exception as e:
            logger.error(f"Search error: {e}")
            response = MESSAGES["search_error"].format(error=str(e)[:100])
            keyboard = [[
                InlineKeyboardButton("🔍 Search", callback_data='search_mode'),
                InlineKeyboardButton("🏠 Menu", callback_data='main_menu')
            ]]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await loading_msg.edit_text(response, reply_markup=reply_markup, parse_mode='HTML')

async def admin_source_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kirim source code untuk admin only"""
    query = update.callback_query
    user_id = query.from_user.id

    if user_id not in ADMIN_USER_ID:
        await query.answer("❌ Admin only!", show_alert=True)
        return

    await query.answer("📤 Mengirim source code...")

    files = [
        ('LunaranimeBot-AIVersion.py', '🤖 Main Bot'),
        ('ApiLunaranime.py', '🌙 API Wrapper'),
        ('.LunaranimeBot.db.json', '📋 Dependencies'),
        ('privacy-policy.html', '📋 Dependencies')
    ]

    for file_path, caption in files:
        if Path(file_path).exists():
            try:
                message = await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=open(file_path, 'rb'),
                    caption=f"{caption}\nPath: `{file_path}`",
                    filename=Path(file_path).name,
                    parse_mode='Markdown',
                    protect_content=True
                )

                # Schedule deletion
                chat_id = update.effective_chat.id
                context.job_queue.run_once(
                    MessageManager._delete_message,
                    when=60,
                    data={'chat_id': chat_id, 'message_id': message.message_id},
                    name=f"del_{message.message_id}"
                )
            except Exception as e:
                logger.error(f"Failed to send {file_path}: {e}")

    await MessageManager.send_temp(
        context,
        update.effective_chat.id,
        "✅ Semua file source code telah dikirim! 🎉",
        delay=60
    )

ADMIN_UPLOAD_DIR = Path("admin_uploads")
ADMIN_UPLOAD_DIR.mkdir(exist_ok=True)

async def admin_file_receiver_hendler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin only file receiver"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_ID:
        await update.message.reply_text("❌ Admin only!")
        return

    message = update.message
    file = message.document
    if not file: return

    # Validasi
    allowed_types = ['.pdf', '.jpg', '.png', '.zip', '.py', '.txt', '.json', '.mp4', '.mp3']
    if not any(file.file_name.lower().endswith(ext) for ext in allowed_types):
        await message.reply_text("❌ Tipe file tidak diizinkan!")
        return

    if file.file_size > 20 * 1024 * 1024:  # 20MB
        await message.reply_text("❌ File terlalu besar! Max 20MB")
        return

    # Sanitize filename
    safe_name = re.sub(r'[^\w\-\.]', '_', file.file_name)
    file_path = ADMIN_UPLOAD_DIR / safe_name

    try:
        telegram_file = await context.bot.get_file(file.file_id)
        await telegram_file.download_to_drive(file_path)

        # Hapus pesan user
        try: await message.delete()
        except TelegramError: pass

        await MessageManager.send_temp(
            context,
            update.effective_chat.id,
            f"🖼️ <b>File diterima admin!</b>\n\n"
            f"📁 <code>{file_path.absolute()}</code>\n"
            f"📊 {file_path.stat().st_size / 1024:.1f} KB\n"
            f"👤 Dari: {update.effective_user.mention_html()}",
            delay=10
        )

        # Log
        logger.info(f"Admin {user_id} uploaded: {file_path}")

    except Exception as e:
        await MessageManager.send_temp(
            context,
            update.effective_chat.id,
            f"❌ Upload gagal: {str(e)}",
            delay=10
        )

async def admin_photo_receiver_hendler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Download foto ke server"""
    message = update.message
    user = update.effective_user
    photo = message.photo[-1]  # Best quality

    try:
        # Get file
        photo_file = await context.bot.get_file(photo.file_id)

        # Unique filename
        timestamp = int(time.time())
        ext = photo_file.file_path.split('.')[-1] if '.' in photo_file.file_path else 'jpg'
        filename = f"{timestamp}_{photo.width}x{photo.height}.{ext}"
        file_path = ADMIN_UPLOAD_DIR / filename

        # Download
        await photo_file.download_to_drive(file_path)

        # Hapus pesan user
        try: await message.delete()
        except TelegramError: pass

        await MessageManager.send_temp(
            context,
            update.effective_chat.id,
            f"🖼️ <b>Foto diterima admin!</b>\n\n"
            f"📁 `{file_path.absolute()}`\n"
            f"📏 Ukuran: {photo.width}x{photo.height}\n"
            f"📊 {file_path.stat().st_size / 1024:.1f} KB\n"
            f"👤 Dari: {user.mention_html()}",
            delay=10
        )

        logger.info(f"Photo {photo.width}x{photo.height} from {user.id}")

    except Exception as e:
        await MessageManager.send_temp(
            context,
            update.effective_chat.id,
            f"❌ Gagal simpan foto: {str(e)}",
            delay=10
        )


def atexit() -> None:
    import atexit
    UIColor.clear_screen()
    UIColor.set_title('LunaranimeBot')
    __import__('atexit').register(lambda:(
        UIColor.set_title(''),
        DB_FILE.write_bytes(
            json.dumps(BOT_DATABASE, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        )
    ))

def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN: UIColor.exit_with_msg("❌ Error: BOT_TOKEN not set.")

    app = ApplicationBuilder().token(BOT_TOKEN).job_queue(JobQueue()).build()

    # Handlers
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(privacy_handler, pattern='privacy'))
    app.add_handler(CallbackQueryHandler(main_menu_handler, pattern='main_menu'))
    app.add_handler(CallbackQueryHandler(notify_user_handler, pattern='notify_user'))
    app.add_handler(CallbackQueryHandler(broadcast_handler, pattern='broadcast_mode'))
    app.add_handler(CallbackQueryHandler(search_mode_handler, pattern='search_mode'))
    app.add_handler(CallbackQueryHandler(user_library_handler, pattern='user_library'))

    app.add_handler(CallbackQueryHandler(admin_source_handler, pattern='source_code'))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(MessageHandler(
        filters.PHOTO & filters.User(user_id=ADMIN_USER_ID),
        admin_photo_receiver_hendler
    ))
    app.add_handler(MessageHandler(
        filters.Document.ALL & filters.User(user_id=ADMIN_USER_ID),
        admin_file_receiver_hendler
    ))
    app.add_error_handler(error_handler)

    # Auto cleanup
    app.job_queue.run_repeating(cleanup_job, interval=300, first=60)

    printn("🚀 Bot started!")
    printn("Bot is running...")

    app.run_polling()

if __name__ == "__main__":
    atexit()
    main()
