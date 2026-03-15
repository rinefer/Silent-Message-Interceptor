import re
import requests
from urllib.parse import quote

from telethon import events

from config import GOOGLE_BOOKS_API, OPEN_LIBRARY_API, FLIBUSTA_SEARCH_URL


# Search Google Books API, fall back to Open Library on failure
async def _search_google_books(query):
    try:
        data = requests.get(
            GOOGLE_BOOKS_API,
            params={'q': query, 'maxResults': 5, 'langRestrict': 'ru'}
        ).json()

        if not data.get('items'):
            return await _search_open_library(query)

        results = []
        for item in data['items'][:5]:
            info    = item.get('volumeInfo', {})
            title   = info.get('title', 'Unknown title')
            authors = ', '.join(info.get('authors', ['Unknown author']))
            year    = info.get('publishedDate', 'Unknown year')[:4]
            desc    = (info.get('description', '')[:100] + '...') if info.get('description') else ''
            link    = info.get('previewLink', '')

            entry = (
                f" <b>{title}</b>\n"
                f" Author: {authors}\n"
                f" Year: {year}\n"
            )
            if desc:
                entry += f" Description: {desc}\n"
            if link:
                entry += f" <a href='{link}'>View on Google Books</a>\n"
            results.append(entry)

        return (
            "\n\n".join(results)
            + "\n\n <a href='https://books.google.com/'>Full search on Google Books</a>"
        )

    except Exception as exc:
        print(f"[ERROR] Google Books: {exc}")
        return await _search_open_library(query)


# Search Open Library API, fall back to Flibusta on failure
async def _search_open_library(query):
    try:
        data = requests.get(
            OPEN_LIBRARY_API,
            params={'q': query, 'limit': 5, 'language': 'rus'}
        ).json()

        if not data.get('docs'):
            return await _search_flibusta(query)

        results = []
        for book in data['docs'][:5]:
            title  = book.get('title', 'Unknown title')
            author = ', '.join(book.get('author_name', ['Unknown author']))
            year   = book.get('first_publish_year', 'Unknown year')
            key    = book.get('key', '')

            entry = (
                f" <b>{title}</b>\n"
                f" Author: {author}\n"
                f" Year: {year}\n"
            )
            if key:
                entry += f" <a href='https://openlibrary.org{key}'>Open Library page</a>\n"
            results.append(entry)

        return (
            "\n\n".join(results)
            + "\n\n <a href='https://openlibrary.org/'>Full search on Open Library</a>"
        )

    except Exception as exc:
        print(f"[ERROR] Open Library: {exc}")
        return await _search_flibusta(query)


# Return a direct Flibusta search link (no scraping needed)
async def _search_flibusta(query):
    url = FLIBUSTA_SEARCH_URL.format(query=quote(query))
    return (
        " Search results on Flibusta:\n"
        f"<a href='{url}'>Click to view results</a>\n\n"
        " Flibusta has a large Russian-language collection. A VPN may be required."
    )


def register_poisk_handlers(client):

    # Search for a book via the chosen source: google, openlib or flibusta
    @client.on(events.NewMessage(pattern='/searchbook'))
    async def handle_search_book(event):
        args = event.message.text.split(maxsplit=2)
        if len(args) < 3:
            await event.reply(
                "ℹ <b>Usage:</b>\n"
                "<code>/searchbook google Title</code> — Google Books\n"
                "<code>/searchbook openlib Title</code> — Open Library\n"
                "<code>/searchbook flibusta Title</code> — Flibusta\n\n"
                "Example: <code>/searchbook google Crime and Punishment</code>",
                parse_mode='HTML'
            )
            return

        source = args[1].lower()
        if source not in ('google', 'openlib', 'flibusta'):
            await event.reply(" Unknown source. Use: <b>google</b>, <b>openlib</b>, or <b>flibusta</b>.",
                              parse_mode='HTML')
            return

        query = args[2].strip()
        if not query:
            await event.reply(" Please provide a book title.")
            return

        await event.reply(f" Searching on <b>{source}</b>...", parse_mode='HTML')

        if source == 'google':
            result = await _search_google_books(query)
        elif source == 'openlib':
            result = await _search_open_library(query)
        else:
            result = await _search_flibusta(query)

        await event.reply(result, parse_mode='HTML')

    # Search the Russian Wikipedia and show related articles
    @client.on(events.NewMessage(pattern='/wiki'))
    async def handle_wiki_search(event):
        args = event.message.text.split(maxsplit=1)
        if len(args) < 2:
            await event.reply(
                "ℹ <b>Usage:</b> <code>/wiki query</code>\n"
                "Example: <code>/wiki Python</code>",
                parse_mode='HTML'
            )
            return

        query = args[1]
        await event.reply(f" Searching Wikipedia for: {query}...")

        WIKI = "https://ru.wikipedia.org/w/api.php"

        try:
            main_data = requests.get(WIKI, params={
                'action': 'query', 'format': 'json',
                'titles': query, 'prop': 'extracts|info',
                'exintro': True, 'explaintext': True,
                'inprop': 'url', 'redirects': True,
            }).json()

            search_data = requests.get(WIKI, params={
                'action': 'query', 'format': 'json',
                'list': 'search', 'srsearch': query, 'srlimit': 6,
            }).json()

            pages = main_data.get('query', {}).get('pages', {})
            if not pages or '-1' in pages:
                await event.reply(" Article not found. Try a different query.")
                return

            page     = next(iter(pages.values()))
            title    = page.get('title', 'Unknown')
            extract  = page.get('extract', 'No description.')
            main_url = page.get('canonicalurl', f"https://ru.wikipedia.org/wiki/{quote(title)}")

            similar = []
            for art in search_data.get('query', {}).get('search', [])[:5]:
                art_title = art.get('title', '')
                art_data  = requests.get(WIKI, params={
                    'action': 'query', 'format': 'json',
                    'titles': art_title, 'prop': 'extracts',
                    'exintro': True, 'explaintext': True, 'redirects': True,
                }).json()
                art_pages = art_data.get('query', {}).get('pages', {})
                if art_pages and '-1' not in art_pages:
                    art_page    = next(iter(art_pages.values()))
                    art_extract = art_page.get('extract', '')
                    art_url     = f"https://ru.wikipedia.org/wiki/{quote(art_title)}"
                    similar.append(
                        f" <b>{art_title}</b>\n"
                        f"{art_extract[:500]}{'...' if len(art_extract) > 500 else ''}\n"
                        f" <a href='{art_url}'>Read</a>"
                    )

            response = (
                f" <b>{title}</b>\n\n"
                f"{extract[:1500]}{'...' if len(extract) > 1500 else ''}\n\n"
                f" <a href='{main_url}'>Read full article</a>\n\n"
                " <b>Related articles:</b>\n\n"
                + "\n\n".join(similar)
            )
            await event.reply(response, parse_mode='HTML')

        except Exception as exc:
            print(f"[ERROR] Wikipedia: {exc}")
            await event.reply(" Search failed. Please try again later.")

    # Search anime via the AniList GraphQL API
    @client.on(events.NewMessage(pattern='/anime'))
    async def search_anime(event):
        query = event.text.replace('/anime', '').strip()
        if not query:
            await event.reply(
                "ℹ <b>Usage:</b> <code>/anime Title</code>\n"
                "Example: <code>/anime Attack on Titan</code>",
                parse_mode='HTML'
            )
            return

        await event.reply(" Searching for anime...")

        gql = """
        query ($search: String, $perPage: Int) {
            Page(page: 1, perPage: $perPage) {
                media(search: $search, type: ANIME, sort: POPULARITY_DESC) {
                    id title { romaji english native }
                    description(asHtml: false)
                    averageScore episodes
                    coverImage { large }
                    siteUrl
                }
            }
        }
        """
        try:
            resp = requests.post(
                'https://graphql.anilist.co',
                json={'query': gql, 'variables': {'search': query, 'perPage': 5}}
            ).json()

            media_list = resp.get('data', {}).get('Page', {}).get('media', [])
            if not media_list:
                await event.reply(" Anime not found. Try a different title.")
                return

            main  = media_list[0]
            title = main['title']['romaji'] or main['title']['english'] or main['title']['native']
            desc  = re.sub(r'<[^>]+>', '', main.get('description') or '')[:300]
            if len(main.get('description') or '') > 300:
                desc += '...'

            msg = (
                f" <b>Top result:</b>\n"
                f" <b>{title}</b>\n"
                f" <b>Score:</b> {main.get('averageScore') or 'N/A'}/100\n"
                f" <b>Episodes:</b> {main.get('episodes') or '?'}\n"
                f" <b>Description:</b>\n{desc or 'No description.'}\n"
                f" <a href='{main['siteUrl']}'>AniList page</a>"
            )

            others = []
            for i, m in enumerate(media_list[1:], 2):
                t = m['title']['romaji'] or m['title']['english'] or m['title']['native']
                others.append(f"{i}. <a href='{m['siteUrl']}'>{t}</a> ({m.get('averageScore') or 'N/A'}/100)")
            if others:
                msg += "\n\n <b>Other results:</b>\n" + "\n".join(others)

            cover = main.get('coverImage', {}).get('large')
            if cover:
                await event.reply(msg, parse_mode='HTML', file=cover)
            else:
                await event.reply(msg, parse_mode='HTML')

        except Exception as exc:
            print(f"[ERROR] Anime search: {exc}")
            await event.reply(" Search failed. Please try again later.")

    # Search manga via the AniList GraphQL API
    @client.on(events.NewMessage(pattern='/manga'))
    async def search_manga(event):
        query = event.text.replace('/manga', '').strip()
        if not query:
            await event.reply(
                "ℹ <b>Usage:</b> <code>/manga Title</code>\n"
                "Example: <code>/manga Berserk</code>",
                parse_mode='HTML'
            )
            return

        await event.reply(" Searching for manga...")

        gql = """
        query ($search: String, $perPage: Int) {
            Page(page: 1, perPage: $perPage) {
                media(search: $search, type: MANGA, sort: POPULARITY_DESC) {
                    id title { romaji english native }
                    description(asHtml: false)
                    averageScore chapters volumes
                    coverImage { large }
                    siteUrl
                }
            }
        }
        """
        try:
            resp = requests.post(
                'https://graphql.anilist.co',
                json={'query': gql, 'variables': {'search': query, 'perPage': 5}}
            ).json()

            media_list = resp.get('data', {}).get('Page', {}).get('media', [])
            if not media_list:
                await event.reply(" Manga not found. Try a different title.")
                return

            main  = media_list[0]
            title = main['title']['romaji'] or main['title']['english'] or main['title']['native']
            desc  = re.sub(r'<[^>]+>', '', main.get('description') or '')[:300]
            if len(main.get('description') or '') > 300:
                desc += '...'

            msg = (
                f" <b>Top result:</b>\n"
                f" <b>{title}</b>\n"
                f" <b>Score:</b> {main.get('averageScore') or 'N/A'}/100\n"
                f" <b>Chapters:</b> {main.get('chapters') or '?'}\n"
                f" <b>Volumes:</b> {main.get('volumes') or '?'}\n"
                f" <b>Description:</b>\n{desc or 'No description.'}\n"
                f" <a href='{main['siteUrl']}'>AniList page</a>"
            )

            others = []
            for i, m in enumerate(media_list[1:], 2):
                t = m['title']['romaji'] or m['title']['english'] or m['title']['native']
                others.append(f"{i}. <a href='{m['siteUrl']}'>{t}</a> ({m.get('averageScore') or 'N/A'}/100)")
            if others:
                msg += "\n\n <b>Other results:</b>\n" + "\n".join(others)

            cover = main.get('coverImage', {}).get('large')
            if cover:
                await event.reply(msg, parse_mode='HTML', file=cover)
            else:
                await event.reply(msg, parse_mode='HTML')

        except Exception as exc:
            print(f"[ERROR] Manga search: {exc}")
            await event.reply(" Search failed. Please try again later.")
