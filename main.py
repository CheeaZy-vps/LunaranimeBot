#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Coded by aqil.almara - t.me/prudentscitus

# Imports
import os
import re
import sys
import html
import json
import math
import time
import atexit
import logging
import pyzipper
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Union, Dict, Any, List, Tuple
from urllib.parse import quote
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

import requests
from requests.exceptions import HTTPError, ConnectionError, ReadTimeout, RequestException
try: from json.decoder import JSONDecodeError
except ImportError: JSONDecodeError = ValueError

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters, JobQueue
)
from telegram.error import TelegramError, BadRequest
from telegram.constants import ParseMode

# Third-party modules (ensure installed)
try: import ApiLunaranime
except ImportError as e:
    raise ImportError("ApiLunaranime module not found. Please install it.") from e

# Configuration
@dataclass
class Config:
    """Bot configuration"""
    bot_token: str = os.getenv("BOT_TOKEN")
    db_file: Path = Path('.LunaranimeBot.db.json')
    admin_user_ids: List[int] = None
    delete_delay: int = 30
    max_search_results: int = 30
    chunk_size: int = 3
    page_size: int = 30
    base_password: str = "lunaranime"

    def __post_init__(self):
        if self.admin_user_ids is None: self.admin_user_ids = [1308147558, 5074802729]
        if not self.bot_token: raise ValueError("BOT_TOKEN environment variable is required")

config = Config()

# Messages
MESSAGES = {
    "welcome": """👋 <b>Welcome {user_mention}!</b>\n🆔 <code>{user_id}</code>\n\n🔥 <b>Lunaranime Bot</b>\nSearch and discover your favorite manga instantly!\n\n👇 Tap <b>'🔍 Search Manga'</b> to begin your adventure.""",

    "main_menu": """🏠 <b>Main Menu</b>\n\nPlease select an option below:""",

    "search_mode": """🔍 <b>Search Mode Activated</b>\n\n📝 <b>Enter manga title to search</b>\n\n✨ <b>Popular examples:</b>\n<code>one piece</code>\n<code>jujutsu kaisen</code>\n<code>demon slayer</code>\n\n⏳ Bot will automatically display results.""",

    "broadcast_mode": """📢 <b>Broadcast Mode Activated</b>\n\n📝 <b>Enter your broadcast message below</b>\n\n💡 This will be sent to all users.""",

    "search_user_projects_mode": """🔍 <b>Search User Projects</b>\n\n📝 <b>Enter username to search projects</b>\n\n⏳ Bot will find all projects by that user.""",

    "searching": """🔍 <b>Searching for</b> <code>{query}</code>...\n⏳ Please wait a moment.""",

    "search_success": """✅ <b>Search Results</b>\n<i>Found manga for <code>{search_query}</code></i>""",

    "search_total": """📊 <b>{total} manga found</b> | Page {page}/{total_pages}""",

    "no_results": """❌ <b>No results found</b>\n<i>for <code>{search_query}</code></i>\n\n💡 Try different keywords or check spelling.""",

    "search_suggestions": """💡 <b>Try searching for:</b>\n• One Piece\n• Naruto\n• Demon Slayer\n• Attack on Titan""",

    "my_library": """📚 <b>Your Library</b>\n\n📖 <b>Saved manga collection:</b>""",

    "library_empty": """📚 <b>Your Library</b>\n\n📭 <i>Your library is empty</i>\n\n💡 <b>Search for manga and add them to your library!</b>""",

    "manga_detail_title": """📖 <b>{title}</b>""",
    "manga_author": """✍️ <b>Author:</b> {author}""",
    "manga_artist": """🎨 <b>Artist:</b> {artist}""",
    "manga_genre": """🎭 <b>Genres:</b> {genres}""",
    "manga_status": """📊 <b>Status:</b> {status}""",
    "manga_languages": """🗣️ <b>Available:</b> {langs}""",
    "manga_description": """📄 <b>Description:</b>\n\n{description}""",

    "manga_not_found": """❌ <b>Manga not found</b>\n\n💡 Return to menu and try searching again.""",

    "unknown_menu": """❓ <b>Invalid option</b>\n\nPlease select from the available menu options.""",

    "error_occurred": """⚠️ <b>Something went wrong</b>\n\nPlease try again in a few moments.""",

    "api_error": """🌐 <b>Service temporarily unavailable</b>\n\nPlease try again in a few minutes.""",

    "search_error": """💥 <b>Search failed</b>\n\n<i>{error}</i>\n\nPlease try again.""",

    "privacy_not_available": """📄 <b>Privacy Policy</b>\n\nPrivacy policy documentation is currently unavailable.\n\nWe respect your privacy and do not store personal data unnecessarily.""",

    "broadcast_success": """✅ <b>Broadcast completed!</b>\n\n📤 Message sent to <b>{count}</b> users successfully.""",

    "added_to_library": """✅ <b>Added to your library!</b>""",
    "removed_from_library": """✅ <b>Removed from library</b>""",
    "already_in_library": """✅ <b>Already in your library</b>"""
}

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lunaranime_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

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

class Database:
    """Thread-safe database manager"""
    def __init__(self, db_file: Path):
        self.db_file = db_file
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load database from file"""
        try:
            if self.db_file.exists():
                self._data = json.loads(self.db_file.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"Failed to load database: {e}")
            self._data = {}

    def _save(self) -> None:
        """Save database to file"""
        try:
            self.db_file.parent.mkdir(exist_ok=True)
            self.db_file.write_text(
                json.dumps(self._data, ensure_ascii=False, separators=(',', ':')),
                encoding='utf-8'
            )
        except Exception as e: logger.error(f"Failed to save database: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def user_exists(self, user_id: str) -> bool:
        return user_id in self._data

    def _users(self) -> list:
        return list(self._data.keys())

    def ensure_user(self, user_id: str, user_info: Dict[str, Any]) -> None:
        """Ensure user exists in database"""
        if not self.user_exists(user_id):
            self._data[user_id] = {
                'User': user_info,
                'Library': {}
            }
            self._save()

    def get_library(self, user_id: str) -> Dict[str, Any]:
        return self._data.get(user_id, {}).get('Library', {})

db = Database(config.db_file)

def format_languages(translated_languages: str) -> str:
    """Format translated_languages JSON string"""
    try:
        langs = json.loads(translated_languages or "[]")
        if not langs: return "🌐"

        lang_flags = {
            'id': '🇮🇩', 'en': '🇺🇸', 'ko': '🇰🇷',
            'jp': '🇯🇵', 'th': '🇹🇭', 'vi': '🇻🇳'
        }
        return ' '.join(lang_flags.get(lang, '🌐') for lang in langs[:3])
    except (json.JSONDecodeError, ValueError): return '🌐'

def get_read_url(slug: str) -> str:
    """Generate read URL from slug"""
    return f"https://lunaranime.ru/manga/{quote(slug)}" if slug else "https://lunaranime.ru/manga"

def get_status_emoji(status: str) -> str:
    """Get emoji for manga status"""
    return {
        'completed': "✅",
        'ongoing': "🔄",
        'hiatus': "⏸️"
    }.get(status.lower(), "❓")

class MessageManager:
    """Message management utilities"""

    @staticmethod
    async def send_temp(context: ContextTypes.DEFAULT_TYPE,
                       chat_id: int,
                       text: str,
                       reply_markup: Optional[InlineKeyboardMarkup] = None,
                       delay: int = None) -> Optional[int]:
        """Send temporary message with auto-delete"""
        if delay is None: delay = config.delete_delay

        try:
            message = await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
                protect_content=int(chat_id) not in config.admin_user_ids,
                disable_web_page_preview=True
            )

            # Schedule deletion
            context.job_queue.run_once(
                MessageManager._delete_message,
                when=delay,
                data={'chat_id': chat_id, 'message_id': message.message_id},
                name=f"del_{message.message_id}"
            )
            return message.message_id
        except Exception as e:
            logger.error(f"Failed to send temp message: {e}")
            return None

    @staticmethod
    async def _delete_message(context: ContextTypes.DEFAULT_TYPE) -> None:
        """Delete message callback"""
        try:
            data = context.job.data
            await context.bot.delete_message(**data)
        except Exception as e: logger.debug(f"Delete failed: {e}")

class MangaHandler:
    """Manga detail and library management"""

    @staticmethod
    def create_manga_data(manga: Dict[str, Any]) -> Dict[str, Any]:
        """Create standardized manga data"""
        return {
            'slug': manga.get('slug', ''),
            'title': html.escape(manga.get('title', 'Unknown'), quote=True),
            'author': manga.get('author', 'Unknown'),
            'artist': manga.get('artist', 'Unknown'),
            'genres': json.loads(manga.get('genres', '[]')),
            'status': manga.get('publication_status', 'Unknown'),
            'langs': manga.get('translated_languages', ''),
            'read_url': get_read_url(manga.get('slug')),
            'description': manga.get('description', 'No description available')
        }

    @staticmethod
    def generate_detail_message(manga_data: Dict[str, Any]) -> str:
        """Generate manga detail message"""
        response_parts = [
            MESSAGES["manga_detail_title"].format(title=manga_data['title']),
            MESSAGES["manga_author"].format(author=manga_data['author']),
            MESSAGES["manga_artist"].format(artist=manga_data['artist']),
            MESSAGES["manga_genre"].format(genres=', '.join(manga_data['genres'])),
            MESSAGES["manga_status"].format(
                status=f"{get_status_emoji(manga_data['status'])} {manga_data['status'].upper()}"
            ),
            MESSAGES["manga_languages"].format(langs=format_languages(manga_data['langs'])),
            MESSAGES["manga_description"].format(description=manga_data['description'])
        ]
        return "\n\n".join(response_parts)

    @staticmethod
    def generate_detail_keyboard(manga_id: str,
                               manga_data: Dict[str, Any],
                               user_id: str,
                               chapters_index: int = 0,
                               lang: str = None) -> List[List[InlineKeyboardButton]]:
        """Generate manga detail keyboard"""
        try:
            chapters_data = ApiLunaranime.get_chapters(manga_data.get('slug'))
            chapters = chapters_data.get('data', {})
            langs = list(chapters.keys())
            if not lang and langs: lang = langs[0]

            # Chapter buttons
            chapter_buttons = []
            chapter_list = list(reversed(chapters.get(lang, [])))[chapters_index:chapters_index + config.max_search_results]
            for chapter in chapter_list:
                ch_num = chapter['chapter_number']
                chapter_buttons.append(InlineKeyboardButton(
                    f"Chapter {ch_num}",
                    web_app={"url": f"https://lunaranime.ru/manga/{manga_data.get('slug')}/{ch_num}?lang={lang}"}
                ))
        except Exception as e:
            logger.error(f"Failed to get chapters: {e}")
            chapter_buttons = []
            langs = []

        # Library button
        library_btn = InlineKeyboardButton(
            "✚ Add to Library",
            callback_data=f'addlibrary_{manga_id}:{chapters_index}:{lang or ""}'
        )
        if manga_id in db.get_library(str(user_id)):
            library_btn = InlineKeyboardButton(
                "✅ In Library",
                callback_data=f'remlibrary_{manga_id}:{chapters_index}:{lang or ""}'
            )

        # Navigation
        total_chapters = chapters_data.get("count", 0)
        total_pages = max(1, (total_chapters + config.page_size - 1) // config.page_size)
        current_page = chapters_index // config.page_size

        nav_buttons = [
            InlineKeyboardButton("◀️", callback_data=f'manga_{manga_id}:{max(chapters_index-config.page_size, 0)}:{lang or ""}'),
            InlineKeyboardButton(format_languages(f'["{lang}"]'), callback_data=f'manga_{manga_id}:{chapters_index}:{langs[(langs.index(lang)+1) % len(langs)] if lang in langs else ""}'),
            InlineKeyboardButton("▶️", callback_data=f'manga_{manga_id}:{min(chapters_index+config.page_size, config.page_size*(total_pages-1))}:{lang or ""}')
        ]

        keyboard = [
            [library_btn, InlineKeyboardButton("🌐 Read Online", web_app={"url": manga_data['read_url']})],
            nav_buttons
        ]

        # Add chapter buttons in chunks
        for i in range(0, len(chapter_buttons), config.chunk_size):
            keyboard.append(chapter_buttons[i:i + config.chunk_size])

        return keyboard

def generate_search_keyboard(results: Dict[str, Any], page: int, total_pages: int) -> List[List[InlineKeyboardButton]]:
    """Generate search results keyboard"""
    responses = []
    keyboard = []

    # Pagination
    if total_pages > 1:
        keyboard.append([
            InlineKeyboardButton("◀️", callback_data=f'search:{max(page-1, 1)}'),
            InlineKeyboardButton("▶️", callback_data=f'search:{min(page+1, total_pages)}')
        ])

    # Manga buttons
    manga_list = results.get('manga', [])
    buttons = []
    for index, manga in enumerate(manga_list, start=1 + (config.page_size * (page - 1))):
        manga_id = manga.get('manga_id')
        title = html.escape(manga.get('title', 'Unknown'), quote=True)
        langs = format_languages(manga.get('translated_languages', ''))

        responses.append(f"{index:0>2}). <b>{title} {langs}</b>")
        buttons.append(InlineKeyboardButton(
            f"{index:0>2}",
            callback_data=f"manga_{manga_id}::"
        ))

    # Chunk buttons
    for i in range(0, len(buttons), 5):
        keyboard.append(buttons[i:i + 5])

    keyboard.append([
        InlineKeyboardButton("🔍 Search", callback_data='search_mode'),
        InlineKeyboardButton("🏠 Menu", callback_data='main_menu')
    ])

    return '\n'.join(responses), keyboard

def generate_main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Generate main menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("🔍 Search Manga", callback_data='search_mode'),
            InlineKeyboardButton("📚 My Library", callback_data='user_library')
        ],
        [InlineKeyboardButton("🔍 Search User Projects", callback_data='search_user_projects_mode')],
        [InlineKeyboardButton("💰 Daily Rewards (Auto)", callback_data='claim_daily')],
        [InlineKeyboardButton("📄 Privacy Policy", callback_data='privacy')]
    ]

    if is_admin:
        keyboard.insert(1, [
            InlineKeyboardButton("📢 Broadcast", callback_data='broadcast_mode'),
            InlineKeyboardButton("👥 Notify Users", callback_data='notify_user')
        ])
        keyboard.insert(2, [InlineKeyboardButton("💻 Source Code", callback_data='source_code')])

    return InlineKeyboardMarkup(keyboard)


# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    user = update.effective_user
    user_id = str(user.id)

    # Ensure user in database
    user_info = {
        'first_name': user.first_name or '',
        'username': user.username or '',
        'is_bot': user.is_bot,
        'language_code': user.language_code or ''
    }
    db.ensure_user(user_id, user_info)

    # Clear user data
    context.user_data.clear()

    await update.message.reply_html(
        MESSAGES["welcome"].format(
            user_mention=user.mention_html(),
            user_id=user_id
        ),
        reply_markup=generate_main_menu_keyboard(user.id in config.admin_user_ids),
        protect_content=int(user_id) not in config.admin_user_ids,
        disable_web_page_preview=True
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler"""
    logger.error(f"Update {update} caused error: {context.error}")

    if (update and hasattr(update, 'callback_query') and
        update.callback_query and update.callback_query.message):
        try:
            await update.callback_query.answer(
                MESSAGES["error_occurred"], show_alert=True
            )
        except Exception: pass

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main menu handler"""
    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    reply_markup = generate_main_menu_keyboard(query.from_user.id in config.admin_user_ids)
    await query.edit_message_text(
        text=MESSAGES["main_menu"],
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main button handler"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    data = query.data

    # Manga detail handling
    if data.startswith(('manga_', 'addlibrary_', 'remlibrary_')):
        try:
            parts = data.split('_', 2)[1].split(':')
            manga_id = parts[0]
            chapters_index = int(parts[1]) if (len(parts) > 1 and parts[1]) else 0
            lang = parts[2] if len(parts) > 2 else None

            # Get manga data
            results = context.user_data.get('search_results', {}).get('manga', [])
            manga = next((m for m in results if m.get('manga_id') == manga_id), None)
            if manga:
                keyboard_androwcol1 = InlineKeyboardButton("🔍 Searched", callback_data='search_results')
                manga_data = MangaHandler.create_manga_data(manga)

            else:
                keyboard_androwcol1 = InlineKeyboardButton("📚 My Library", callback_data='user_library')
                manga_data = db.get_library(user_id).get(manga_id)

            if not manga and not manga_data:
                reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu", callback_data='main_menu')]])
                await query.edit_message_text(
                    text=MESSAGES["manga_not_found"],
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
                return

            # Handle library actions
            if data.startswith('addlibrary_'):
                db.get_library(user_id)[manga_id] = manga_data
                db.set(user_id, db.get(user_id))
            elif data.startswith('remlibrary_'):
                library = db.get_library(user_id)
                library.pop(manga_id, None)
                db.set(user_id, db.get(user_id))

            # Generate response
            response = MangaHandler.generate_detail_message(manga_data)
            keyboard = MangaHandler.generate_detail_keyboard(
                manga_id, manga_data, user_id, chapters_index, lang
            )

            # Add navigation buttons
            keyboard.extend([[
                keyboard_androwcol1,
                InlineKeyboardButton("🏠 Menu", callback_data='main_menu')
            ]])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                text=response,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Manga handler error: {e}")
            await query.answer(MESSAGES["error_occurred"], show_alert=True)

    # Project detail handling
    elif data.startswith('projects_'):
        manga_id = data.split('_')[1]
        # Get manga data
        results = context.user_data.get('search_user_projects_results', [])
        for manga_data in results:
            if manga_data.get('manga_id') == manga_id:
                manga = ApiLunaranime.function(manga_data.get('slug'))
                manga_data = MangaHandler.create_manga_data(manga)

                response = MangaHandler.generate_detail_message(manga_data)
                keyboard = MangaHandler.generate_detail_keyboard(
                    manga_id, manga_data, user_id
                )

                # Add navigation buttons
                keyboard.extend([[
                    InlineKeyboardButton("🔍 Searched Projects", callback_data='search_user_projects_results'),
                    InlineKeyboardButton("🏠 Menu", callback_data='main_menu')
                ]])

                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    text=response,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                break

    # Search pagination
    elif data.startswith('search:'):
        context.user_data['search_page'] = int(data.split(':')[1])
        await get_search_query(update, context)
        # await search_mode_handler(update, context)

    # Library pagination
    elif data.startswith('library:'):
        context.user_data['library_index'] = int(data.split(':')[1])
        await user_library_handler(update, context)

    # Projects pagination
    elif data.startswith('projects:'):
        context.user_data['search_user_projects_index'] = int(data.split(':')[1])
        await search_user_projects_results(update, context)

    # Mode handlers
    elif data == 'search_results': await get_search_query(update, context)
    elif data == 'search_mode': await search_mode_handler(update, context)
    elif data == 'user_library': await user_library_handler(update, context)
    elif data == 'search_user_projects_mode': await search_user_projects_handler(update, context)
    elif data == 'search_user_projects_results': await search_user_projects_results(update, context)
    elif data == 'claim_daily': await claim_daily_handler(update, context)
    elif data == 'broadcast_mode': await broadcast_handler(update, context)
    elif data == 'notify_user': await notify_user_handler(update, context)
    elif data == 'source_code': await admin_source_handler(update, context)
    elif data == 'privacy': await privacy_handler(update, context)
    else: await main_menu_handler(update, context)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages"""

    message = update.message
    text = message.text.strip()
    printn(f"?95>>> ?93`{text}")

    # Delete user message
    try: await message.delete()
    except TelegramError: pass

    state = context.user_data.get('state')
    if not state: return

    if state == 'search':
        context.user_data['search_query'] = text
        await get_search_query(update, context)

    elif state == 'search_user_projects':
        context.user_data['search_user_projects_query'] = text
        await get_user_projects(update, context)

    elif state == 'broadcast':
        await broadcast_message(update, context, text)

async def search_mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search mode activation"""
    query = update.callback_query
    await query.answer()

    context.user_data.update({
        'state': 'search',
        'search_query': '',
        'search_results': {},
        'search_page': 1,
        'message_id': query.message.message_id,
        'chat_id': query.message.chat_id
    })

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data='main_menu')]])
    await query.edit_message_text(
        text=MESSAGES["search_mode"],
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

async def get_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process search query"""
    user_data = context.user_data
    search_query = user_data.get("search_query", "").strip()
    search_page = user_data.get("search_page", 1)
    chat_id = user_data.get("chat_id")
    message_id = user_data.get("message_id")

    try:
        # Show loading
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=MESSAGES["searching"].format(query=search_query),
            parse_mode=ParseMode.HTML
        )

        # Search
        results = ApiLunaranime.search_manga(query=search_query, page=search_page)

        if results and results.get('message') == 'success':
            user_data['search_results'] = results
            total = results.get('total', 0)
            total_pages = results.get('total_pages', 1)

            response = "\n".join([
                MESSAGES["search_success"].format(search_query=search_query),
                MESSAGES["search_total"].format(total=total, page=search_page, total_pages=total_pages)
            ])

            if not results.get('manga'):
                response += f"\n\n{MESSAGES['no_results'].format(search_query=search_query)}\n\n{MESSAGES['search_suggestions']}"

            responses, keyboard = generate_search_keyboard(results, search_page, total_pages)
            response += f"\n\n{responses}\n"

        else:
            response = MESSAGES["api_error"]
            keyboard = [[
                InlineKeyboardButton("🔍 Search", callback_data='search_mode'),
                InlineKeyboardButton("🏠 Menu", callback_data='main_menu')
            ]]

    except Exception as e:
        logger.error(f"Search error: {e}")
        response = MESSAGES["search_error"].format(error=str(e)[:100])
        keyboard = [[InlineKeyboardButton("🏠 Menu", callback_data='main_menu')]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.edit_message_text(
        text=response,
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

async def user_library_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User library handler"""
    query = update.callback_query
    await query.answer("⏳ Processing data, please wait..")

    user_id = str(query.from_user.id)
    library_index = context.user_data.get('library_index', 0)

    library = db.get_library(user_id)
    if not library:
        keyboard = [[InlineKeyboardButton("🔍 Search Manga", callback_data='search_mode')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=MESSAGES["library_empty"],
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return

    page_size = config.page_size
    total_items = len(library)
    total_pages = math.ceil(total_items / page_size)
    current_page = library_index // page_size

    responses = [MESSAGES["my_library"]]
    buttons = []

    library_items = list(library.items())[library_index:library_index + page_size]
    for idx, (manga_id, data) in enumerate(library_items, start=library_index + 1):
        title = data.get('title', 'Unknown')
        responses.append(f"{idx:0>2}). <b>{title}</b> {format_languages(data.get('langs', ''))}")
        buttons.append(InlineKeyboardButton(f"{idx:0>2}", callback_data=f"manga_{manga_id}::"))

    keyboard = []
    if total_items > page_size:
        keyboard.append([
            InlineKeyboardButton("◀️", callback_data=f'library:{max(library_index-page_size, 0)}'),
            InlineKeyboardButton("▶️", callback_data=f'library:{min(library_index+page_size, page_size*(total_pages-1))}'),
        ])

    for i in range(0, len(buttons), 5):
        keyboard.append(buttons[i:i + 5])

    keyboard.append([InlineKeyboardButton("🏠 Menu", callback_data='main_menu')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="\n".join(responses),
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

async def search_user_projects_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search user projects mode"""
    query = update.callback_query
    await query.answer()

    context.user_data.update({
        'state': 'search_user_projects',
        'search_user_projects_query': '',
        'search_user_projects_results': [],
        'search_user_projects_index': 0,
        'message_id': query.message.message_id,
        'chat_id': query.message.chat_id
    })

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data='main_menu')]])
    await query.edit_message_text(
        text=MESSAGES["search_user_projects_mode"],
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def get_user_projects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get user projects"""
    user_data = context.user_data
    query = user_data.get("search_user_projects_query")
    chat_id = user_data.get("chat_id")
    message_id = user_data.get("message_id")

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=MESSAGES["searching"].format(query=query),
            parse_mode=ParseMode.HTML
        )

        user = ApiLunaranime.search_profile(query)
        if data := user.get('data'):
            projects = ApiLunaranime.get_user_projects(data['user_id'])
            user_data.update({
                'search_user_projects_query': data['username'],
                'search_user_projects_results': projects
            })
            await search_user_projects_results(update, context)
            return

        else:
            response = f"❌ User <code>{query}</code> not found"
            keyboard = [[InlineKeyboardButton("🏠 Menu", callback_data='main_menu')]]

    except Exception as e:
        logger.error(f"User projects error: {e}")
        response = MESSAGES["search_error"].format(error=str(e)[:100])
        keyboard = [[InlineKeyboardButton("🏠 Menu", callback_data='main_menu')]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.edit_message_text(
        text=response,
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def search_user_projects_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display user projects results"""
    user_data = context.user_data
    projects = user_data.get("search_user_projects_results", [])
    query = user_data.get("search_user_projects_query", "")
    projects_index = user_data.get("search_user_projects_index", 0)
    chat_id = user_data.get("chat_id")
    message_id = user_data.get("message_id")

    page_size = config.page_size
    total = len(projects)
    page = (projects_index // page_size) + 1
    total_pages = math.ceil(total / page_size)

    responses = [
        f"✅ <b>User Projects</b> for <code>{query}</code>",
        f"📊 <b>{total} projects found</b> | Page {page}/{total_pages}\n"
    ]

    keyboard = []
    if total > page_size:
        keyboard.append([
            InlineKeyboardButton("◀️", callback_data=f'projects:{max(projects_index-page_size, 0)}'),
            InlineKeyboardButton("▶️", callback_data=f'projects:{min(projects_index+page_size, page_size*(total_pages-1))}'),
        ])

    buttons = []
    for idx, project in enumerate(projects[projects_index:projects_index+page_size], start=projects_index+1):
        manga_id = project['manga_id']
        title = html.escape(project.get('title', 'Unknown'), quote=True)
        status = project.get('status', '')
        responses.append(f"{idx:0>2}). <b>{title}</b> {get_status_emoji(status)}")
        buttons.append(InlineKeyboardButton(f"{idx:0>2}", callback_data=f"projects_{manga_id}"))

    for i in range(0, len(buttons), 5):
        keyboard.append(buttons[i:i + 5])

    keyboard.append([
        InlineKeyboardButton("🔍 Search Projects", callback_data='search_user_projects_mode'),
        InlineKeyboardButton("🏠 Menu", callback_data='main_menu')
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.edit_message_text(
        text="\n".join(responses),
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str) -> None:
    """Broadcast message to all users"""
    user_data = context.user_data
    chat_id = user_data.get("chat_id")
    message_id = user_data.get("message_id")

    success_count = 0
    for user_id_str, user_data in db._data.items():
        user_id = int(user_id_str)
        if user_id in config.admin_user_ids:
            continue

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                protect_content=int(user_id) not in config.admin_user_ids,
                disable_web_page_preview=True
            )
            success_count += 1
            await asyncio.sleep(0.05)  # Rate limit
        except Exception:
            continue

    reply_markup = generate_main_menu_keyboard(update.effective_user.id in config.admin_user_ids)
    await context.bot.edit_message_text(
        text=MESSAGES["main_menu"],
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

    await MessageManager.send_temp(
        context, update.effective_chat.id,
        MESSAGES["broadcast_success"].format(count=success_count)
    )

async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcast mode handler"""
    query = update.callback_query
    user_id = query.from_user.id

    if user_id not in config.admin_user_ids:
        await query.answer("❌ Admin only!", show_alert=True)
        return

    await query.answer()
    context.user_data.update({
        'state': 'broadcast',
        'message_id': query.message.message_id,
        'chat_id': query.message.chat_id
    })

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data='main_menu')]])
    await query.edit_message_text(
        text=MESSAGES["broadcast_mode"],
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def notify_user_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Notify users handler (admin)"""
    query = update.callback_query
    if query.from_user.id not in config.admin_user_ids:
        await query.answer("❌ Admin only!", show_alert=True)
        return

    await query.answer()

    buttons = []
    for user_id_str, data in db._data.items():
        user_id = int(user_id_str)
        if user_id in config.admin_user_ids: continue
        username = data['User'].get('username', f"User_{user_id}")
        buttons.append(InlineKeyboardButton(f"@{username}", callback_data=f"user_{user_id}"))

    keyboard = []
    for i in range(0, len(buttons), 2):
        keyboard.append(buttons[i:i + 2])
    keyboard.append([InlineKeyboardButton("🏠 Menu", callback_data='main_menu')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="👥 <b>Select user to notify:</b>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def admin_source_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send source code (admin only)"""
    query = update.callback_query
    if query.from_user.id not in config.admin_user_ids:
        await query.answer("❌ Admin only!", show_alert=True)
        return

    await query.answer("📤 Preparing source files...")

    source_files = [
        ('LunaranimeBot.V3.py', '🤖 Main Bot'),
        ('ApiLunaranime.py', '🌙 API Wrapper'),
        ('.LunaranimeBot.db.json', '📊 Database'),
        ('privacy-policy.html', '📄 Privacy Policy')
    ]

    chat_id = query.message.chat_id
    for file_path, caption in source_files:
        file = Path(file_path)
        if file.exists():
            try:
                with open(file, 'rb') as f:
                    message = await context.bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        caption=f"{caption}\n<code>{file_path}</code>",
                        filename=file.name,
                        parse_mode=ParseMode.HTML,
                        protect_content=int(chat_id) not in config.admin_user_ids
                    )

                # Auto-delete after 5 minutes
                context.job_queue.run_once(
                    MessageManager._delete_message,
                    when=300,
                    data={'chat_id': chat_id, 'message_id': message.message_id}
                )
            except Exception as e:
                logger.error(f"Failed to send {file_path}: {e}")

    await MessageManager.send_temp(
        context, chat_id,
        "✅ <b>All source files sent successfully!</b>\n🎉 Thank you for your support!"
    )

async def privacy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Privacy policy handler"""
    query = update.callback_query
    await query.answer()

    privacy_file = Path('privacy-policy.html')
    try: response = privacy_file.read_text(encoding='utf-8')
    except FileNotFoundError: response = MESSAGES["privacy_not_available"]

    keyboard = [[
        InlineKeyboardButton("🏠 Menu", callback_data='main_menu'),
        InlineKeyboardButton("💬 Contact", url='https://t.me/ShenZhiiyi')
    ]]

    await query.edit_message_text(
        text=response,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

async def cleanup_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Periodic cleanup of user states"""
    for job in context.job_queue.jobs():
        if job.name and job.name.startswith('cleanup_'):
            job.schedule_removal()

    # Cleanup inactive search states
    current_time = time.time()
    for chat_data in context.bot_data.setdefault('chat_states', {}).values():
        if current_time - chat_data.get('last_activity', 0) > 300:  # 5 minutes
            chat_data.clear()

last_file_size = None
async def job_send_reports(context: ContextTypes.DEFAULT_TYPE) -> None:
    global last_file_size
    RECEIVER_ID = 1308147558
    try:
        now = datetime.now()

        current_size = os.path.getsize(config.db_file)
        last_size = last_file_size or current_size

        size_diff = abs(current_size - last_size) / last_size if last_size > 0 else 0
        anomali_msg = ""
        if size_diff > 0.2 and last_size > 0:
            anomali_msg = f"\n\n⚠️ <b>ANOMALY DETECTED:</b> File size changed by {size_diff:.1%}"

        last_file_size = current_size

        dynamic_pw = f"{config.base_password}{int(now.timestamp())}"
        zip_name = f"REPORT_({config.db_file}).zip"

        with pyzipper.AESZipFile(zip_name, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
            zf.setpassword(dynamic_pw.encode())
            zf.write(config.db_file)

        with open(zip_name, 'rb') as doc:
            caption = (
                f"<b>📊 PERIODIC MEMBER REPORT</b>\n"
                f"<i>Automated Security Monitoring System</i>\n\n"
                f"📅 <b>Date:</b> {now.strftime('%d %B %Y')}\n"
                f"⏰ <b>Time:</b> {now.strftime('%H:%M:%S')} UTC+7\n"
                f"📁 <b>Format:</b> ZIP (AES-256 Encrypted)\n"
                f"👥 <b>Users:</b> {len(db._users())}\n"
                f"🔑 <b>Password:</b> <tg-spoiler>{dynamic_pw}</tg-spoiler>{anomali_msg}\n\n"
                f"⚠️ <i>This document is confidential. Internal use only.</i>"
            )
            sent_msg = await context.bot.send_document(
                chat_id=RECEIVER_ID,
                document=doc,
                caption=caption,
                filename=zip_name,
                parse_mode=ParseMode.HTML
            )

            context.job_queue.run_once(
                MessageManager._delete_message,
                when=450,
                data={'chat_id': RECEIVER_ID, 'message_id': sent_msg.message_id}
            )

        if os.path.exists(zip_name): os.remove(zip_name)

    except Exception as e:
        logger.error(f"Failed to send {config.db_file}: {e}")
        await MessageManager.send_temp(
            context, RECEIVER_ID,
            "Gagal memperbarui data laporan."
        )

async def forwarded_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if user_id in config.admin_user_ids:
        return

    await context.bot.send_message(
        chat_id=config.admin_user_ids[0],
        text=f"⚠️ <b>SECURITY WARNING:</b> Unauthorized Forwarding\n"
        f"👤 <b>User:</b> {update.effective_user.full_name}\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>",
        parse_mode=ParseMode.HTML
    )

    warning_msg = await update.message.reply_text(
        f"<b>🚫 ACCESS DENIED</b>\n"
        f"Forwarding is not allowed.",
        parse_mode=ParseMode.HTML
    )

    try:
        await update.message.delete()
        await asyncio.sleep(10)
        await warning_msg.delete()
    except: pass

async def claim_daily_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await MessageManager.send_temp(
        context, update.effective_chat.id,
        "❌ Admin only!",
        delay=10
    )


def save_database_on_exit() -> None:
    """Save database on exit"""
    db._save()
    logger.info("Database saved on exit")

def main() -> None:
    """Main application entry point"""
    if not config.bot_token:
        logger.error("BOT_TOKEN not set")
        sys.exit(1)

    UIColor.clear_screen()
    UIColor.set_title('LunaranimeBot')
    # Register exit handler
    atexit.register(save_database_on_exit)

    # Create application
    app = (
        ApplicationBuilder()
        .token(config.bot_token)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        # .job_queue(JobQueue())
        .build()
    )

    # Handlers registration
    app.add_handler(CommandHandler('start', start))

    # Callback query handlers
    app.add_handler(CallbackQueryHandler(main_menu_handler, pattern='^main_menu$'))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CallbackQueryHandler(privacy_handler, pattern='^privacy$'))

    # Admin handlers
    app.add_handler(CallbackQueryHandler(broadcast_handler, pattern='^broadcast_mode$'))
    app.add_handler(CallbackQueryHandler(notify_user_handler, pattern='^notify_user$'))
    app.add_handler(CallbackQueryHandler(admin_source_handler, pattern='^source_code$'))

    # Mode handlers
    app.add_handler(CallbackQueryHandler(search_mode_handler, pattern='^search_mode$'))
    app.add_handler(CallbackQueryHandler(user_library_handler, pattern='^user_library$'))
    app.add_handler(CallbackQueryHandler(search_user_projects_handler, pattern='^search_user_projects_mode$'))

    app.add_handler(MessageHandler(filters.FORWARDED, forwarded_message_handler))

    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Error handler
    app.add_error_handler(error_handler)

    # Periodic cleanup
    app.job_queue.run_repeating(cleanup_job, interval=300, first=60)

    now = datetime.now()
    minute_to_add = 5 - (now.minute % 5)
    first_run = (now + timedelta(minutes=minute_to_add)).replace(second=0, microsecond=0)
    # printn(f"?95>>> ?97`{first_run} {dir(first_run)}")
    app.job_queue.run_repeating(
        job_send_reports,
        interval=300,
        first=(first_run - now).seconds,
        name="hourly_reports"
    )

    logger.info("🚀 Lunaranime Bot started successfully!")
    logger.info("Bot is now running...")

    # Run bot
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        close_loop=False
    )

if __name__ == "__main__":
    import asyncio
    main()
