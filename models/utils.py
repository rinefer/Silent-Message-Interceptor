import os
import io
import asyncio
import datetime
import requests

from telethon import events, Button, types
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

from config import MEDIA_FOLDER
from models.admin import is_admin


def register_utils_handlers(client):

    # Send the full command reference to the caller
    @client.on(events.NewMessage(pattern='/help'))
    async def show_help(event):
        help_text = """
 <b>Available commands:</b>

 <b>General:</b>
<code>/help</code> — Show this message
<code>/ping</code> — Bot health check
<code>/myid</code> — Your Telegram ID
<code>/admins</code> — List admins

 <b>Parsing &amp; invites:</b>
<code>/pars all_uss &lt;link&gt;</code> — Export all channel members to CSV
<code>/parsmsg &lt;link&gt; &lt;user_id&gt; &lt;limit&gt;</code> — Export one user's messages
<code>/invite &lt;channel&gt;</code> — Bulk-invite from users.csv

 <b>Data lookup:</b>
<code>/photo_location</code> — Extract GPS from photo EXIF (reply to a photo)

 <b>Downloaders:</b>
<code>/download &lt;url&gt;</code> — Download from YouTube or TikTok

 <b>Search:</b>
<code>/searchbook google|openlib|flibusta &lt;title&gt;</code> — Book search
<code>/wiki &lt;query&gt;</code> — Wikipedia
<code>/anime &lt;title&gt;</code> — AniList anime
<code>/manga &lt;title&gt;</code> — AniList manga

 <b>Games:</b>
<code>/slots</code> — Slot machine
<code>/blackjack</code> — Blackjack (21)
<code>/poker</code> — 5-card draw poker
<code>/ttt</code> — Tic-tac-toe vs bot
<code>/ttt @username</code> — Tic-tac-toe vs user
<code>/rps</code> — Rock-paper-scissors

 <b>Message surveillance (admins only):</b>
<code>/deleted</code> — Last 10 deleted messages
<code>/viewonce</code> — Saved fire / self-destruct media
<code>/media</code> — All saved media files
<code>/stats</code> — Deletion statistics

 <b>Cleanup (admins only):</b>
<code>/delete_text_logs</code> — Delete all text log files
<code>/delete_media</code> — Delete all saved media files

 <b>Copy from restricted chats (admins only):</b>
<code>/msgcopy &lt;https://t.me/channel/123&gt;</code> — Copy a message by link
"""
        await event.reply(help_text, parse_mode='HTML')

    # Download a video from YouTube or TikTok with a progress bar
    @client.on(events.NewMessage(pattern='/download'))
    async def handle_download(event):
        from pytube import YouTube

        args = event.message.text.split(maxsplit=1)
        if len(args) < 2:
            await event.reply(
                "ℹ <b>Usage:</b>\n"
                "<code>/download url</code>\n\n"
                "Examples:\n"
                "<code>/download https://youtu.be/example</code>\n"
                "<code>/download https://tiktok.com/@user/video/123</code>",
                parse_mode='HTML'
            )
            return

        url           = args[1].strip()
        last_progress = [-1]
        progress_msg  = await event.reply("⏳ Preparing download...\n\n0% — []")

        def _bar(pct):
            filled = min(int(pct / 25) + 1, 4)
            return f"{pct}% — [{'' * filled}{'  ' * (4 - filled)}]"

        async def _update(pct):
            if pct != last_progress[0]:
                try:
                    await progress_msg.edit(f"⏳ Downloading...\n\n{_bar(pct)}")
                    last_progress[0] = pct
                except Exception as exc:
                    print(f"[WARN] Progress update failed: {exc}")

        try:
            if "youtube.com" in url or "youtu.be" in url:
                def _yt_progress(stream, chunk, bytes_remaining):
                    pct = min(int(((stream.filesize - bytes_remaining) / stream.filesize) * 100), 100)
                    asyncio.create_task(_update(pct))

                yt     = YouTube(url, on_progress_callback=_yt_progress)
                stream = (yt.streams
                          .filter(progressive=True, file_extension='mp4')
                          .order_by('resolution').desc().first())

                if not stream:
                    await progress_msg.edit(" No suitable YouTube stream found.")
                    return

                fname = f"yt_{yt.video_id}.mp4"
                fpath = os.path.join(MEDIA_FOLDER, fname)
                loop  = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, lambda: stream.download(output_path=MEDIA_FOLDER, filename=fname)
                )
                await progress_msg.edit(" Download complete!")
                await asyncio.sleep(0.5)

                await event.reply(
                    f" <b>YouTube video downloaded!</b>\n"
                    f" <b>Title:</b> {yt.title}\n"
                    f" <b>Size:</b> {stream.filesize // (1024 * 1024)} MB\n"
                    f"⏱ <b>Duration:</b> {yt.length // 60}:{yt.length % 60:02d}\n"
                    f" <b>Format:</b> MP4",
                    file=fpath, parse_mode='HTML'
                )

            elif "tiktok.com" in url:
                data = requests.get(f"https://tikwm.com/api?url={url}").json()
                if not data.get("data"):
                    await progress_msg.edit(" Could not fetch TikTok video.")
                    return

                video_url = data["data"]["play"]
                fname     = f"tt_{int(datetime.datetime.now().timestamp())}.mp4"
                fpath     = os.path.join(MEDIA_FOLDER, fname)

                with requests.get(video_url, stream=True) as r:
                    r.raise_for_status()
                    total      = int(r.headers.get('content-length', 0))
                    downloaded = 0
                    with open(fpath, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total:
                                    await _update(min(int(downloaded / total * 100), 100))

                await progress_msg.edit(" Download complete!")
                await asyncio.sleep(0.5)

                duration = data["data"].get("duration", 0)
                size_mb  = os.path.getsize(fpath) / (1024 * 1024)

                await event.reply(
                    f" <b>TikTok video downloaded!</b>\n"
                    f" <b>Size:</b> {size_mb:.1f} MB\n"
                    f"⏱ <b>Duration:</b> {duration // 60}:{duration % 60:02d}\n"
                    f" <b>Format:</b> MP4",
                    file=fpath, parse_mode='HTML'
                )

            else:
                await progress_msg.edit(" Only YouTube and TikTok links are supported.")

        except Exception as exc:
            print(f"[ERROR] Download: {exc}")
            await progress_msg.edit(f" Error: {exc}")

    # Extract GPS coordinates from photo EXIF and return address + map links
    @client.on(events.NewMessage(pattern='/photo_location'))
    async def handle_photo_location(event):
        if not await is_admin(event):
            await event.reply(" Access denied. Admin rights required.")
            return

        reply = await event.get_reply_message()
        if not reply or not reply.media:
            await event.reply("ℹ Reply to a photo file with this command.")
            return

        try:
            photo_bytes = await reply.download_media(bytes)
            image = Image.open(io.BytesIO(photo_bytes))
            exif  = getattr(image, "_getexif", lambda: None)()

            if not exif:
                await event.reply(
                    " No EXIF data found.\n"
                    "Send the photo *as a file* (uncompressed) to preserve GPS coordinates.",
                    parse_mode="markdown"
                )
                return

            gps_tag_id = next((k for k, v in TAGS.items() if v == "GPSInfo"), None)
            gps_raw    = exif.get(gps_tag_id) if gps_tag_id else None
            gps        = {}
            if gps_raw:
                for k, v in gps_raw.items():
                    gps[GPSTAGS.get(k, k)] = v

            if not gps or "GPSLatitude" not in gps or "GPSLongitude" not in gps:
                await event.reply(
                    " No GPS coordinates in EXIF.\n"
                    "Send the photo *as a file* (uncompressed) and try again.",
                    parse_mode="markdown"
                )
                return

            def _to_float(x):
                try:
                    return float(x)
                except Exception:
                    try:
                        num, den = x
                        return num / den
                    except Exception:
                        return float(x)

            def dms_to_deg(dms):
                d, m, s = dms
                return _to_float(d) + _to_float(m) / 60.0 + _to_float(s) / 3600.0

            lat = dms_to_deg(gps["GPSLatitude"])
            lon = dms_to_deg(gps["GPSLongitude"])

            lat_ref = gps.get("GPSLatitudeRef")
            lon_ref = gps.get("GPSLongitudeRef")
            if isinstance(lat_ref, bytes): lat_ref = lat_ref.decode(errors="ignore")
            if isinstance(lon_ref, bytes): lon_ref = lon_ref.decode(errors="ignore")
            if lat_ref and lat_ref.upper() == "S": lat = -lat
            if lon_ref and lon_ref.upper() == "W": lon = -lon

            geo = requests.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "jsonv2"},
                headers={"User-Agent": "SohBot/1.0 (photo_location)"}
            ).json()

            address = geo.get("display_name", "Address not determined")
            gmaps   = f"https://maps.google.com/?q={lat},{lon}"
            osm     = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}"

            await event.reply(
                " <b>Photo location</b>\n"
                f"• Latitude : <code>{lat:.6f}</code>\n"
                f"• Longitude: <code>{lon:.6f}</code>\n"
                f"• Address  : <code>{address}</code>\n\n"
                f" <a href='{gmaps}'>Google Maps</a> | <a href='{osm}'>OpenStreetMap</a>",
                parse_mode="HTML", link_preview=False
            )

        except Exception as exc:
            await event.reply(f" Processing error: <code>{exc}</code>", parse_mode="HTML")

    # Copy a message from a restricted chat by link and forward it with a source button
    @client.on(events.NewMessage(pattern='/msgcopy'))
    async def handle_msg_copy(event):
        if not await is_admin(event):
            await event.reply(" Access denied. Admin rights required.")
            return

        args = event.message.text.split(maxsplit=1)
        if len(args) < 2:
            await event.reply(
                "ℹ <b>Usage:</b>\n"
                "<code>/msgcopy https://t.me/channel/123</code>",
                parse_mode='HTML'
            )
            return

        try:
            await event.delete()

            url = args[1].strip()
            if not url.startswith('https://t.me/'):
                reply = await event.respond(" Invalid link. Format: https://t.me/channel/123")
                await asyncio.sleep(5)
                await reply.delete()
                return

            parts = url.split('/')
            if len(parts) < 4 or not parts[-1].isdigit():
                reply = await event.respond(" Bad link format. The message ID must be the last segment.")
                await asyncio.sleep(5)
                await reply.delete()
                return

            chat_ref   = parts[3] if len(parts) == 5 else '/'.join(parts[3:-1])
            msg_id     = int(parts[-1])

            try:
                source_msg = await client.get_messages(chat_ref, ids=msg_id)
            except ValueError:
                reply = await event.respond(" Chat/channel not found or not accessible.")
                await asyncio.sleep(5)
                await reply.delete()
                return

            if not source_msg:
                reply = await event.respond(" Message not found.")
                await asyncio.sleep(5)
                await reply.delete()
                return

            source_link = f"\n\n [Source]({url})"
            text        = (f"{source_msg.text}{source_link}"
                           if source_msg.text else source_link)
            buttons     = [[Button.url(" Go to original", url=url)]]

            if source_msg.media:
                temp_file = await _download_temp_media(source_msg)
                if not temp_file:
                    await event.respond(" Could not process the media file.")
                    return
                try:
                    is_photo = isinstance(source_msg.media, types.MessageMediaPhoto)
                    await event.client.send_file(
                        event.chat_id, temp_file,
                        caption=text, buttons=buttons,
                        supports_streaming=not is_photo,
                        parse_mode='markdown'
                    )
                finally:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
            else:
                await event.client.send_message(
                    event.chat_id, text,
                    buttons=buttons, parse_mode='markdown', link_preview=False
                )

        except Exception as exc:
            err = await event.respond(f" Error: {exc}")
            await asyncio.sleep(5)
            await err.delete()

    # Download media to a temp folder and return the file path
    async def _download_temp_media(message):
        try:
            temp_dir = os.path.join(MEDIA_FOLDER, 'temp')
            os.makedirs(temp_dir, exist_ok=True)

            if message.photo:
                ext = 'jpg'
            elif message.video:
                ext = 'mp4'
            elif message.document:
                ext = (message.document.mime_type.split('/')[-1]
                       if message.document.mime_type else 'bin')
            else:
                return None

            fpath = os.path.join(temp_dir, f"copy_{message.id}.{ext}")
            await message.download_media(file=fpath)
            return fpath

        except Exception as exc:
            print(f"[ERROR] Temp media download: {exc}")
            return None
