import os
import datetime

from telethon import events, Button

from config import ADMIN_IDS, NOTIFY_CHAT_ID, BOT_VERSION, MEDIA_FOLDER, TXT_LOGS_FOLDER


# Check if the event sender is in ADMIN_IDS
async def is_admin(event):
    try:
        uid = event.sender_id
        print(f"[DEBUG] is_admin check — user_id={uid}, ADMIN_IDS={ADMIN_IDS}")
        return uid in ADMIN_IDS
    except Exception as exc:
        print(f"[ERROR] is_admin: {exc}")
        return False


# Download media from the message, return (path, type, is_view_once)
async def save_media(message, media_folder):
    is_view_once = False

    if message.photo:
        if hasattr(message, 'ttl_seconds') and message.ttl_seconds:
            is_view_once = True
            media_type = 'self_destruct_photo'
        else:
            media_type = 'photo'
        filename = f"photo_{message.id}.jpg"
        path = os.path.join(media_folder, filename)
        await message.download_media(file=path)

    elif message.video:
        if hasattr(message, 'ttl_seconds') and message.ttl_seconds:
            is_view_once = True
            media_type = 'self_destruct_video'
        else:
            media_type = 'video'
        filename = f"video_{message.id}.mp4"
        path = os.path.join(media_folder, filename)
        await message.download_media(file=path)

    elif message.document:
        if hasattr(message, 'ttl_seconds') and message.ttl_seconds:
            is_view_once = True
            media_type = 'self_destruct_document'
        else:
            ext = (message.document.mime_type.split('/')[-1]
                   if message.document.mime_type else 'bin')
            media_type = 'document'
        filename = f"doc_{message.id}.{ext}"
        path = os.path.join(media_folder, filename)
        await message.download_media(file=path)

    else:
        return None, None, False

    return path, media_type, is_view_once


# Append a deleted message record to the daily text log
def save_to_txt(msg_data, filepath):
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write("=== Deleted message ===\n")
        if msg_data.get('is_view_once'):
            f.write(" TYPE: SELF-DESTRUCT (fire)\n")
        f.write(f"Sent at   : {msg_data['date']}\n")
        f.write(f"Deleted at: {datetime.datetime.now()}\n")
        f.write(f"Chat      : {msg_data['chat_name']} (ID: {msg_data['chat_id']})\n")
        f.write(f"Sender    : {msg_data['sender_name']} (ID: {msg_data['sender_id']})\n")
        f.write(f"Text      : {msg_data['text']}\n")
        if msg_data['media_path']:
            mt = msg_data['media_type']
            if msg_data.get('is_view_once'):
                mt = f" {mt} (FIRE)"
            f.write(f"Media     : {mt} → {msg_data['media_path']}\n")
        f.write("\n")


# Send a deletion alert to every chat in NOTIFY_CHAT_ID
async def send_notification(client, msg_data):
    if not NOTIFY_CHAT_ID:
        return

    text = msg_data['text'] or 'No text'
    if len(text) > 500:
        text = text[:500] + "... [message too long]"

    if msg_data.get('is_view_once'):
        notification = (
            " **NEW FIRE (self-destruct media)!**\n\n"
            f" **Sender:** {msg_data['sender_name']} (ID: `{msg_data['sender_id']}`)\n"
            f" **Chat:** {msg_data['chat_name']} (ID: `{msg_data['chat_id']}`)\n"
            f" **Sent:** {msg_data['date'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            f" **Deleted:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
    else:
        notification = (
            " **New deleted message!**\n\n"
            f" **Sender:** {msg_data['sender_name']} (ID: `{msg_data['sender_id']}`)\n"
            f" **Chat:** {msg_data['chat_name']} (ID: `{msg_data['chat_id']}`)\n"
            f" **Sent:** {msg_data['date'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            f" **Deleted:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )

    if text != 'No text':
        notification += f" **Text:**\n`{text}`"

    if msg_data['media_path']:
        tag = " (FIRE)" if msg_data.get('is_view_once') else ""
        notification += f"\n\n **Media:** {msg_data['media_type']} {tag}"

    for chat_id in NOTIFY_CHAT_ID:
        try:
            if msg_data.get('is_view_once'):
                await client.send_message(chat_id, notification, parse_mode='markdown')
            else:
                await client.send_message(
                    chat_id, notification,
                    parse_mode='markdown',
                    file=msg_data['media_path'] if msg_data['media_path'] else None
                )
        except Exception as exc:
            print(f"[ERROR] Notification to {chat_id} failed: {exc}")


def register_admin_handlers(client, cursor, conn, txt_filepath):

    # Show the caller's Telegram ID and admin status
    @client.on(events.NewMessage(pattern='/myid'))
    async def show_my_id(event):
        uid = event.sender_id
        try:
            user = await event.get_sender()
            if user:
                info = (
                    f" **Your info:**\n\n"
                    f" **ID:** `{user.id}`\n"
                    f" **Name:** {user.first_name or 'N/A'}\n"
                    f" **Username:** @{user.username or 'N/A'}\n"
                    f" **Bot:** {'Yes' if user.bot else 'No'}"
                )
            else:
                info = f" **Your ID:** `{uid}`\n\n Could not retrieve full user info."
        except Exception:
            info = f" **Your ID:** `{uid}`"

        await event.reply(
            f"{info}\n\n"
            f" **Admin list:** {ADMIN_IDS}\n\n"
            f" **You {'are' if uid in ADMIN_IDS else 'are NOT'} an admin.**\n\n"
            f" Add `{uid}` to `ADMIN_IDS` in config.py to grant access.",
            parse_mode='markdown'
        )

    # Check bot response latency and database connectivity
    @client.on(events.NewMessage(pattern='/ping'))
    async def handle_ping(event):
        t0 = datetime.datetime.now()
        try:
            cursor.execute('SELECT 1')
            db_status = ' Active'
        except Exception as exc:
            db_status = f' Error: {exc}'

        msg = await event.reply(' Checking connections...')
        latency = (datetime.datetime.now() - t0).total_seconds() * 1000

        await msg.edit(
            f' **Bot status** (v{BOT_VERSION})\n\n'
            f'• **Latency:** `{latency:.2f} ms`\n'
            f'• **Database:** {db_status}\n'
            f'• **Checked at:** `{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}`\n\n'
            f' **Your ID:** `{event.sender_id}`'
        )

    # List all admin IDs and the caller's status
    @client.on(events.NewMessage(pattern='/admins'))
    async def show_admins(event):
        if not await is_admin(event):
            await event.reply(" Access denied. Admin rights required.")
            return
        uid = event.sender_id
        admin_lines = "\n".join(f"•  `{aid}`" for aid in ADMIN_IDS)
        await event.reply(
            f" **Admin list:**\n\n"
            f" Your ID: `{uid}`\n\n"
            f"{admin_lines}\n\n"
            f" You {'are' if uid in ADMIN_IDS else 'are NOT'} an admin.",
            parse_mode='markdown'
        )

    # Show the 10 most recently deleted messages from the DB
    @client.on(events.NewMessage(pattern='/deleted'))
    async def show_deleted(event):
        if not await is_admin(event):
            uid = event.sender_id
            await event.reply(
                f" Access denied.\n\n"
                f" Your ID: `{uid}`\n Admins: {ADMIN_IDS}",
                parse_mode='markdown'
            )
            return
        try:
            cursor.execute('''
                SELECT chat_name, sender_name, message_text,
                       deleted_at, media_type, media_path, is_view_once
                FROM deleted_messages
                ORDER BY deleted_at DESC
                LIMIT 10
            ''')
            rows = cursor.fetchall()
            if not rows:
                await event.reply(" No deleted messages saved yet.")
                return

            response = " **Last 10 deleted messages:**\n\n"
            for i, (chat, sender, text, deleted_at, mtype, mpath, vo) in enumerate(rows, 1):
                fire = " " if vo else ""
                media_info = ""
                if mtype:
                    media_info = f" [{mtype}]"
                    if mpath and os.path.exists(mpath):
                        media_info += " (file saved)"
                response += (
                    f"{i}. {fire} {sender} (chat: {chat})\n"
                    f"    {deleted_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"    {text if text else media_info}\n\n"
                )
            await event.reply(response)
        except Exception as exc:
            await event.reply(f" Error: {exc}")

    # Show saved self-destruct (fire) media with inline buttons
    @client.on(events.NewMessage(pattern='/viewonce'))
    async def show_view_once(event):
        if not await is_admin(event):
            await event.reply(" Access denied. Admin rights required.")
            return
        try:
            cursor.execute('''
                SELECT chat_name, sender_name, message_text,
                       deleted_at, media_type, media_path
                FROM deleted_messages
                WHERE media_type LIKE '%self_destruct%' OR is_view_once = 1
                ORDER BY deleted_at DESC
                LIMIT 20
            ''')
            rows = cursor.fetchall()
            if not rows:
                await event.reply(" No saved fire (self-destruct) media found.")
                return

            response = " **Saved self-destruct media:**\n\n"
            for i, (chat, sender, text, deleted_at, mtype, _) in enumerate(rows, 1):
                clean_type = mtype.replace('self_destruct_', '').upper()
                response += (
                    f"{i}.  **{sender}** → {chat}\n"
                    f"    {deleted_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"    Type: {clean_type}\n"
                )
                if text and text != 'No text':
                    response += f"    {text[:50]}...\n"
                response += "\n"

            await event.reply(response, parse_mode='markdown')

            if rows:
                buttons = [
                    [Button.inline(f" Show #{i+1}", f"show_viewonce_{i}")]
                    for i in range(min(5, len(rows)))
                ]
                await event.reply("Select a fire media to retrieve:", buttons=buttons)

        except Exception as exc:
            await event.reply(f" Error: {str(exc)}")

    # Send the selected fire media back to the admin
    @client.on(events.CallbackQuery(pattern=b'show_viewonce_'))
    async def show_specific_view_once(event):
        if not await is_admin(event):
            await event.answer("Access denied!", alert=True)
            return
        try:
            index = int(event.data.decode().split('_')[-1])
            cursor.execute('''
                SELECT sender_name, message_text, media_type, media_path
                FROM deleted_messages
                WHERE media_type LIKE '%self_destruct%' OR is_view_once = 1
                ORDER BY deleted_at DESC
                LIMIT 1 OFFSET ?
            ''', (index,))
            row = cursor.fetchone()
            if not row:
                await event.answer("Media not found!", alert=True)
                return

            sender, text, mtype, mpath = row
            if not os.path.exists(mpath):
                await event.answer("File missing on disk!", alert=True)
                return

            caption = (
                f" **SAVED FIRE MEDIA**\n"
                f" From: {sender}\n"
                f" Text: {text or 'No text'}"
            )
            send_kwargs = dict(caption=caption, parse_mode='markdown', reply_to=event.message_id)
            if 'photo' in mtype:
                await event.client.send_file(event.chat_id, mpath, **send_kwargs)
            elif 'video' in mtype:
                await event.client.send_file(event.chat_id, mpath, supports_streaming=True, **send_kwargs)
            else:
                await event.client.send_file(event.chat_id, mpath, force_document=True, **send_kwargs)
            await event.answer(" Media sent!")

        except Exception as exc:
            await event.answer(f"Error: {str(exc)}", alert=True)

    # List saved media files and resend the first 5
    @client.on(events.NewMessage(pattern='/media'))
    async def show_media(event):
        if not await is_admin(event):
            await event.reply(" Access denied. Admin rights required.")
            return
        try:
            cursor.execute('''
                SELECT sender_name, message_text, media_type, media_path, is_view_once
                FROM deleted_messages
                WHERE media_type IS NOT NULL
                ORDER BY deleted_at DESC
                LIMIT 15
            ''')
            rows = cursor.fetchall()
            if not rows:
                await event.reply(" No media saved yet.")
                return

            response = " **Saved media files:**\n\n"
            for i, (sender, text, mtype, mpath, vo) in enumerate(rows, 1):
                fire = " " if vo else ""
                response += f"{i}. {fire} {sender}\n    Type: {mtype}\n"
                if text and text != 'No text':
                    response += f"    {text[:50]}...\n"
                response += "\n"

            await event.reply(response, parse_mode='markdown')

            for _, _, mtype, mpath, _ in rows[:5]:
                if mpath and os.path.exists(mpath):
                    try:
                        if 'photo' in mtype:
                            await event.reply(file=mpath)
                        elif 'video' in mtype:
                            await event.reply(file=mpath, supports_streaming=True)
                        else:
                            await event.reply(file=mpath, force_document=True)
                    except Exception as exc:
                        print(f"[ERROR] Resending media: {exc}")

        except Exception as exc:
            await event.reply(f" Error: {exc}")

    # Show aggregate deletion stats and top senders
    @client.on(events.NewMessage(pattern='/stats'))
    async def show_stats(event):
        if not await is_admin(event):
            await event.reply(" Access denied. Admin rights required.")
            return
        try:
            cursor.execute('''
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN media_type IS NULL THEN 1 ELSE 0 END) AS text_only,
                    SUM(CASE WHEN media_type IN ('photo','self_destruct_photo') THEN 1 ELSE 0 END) AS photos,
                    SUM(CASE WHEN media_type IN ('video','self_destruct_video') THEN 1 ELSE 0 END) AS videos,
                    SUM(CASE WHEN media_type IN ('document','self_destruct_document') THEN 1 ELSE 0 END) AS docs,
                    SUM(CASE WHEN is_view_once = 1 OR media_type LIKE '%self_destruct%' THEN 1 ELSE 0 END) AS fires
                FROM deleted_messages
            ''')
            totals = cursor.fetchone()

            cursor.execute('''
                SELECT sender_id, sender_name,
                       COUNT(*) AS cnt,
                       SUM(CASE WHEN is_view_once = 1 OR media_type LIKE '%self_destruct%'
                                THEN 1 ELSE 0 END) AS fire_cnt
                FROM deleted_messages
                GROUP BY sender_id
                ORDER BY cnt DESC
                LIMIT 5
            ''')
            top = cursor.fetchall()

            response = (
                " **Overall statistics:**\n"
                f"• Total messages : {totals[0]}\n"
                f"• Text only      : {totals[1]}\n"
                f"• Photos         : {totals[2]}\n"
                f"• Videos         : {totals[3]}\n"
                f"• Documents      : {totals[4]}\n"
                f"•  Fire media  : {totals[5]}\n\n"
                " **Top senders:**\n"
            )
            for i, (uid, uname, cnt, fire_cnt) in enumerate(top, 1):
                fire_info = f" (: {fire_cnt})" if fire_cnt > 0 else ""
                response += f"{i}. {uname} (`{uid}`) — **{cnt}** deletions{fire_info}\n\n"

            await event.reply(response, parse_mode='markdown')
        except Exception as exc:
            await event.reply(f" Error: {str(exc)}")

    # Delete all plain-text deletion log files
    @client.on(events.NewMessage(pattern='/delete_text_logs'))
    async def delete_text_logs(event):
        if not await is_admin(event):
            await event.reply(" Access denied. Admin rights required.")
            return
        try:
            count = 0
            for fname in os.listdir(TXT_LOGS_FOLDER):
                if fname.startswith("deleted_messages_"):
                    fpath = os.path.join(TXT_LOGS_FOLDER, fname)
                    if os.path.isfile(fpath):
                        os.unlink(fpath)
                        count += 1
            await event.reply(f" Deleted {count} text log file(s).")
        except Exception as exc:
            await event.reply(f" Error: {str(exc)}")

    # Delete all files in the media folder
    @client.on(events.NewMessage(pattern='/delete_media'))
    async def delete_media_cmd(event):
        if not await is_admin(event):
            await event.reply(" Access denied. Admin rights required.")
            return
        try:
            count = 0
            for fname in os.listdir(MEDIA_FOLDER):
                fpath = os.path.join(MEDIA_FOLDER, fname)
                if os.path.isfile(fpath):
                    os.unlink(fpath)
                    count += 1
            await event.reply(f" Deleted {count} media file(s).")
        except Exception as exc:
            await event.reply(f" Error: {str(exc)}")
