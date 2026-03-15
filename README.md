# Silent-Message-Interceptor
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Telethon](https://img.shields.io/badge/library-Telethon-blue.svg)
![SQLite](https://img.shields.io/badge/database-SQLite-lightgrey.svg)
![Pillow](https://img.shields.io/badge/library-Pillow-yellow.svg)
![Requests](https://img.shields.io/badge/library-Requests-orange.svg)

A multifunctional Telegram userbot built with Python and Telethon. The program intercepts and saves deleted messages, captures self-destruct media before it disappears, parses channel members, runs mini-games, and provides search tools for books, anime, manga, and Wikipedia. All data is stored locally.

## Libraries Used

* **telethon**: Telegram client library for building userbots via the MTProto API.
* **requests**: HTTP requests to external APIs (AniList, Wikipedia, Google Books, TikTok).
* **Pillow (PIL)**: Image processing and EXIF data extraction for GPS location lookup.
* **pytube**: YouTube video downloading.
* **sqlite3**: Built-in Python module for local database storage of deleted messages.
* **csv, os, asyncio, datetime**: Standard library modules for file handling, async execution, and time operations.

## System Requirements

To run this project, you must have a registered Telegram application.

* Get your API credentials: [https://my.telegram.org](https://my.telegram.org)
* Telethon documentation: [https://docs.telethon.dev](https://docs.telethon.dev)

## Project Structure

```
soh_bot/
|-- main.py                  # Entry point, core listeners, module registration
|-- config.py                # API credentials, paths, game state stores
|
|-- models/
|   |-- admin.py             # Deletion logging, /deleted /viewonce /media /stats /ping
|   |-- pars_invite.py       # /pars /parsmsg /invite
|   |-- poisk.py             # /searchbook /wiki /anime /manga
|   |-- game.py              # /slots /blackjack /poker /ttt /rps
|   |-- utils.py             # /help /download /photo_location /msgcopy
|   |
|   |-- databases/
|       |-- database.py      # SQLite connection, schema, datetime adapters
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/soh_bot.git
cd soh_bot
```

### 2. Configure credentials

Open `config.py` and fill in your Telegram API credentials:

```python
api_id   = 12345678        # from my.telegram.org
api_hash = 'your_api_hash'

ADMIN_IDS      = [123456789]     # your numeric Telegram ID
NOTIFY_CHAT_ID = [-100123456789] # chat to receive deletion alerts
```

To find your Telegram ID, start the bot and send `/myid`. Add the returned number to `ADMIN_IDS` and restart.

### 3. Install dependencies

```bash
pip install telethon requests Pillow pytube
```

### 4. Run the bot

```bash
python main.py
```

On first launch Telethon will ask for your phone number and a confirmation code. A session file `sessionka.session` will be created automatically.

## Usage

### General commands

```
/help     — full command reference
/ping     — bot health check and latency
/myid     — your Telegram ID
/admins   — list all admins
```

### Message surveillance (admins only)

```
/deleted           — last 10 deleted messages
/viewonce          — saved self-destruct media
/media             — all saved media files
/stats             — deletion statistics
/delete_text_logs  — delete all text log files
/delete_media      — delete all saved media files
```

### Parsing and invites (admins only)

```
/pars all_uss <link>               — export all channel members to CSV
/parsmsg <link> <user_id> <limit>  — export one user's messages
/invite <channel>                  — bulk-invite users from users.csv
```

### Search

```
/searchbook google|openlib|flibusta <title>  — book search
/wiki <query>                                — Wikipedia article
/anime <title>                               — AniList anime search
/manga <title>                               — AniList manga search
```

### Utilities (admins only)

```
/download <url>   — download video from YouTube or TikTok
/photo_location   — extract GPS coordinates from photo EXIF (reply to a photo)
/msgcopy <link>   — copy a message from a restricted chat
```

### Games

```
/slots             — slot machine
/blackjack         — blackjack (21)
/poker             — 5-card draw poker
/ttt               — tic-tac-toe vs bot
/ttt @username     — tic-tac-toe vs another user
/rps               — rock-paper-scissors
```

## Technical Features

* **Privacy**: All deleted messages and media are stored locally in SQLite and a plain-text log. No data is sent to external servers except for search queries (Wikipedia, AniList, Google Books).
* **Self-destruct media**: The bot intercepts fire messages (self-destruct photos and videos) and saves them before Telegram deletes them.
* **Modular structure**: Each feature group lives in its own module under `models/`. Adding or removing functionality does not affect the rest of the codebase.
* **Fallback search**: Book search automatically falls back from Google Books to Open Library to Flibusta if a source returns no results.
