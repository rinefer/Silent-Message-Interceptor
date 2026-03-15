import datetime

from telethon import TelegramClient, events
from telethon.tl.types import PeerUser

from config import api_id, api_hash, session_name, MEDIA_FOLDER, BOT_VERSION, ADMIN_IDS, NOTIFY_CHAT_ID
from models.databases.database import conn, cursor, txt_filepath
from models.admin import is_admin, save_media, save_to_txt, send_notification, register_admin_handlers
from models.pars_invite import register_pars_invite_handlers
from models.poisk       import register_poisk_handlers
from models.game        import register_game_handlers
from models.utils       import register_utils_handlers


message_cache = {}
client = TelegramClient(session_name, api_id, api_hash)


# Cache every incoming private message and download any media
@client.on(events.NewMessage(incoming=True))
async def handle_new_message(event):
    if not isinstance(event.peer_id, PeerUser):
        return

    try:
        chat   = await event.get_chat()
        sender = await event.get_sender()
        if not chat or not sender:
            print(f"[ERROR] handle_new_message: could not resolve chat/sender for msg {event.message.id}")
            return

        media_path, media_type, is_view_once = await save_media(event.message, MEDIA_FOLDER)

        if is_view_once:
            msg_type = " SELF-DESTRUCT"
        elif media_type:
            msg_type = f" {media_type.upper()}"
        else:
            msg_type = " TEXT"

        message_cache[event.message.id] = {
            "chat_id":      chat.id,
            "chat_name":    chat.first_name or "Unknown",
            "sender_id":    sender.id,
            "sender_name":  sender.first_name or "Unknown",
            "text":         event.message.text,
            "date":         event.message.date,
            "media_path":   media_path,
            "media_type":   media_type,
            "is_view_once": is_view_once,
            "message_type": msg_type,
        }

    except Exception as exc:
        print(f"[ERROR] handle_new_message: {exc}")


# Persist a deleted message to DB, text log, and send a notification
@client.on(events.MessageDeleted())
async def handle_deleted_messages(event):
    for msg_id in event.deleted_ids:
        if msg_id not in message_cache:
            continue

        msg = message_cache[msg_id]
        try:
            cursor.execute('''
                INSERT INTO deleted_messages
                    (chat_id, chat_name, sender_id, sender_name, message_text,
                     message_date, deleted_at, media_path, media_type, is_view_once)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                msg["chat_id"], msg["chat_name"],
                msg["sender_id"], msg["sender_name"],
                msg["text"], msg["date"],
                datetime.datetime.now(),
                msg["media_path"], msg["media_type"],
                1 if msg.get("is_view_once") else 0,
            ))
            conn.commit()
            save_to_txt(msg, txt_filepath)
            await send_notification(client, msg)
            fire = "" if msg.get("is_view_once") else ""
            print(f"[INFO] Saved deleted message from {msg['sender_name']} {fire}")

        except Exception as exc:
            print(f"[ERROR] handle_deleted_messages: {exc}")


register_admin_handlers      (client, cursor, conn, txt_filepath)
register_pars_invite_handlers(client)
register_poisk_handlers      (client)
register_game_handlers       (client)
register_utils_handlers      (client)


print("=" * 55)
print("  Bot starting...")
print(f"  Version      : {BOT_VERSION}")
print(f"  Fire support : YES")
print(f"  Admins       : {ADMIN_IDS}")
print(f"  Notifications: {NOTIFY_CHAT_ID if NOTIFY_CHAT_ID else 'disabled'}")
print("=" * 55)

client.start()
client.run_until_disconnected()
