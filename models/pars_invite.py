import os
import csv
import datetime
import asyncio
import random

from telethon import events, types
from telethon.tl.types import InputPeerUser, InputPeerChannel
from telethon.tl.functions.channels import InviteToChannelRequest

from config import ADMIN_IDS, TXT_LOGS_FOLDER
from models.admin import is_admin


def register_pars_invite_handlers(client):

    # Export all channel/group participants to CSV
    @client.on(events.NewMessage(pattern='/pars'))
    async def handle_parse_users(event):
        if not await is_admin(event):
            await event.reply(" Access denied. Admin rights required.")
            return

        args = event.message.text.split(maxsplit=2)
        if len(args) < 2 or args[1].lower() != 'all_uss':
            await event.reply(
                "ℹ <b>Usage:</b>\n"
                "<code>/pars all_uss username_or_link</code>\n\n"
                "Examples:\n"
                "<code>/pars all_uss @my_channel</code>\n"
                "<code>/pars all_uss https://t.me/my_channel</code>",
                parse_mode='HTML'
            )
            return

        target = args[2] if len(args) > 2 else ''
        if not target:
            await event.reply(" Please specify a username or link.")
            return

        try:
            await event.reply(" Starting user collection...")

            try:
                entity = await client.get_entity(target)
            except ValueError:
                await event.reply(" Could not find the specified chat/channel.")
                return

            if not isinstance(entity, (types.Channel, types.Chat)):
                await event.reply(" The target is not a chat or channel.")
                return

            participants = await client.get_participants(entity, aggressive=True)
            if not participants:
                await event.reply(" Could not retrieve participants or the chat is empty.")
                return

            ts       = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"parsed_users_{entity.id}_{ts}.csv"
            filepath = os.path.join(TXT_LOGS_FOLDER, filename)

            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'access_hash', 'first_name', 'last_name',
                                 'username', 'phone', 'bot', 'banned', 'admin'])
                for user in participants:
                    writer.writerow([
                        user.id,
                        user.access_hash,
                        user.first_name or '',
                        user.last_name  or '',
                        user.username   or '',
                        user.phone      or '',
                        'Yes' if user.bot else 'No',
                        'Yes' if (hasattr(user, 'left') and user.left) else 'No',
                        'Yes' if (hasattr(user, 'admin_rights') and user.admin_rights) else 'No',
                    ])

            await event.reply(
                f" Collected data for <b>{len(participants)}</b> users.\n"
                f" CSV saved as: <code>{filename}</code>",
                parse_mode='HTML',
                file=filepath
            )

        except Exception as exc:
            await event.reply(f" Parse error: {str(exc)}")

    # Export messages of a specific user from a chat
    @client.on(events.NewMessage(pattern='/parsmsg'))
    async def handle_parse_messages(event):
        if not await is_admin(event):
            await event.reply(" Access denied. Admin rights required.")
            return

        args = event.message.text.split(maxsplit=3)
        if len(args) < 4:
            await event.reply(
                "ℹ <b>Usage:</b>\n"
                "<code>/parsmsg chat_link user_id limit</code>\n\n"
                "Example:\n"
                "<code>/parsmsg @my_channel 123456789 100</code>",
                parse_mode='HTML'
            )
            return

        target  = args[1]
        user_id = int(args[2])
        limit   = min(int(args[3]), 1000) if len(args) > 3 else 100

        try:
            await event.reply(f" Collecting messages for user {user_id}...")

            entity = await client.get_entity(target)
            user   = await client.get_entity(user_id)

            header = (
                f"User info:\n"
                f"  ID          : {user.id}\n"
                f"  Access hash : {user.access_hash}\n"
                f"  First name  : {user.first_name}\n"
                f"  Last name   : {user.last_name or 'N/A'}\n"
                f"  Username    : @{user.username or 'N/A'}\n"
                f"  Phone       : {user.phone or 'N/A'}\n\n"
                f"Messages in {entity.title}:\n"
                + "=" * 50 + "\n\n"
            )

            ts       = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"parsed_msgs_{entity.id}_{user_id}_{ts}.txt"
            filepath = os.path.join(TXT_LOGS_FOLDER, filename)

            count = 0
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(header)
                async for msg in client.iter_messages(entity, from_user=user, limit=limit):
                    count += 1
                    msg_date = msg.date.strftime('%Y-%m-%d %H:%M:%S')
                    msg_text = msg.text or "[Media]"
                    if msg.media:
                        mtype = (
                            "Photo"    if isinstance(msg.media, types.MessageMediaPhoto)
                            else "Document" if isinstance(msg.media, types.MessageMediaDocument)
                            else "Other"
                        )
                        msg_text += f" ({mtype})"
                    f.write(f" {msg_date}\n {msg_text}\n" + "=" * 50 + "\n\n")

            await event.reply(
                f" Collected <b>{count}</b> messages.\n"
                f" Access hash: <code>{user.access_hash}</code>\n"
                f" File: <code>{filename}</code>",
                parse_mode='HTML',
                file=filepath
            )

        except Exception as exc:
            await event.reply(f" Parse error: {str(exc)}")

    # Bulk-invite users from users.csv into a target channel
    @client.on(events.NewMessage(pattern='/invite'))
    async def handle_invite(event):
        if not await is_admin(event):
            await event.reply(" Access denied. Admin rights required.")
            return

        args = event.text.split(maxsplit=1)
        if len(args) < 2:
            await event.reply(
                "ℹ Usage: `/invite @channel`  or  `/invite -100123456789`",
                parse_mode='markdown'
            )
            return

        try:
            target_chat = await client.get_entity(args[1].strip())
            if not isinstance(target_chat, (types.Channel, types.Chat)):
                await event.reply(" That is not a chat or channel.")
                return

            me       = await client.get_me()
            my_perms = await client.get_permissions(target_chat.id, me)
            if not my_perms.invite_users:
                await event.reply(" The account has no invite permission in that chat!")
                return

            if not os.path.exists('users.csv'):
                await event.reply(" users.csv not found in the working directory!")
                return

            users = []
            with open('users.csv', 'r', encoding='utf-8') as f:
                for row in csv.reader(f):
                    if row and row[0].isdigit():
                        users.append({
                            'id':          int(row[0]),
                            'access_hash': int(row[1]) if len(row) > 1 and row[1].lstrip('-').isdigit() else 0,
                            'name':        row[2] if len(row) > 2 else str(row[0]),
                        })

            if not users:
                await event.reply(" No valid users found in users.csv.")
                return

            progress_msg  = await event.reply(f" Starting invite for {len(users)} users...")
            success, failed = 0, []
            target_entity = InputPeerChannel(target_chat.id, target_chat.access_hash)

            for user in users:
                try:
                    user_entity = InputPeerUser(user['id'], user['access_hash'])
                    await client(InviteToChannelRequest(channel=target_entity, users=[user_entity]))
                    success += 1
                    if success % 10 == 0:
                        await progress_msg.edit(
                            f" Added: {success} | Errors: {len(failed)}\n"
                            f"Progress: {success + len(failed)}/{len(users)}"
                        )
                    await asyncio.sleep(random.randint(10, 30))
                except Exception as exc:
                    failed.append(f"{user['id']}: {str(exc)}")

            report = (
                f" Invite report for **{target_chat.title}**:\n"
                f" Success : {success}\n"
                f" Errors  : {len(failed)}\n"
            )
            if failed:
                report += "\n Sample errors:\n" + "\n".join(failed[:3])
                log_file = f"invite_errors_{target_chat.id}.txt"
                log_path = os.path.join(TXT_LOGS_FOLDER, log_file)
                with open(log_path, 'w', encoding='utf-8') as f:
                    f.write("\n".join(failed))
                report += f"\n\n Full error log saved: {log_file}"

            await progress_msg.edit(report)

        except Exception as exc:
            await event.reply(f" Critical error: {str(exc)}")
