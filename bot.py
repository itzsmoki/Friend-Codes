import discord
from discord.ext import commands
from discord import app_commands
from discord.utils import get
from datetime import datetime
import time
import asyncio
import re
from psnawp_api import psnawp
from datetime import datetime, timedelta
import pytz
import os
import json
from dotenv import load_dotenv
from discord.ext.commands import has_permissions
import sqlite3
import aiosqlite
import math
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
NPSSO_TOKEN = os.getenv("NPSSO_TOKEN")
SERVER_ID = int(os.getenv("SERVER_ID"))

psnawp_client = psnawp.PSNAWP(NPSSO_TOKEN)


intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True


lock = asyncio.Lock()

GUILD_ID = discord.Object(id=int(SERVER_ID))

italian_tz = pytz.timezone("Europe/Rome")

count = 0

PLATFORM_CHOICES = [
    app_commands.Choice(name="Switch", value="Switch"),
    app_commands.Choice(name="PlayStation", value="PlayStation"),
    app_commands.Choice(name="Steam", value="Steam"),
    app_commands.Choice(name="Epic Games", value="Epic Games"),
]

COLOR_SWITCH = 0xE60012
COLOR_PSN = 0x00358c
COLOR_STEAM = 0x1477A6
COLOR_EPIC = 0x2F2D2E

database_file = 'codes.db'

active_users1 = set()
active_users2 = set()

class Client(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def on_ready(self):
        global count
        async with aiosqlite.connect(f'{database_file}') as conn:
            async with conn.cursor() as db:
                await conn.execute("PRAGMA foreign_keys = ON;")
                await db.execute("SELECT COUNT(*) FROM codes")
                count_row = await db.fetchone()
                count = count_row[0] if count_row else 0
                await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{count} friend codes"))
                logging.info(f"Logged in as {self.user}!")
        try:
            guild = discord.Object(id=SERVER_ID)
            synced = await self.tree.sync(guild=guild)
            logging.info("Slash commands synced.")
            await auto_update()
        except Exception as e:
            logging.error(f'Error syncing commands: {e}')

async def get_platform_name(platform):
    if platform == 'switch':
        return 'Nintendo Switch'
    elif platform == 'psn':
        return 'PlayStation Network'
    elif platform == 'steam':
        return 'Steam'
    elif platform == 'epic':
        return 'Epic Games'

    return platform

async def create_thread(conn, channel_id, platform):
    async with conn.cursor() as db:
        await conn.execute("PRAGMA foreign_keys = ON;")

        channel = client.get_channel(channel_id)
        platform_name = await get_platform_name(platform)
        file = discord.File(f"/home/smoki/restream/static/{platform}.png")
        thread_result = await channel.create_thread(name=f"{platform_name}", file=file)
        thread = thread_result.thread
        thread_id = thread.id
        await db.execute("INSERT INTO threads (channel_id, thread_id, platform) VALUES (?, ?, ?)", (channel_id, thread.id, platform))

        await conn.commit()
        logging.info(f"Thread created for {platform} in channel {channel_id}.")
        return thread_id

async def create_messages(conn, thread, platform, color, chunk_size=100):
    async with conn.cursor() as db:
        await conn.execute("PRAGMA foreign_keys = ON;")

        await db.execute("SELECT users.alias, codes.code FROM users JOIN codes ON users.user_id = codes.user_id WHERE codes.platform = ?", (platform,))
        users_data = await db.fetchall()
        platform_name = await get_platform_name(platform)

        description = f"Use `/add` anywhere in the server to share your friend code\n\n"
        embed = discord.Embed(
            title="",
            color=color,
        )

        embed.set_author(
            name=platform_name,
            icon_url=f"https://vaojin.xyz/static/icons/{platform}-icon.png"
        )

        if not users_data:
            description += "> List is empty!"
            embed.description = description
            message = await thread.send(embed=embed)
            await db.execute("INSERT INTO messages (thread_id, message_id) VALUES (?, ?)", (thread.id, message.id))
            await conn.commit()
            return

        for i in range(0, len(users_data), chunk_size):
            chunk = users_data[i:i + chunk_size]
            for user_alias, code in chunk:
                description += f"**{user_alias}**: `{code}`\n"
            embed.description = description
            message = await thread.send(embed=embed)
            await db.execute("INSERT INTO messages (thread_id, message_id) VALUES (?, ?)", (thread.id, message.id))
            embed = discord.Embed(color=color,)
            description = ""
        await conn.commit()

async def edit_messages(conn, thread, platform, color, chunk_size=100):
    async with conn.cursor() as db:
        await conn.execute("PRAGMA foreign_keys = ON;")

        await db.execute("SELECT message_id FROM messages WHERE thread_id IN (SELECT thread_id FROM threads WHERE thread_id = ? AND platform = ?)", (thread.id, platform))
        messages = await db.fetchall()
        await db.execute("SELECT users.alias, codes.code FROM users JOIN codes ON users.user_id = codes.user_id WHERE codes.platform = ?", (platform,))
        users_data = await db.fetchall()
        groups = math.ceil(len(users_data) / chunk_size)
        platform_name = await get_platform_name(platform)


        if groups == 0:
            if messages:
                await delete_messages(conn, thread, platform)
            await create_messages(conn, thread, platform, color)
            return


        if len(messages) < groups:
            await delete_messages(conn, thread, platform)
            await create_messages(conn, thread, platform, color)
            return
        elif len(messages) > groups:
            excess = len(messages) - groups

            for i in range(len(messages) - 1, len(messages) - excess - 1, -1):
                try:
                    message = await thread.fetch_message(messages[i][0])
                    await message.delete()
                    await db.execute("DELETE FROM messages WHERE message_id = ?", (messages[i][0],))
                except discord.NotFound:
                    pass


        description = f"Use `/add` anywhere in the server to share your friend code\n\n"
        embed = discord.Embed(
            title="",
            color=color,
        )

        embed.set_author(
            name=platform_name,
            icon_url=f"https://vaojin.xyz/static/icons/{platform}-icon.png"
        )

        for i in range(0, len(users_data), chunk_size):
            index = (i // chunk_size)

            chunk = users_data[i:i + chunk_size]
            for user_alias, code in chunk:
                description += f"**{user_alias}**: `{code}`\n"
            embed.description = description
            try:
                message = await thread.fetch_message(messages[index][0])
                await message.edit(embed=embed)
            except discord.NotFound:
                await delete_messages(conn, thread, platform)
                await create_messages(conn, thread, platform, color)
                return

            embed = discord.Embed(
                color=color,
            )
            description = ""

        await conn.commit()

async def delete_messages(conn, thread, platform):
    async with conn.cursor() as db:
        await conn.execute("PRAGMA foreign_keys = ON;")

        await db.execute("SELECT message_id FROM messages WHERE thread_id IN (SELECT thread_id FROM threads WHERE thread_id = ? AND platform = ?)", (thread.id, platform))
        messages = await db.fetchall()
        for (message_id,) in messages:
            try:
                message = await thread.fetch_message(message_id)
                await message.delete()
            except discord.NotFound:
                pass
        await db.execute("DELETE FROM messages WHERE thread_id = ?", (thread.id,))
        await conn.commit()

async def reload(interaction, platform, color):
    async with aiosqlite.connect(f'{database_file}') as conn:
        async with conn.cursor() as db:
            await conn.execute("PRAGMA foreign_keys = ON;")

            await db.execute("SELECT channel_id FROM channels WHERE server_id = ?", (SERVER_ID,))
            channel_id = await db.fetchone()

            if channel_id is None:
                return
                await interaction.followup.send("⚠️ No channel found for this server.", ephemeral=True)
            channel_id = channel_id[0]

            try:
                channel = await client.fetch_channel(channel_id)
                if not isinstance(channel, discord.ForumChannel):
                    raise ValueError("Invalid channel")
            except discord.NotFound:
                await db.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
                await conn.commit()
                logging.info(f"Channel deleted and removed from DB: {channel.id}")
                return
                await interaction.followup.send("⚠️ The specified channel no longer exists on this server.", ephemeral=True)


            await db.execute("SELECT thread_id FROM threads WHERE channel_id = ? AND platform = ?", (channel_id, platform))
            thread_id = await db.fetchone()
            if thread_id is None:
                thread_id = await create_thread(conn, channel_id, platform)
            else:
                thread_id = thread_id[0]
                try:
                    thread = await client.fetch_channel(thread_id)
                    if not isinstance(thread, discord.Thread):
                        raise ValueError("Invalid thread")
                except discord.NotFound:
                    await db.execute("DELETE FROM threads WHERE thread_id = ?", (thread_id,))
                    await conn.commit()
                    thread_id = await create_thread(conn, channel_id, platform)
            thread = await client.fetch_channel(thread_id)
            await edit_messages(conn, thread, platform, color)
            logging.info(f"Reloaded friend codes list for {platform}.")


async def update_aliases():
    async with aiosqlite.connect(f'{database_file}') as conn:
        async with conn.cursor() as db:
            await conn.execute("PRAGMA foreign_keys = ON;")
            await db.execute("SELECT users.user_id FROM users JOIN codes ON users.user_id = codes.user_id")
            users_data = await db.fetchall()
            for (user_id,) in users_data:
                guild = await client.fetch_guild(SERVER_ID)
                user_nickname = ""
                try:
                    member = await guild.fetch_member(user_id)
                    user_nickname = member.nick if member.nick else member.display_name
                except discord.NotFound:
                    member = None

                if member == None:
                    user = await client.fetch_user(user_id)
                    user_nickname = user.display_name
                await db.execute("SELECT alias FROM users WHERE user_id = ?", (user_id,))
                current_alias = await db.fetchone()
                if not current_alias or current_alias[0] != user_nickname:
                    await db.execute("UPDATE users SET alias = ? WHERE user_id = ?", (user_nickname, user_id))
            await conn.commit()
            logging.info("User aliases updated.")

def normalize_switch_friend_code(friend_code):
    friend_code = ''.join(re.findall(r'\d', friend_code))
    if len(friend_code) == 12:
        return f"SW-{friend_code[:4]}-{friend_code[4:8]}-{friend_code[8:]}"
    return None

def normalize_steam_friend_code(friend_code):
    friend_code = ''.join(re.findall(r'\d', friend_code))
    if len(friend_code) <= 12:
        return friend_code
    return None

def normalize_epic_friend_code(username):
    username = username.strip()

    if 3 <= len(username) <= 16:
        if re.fullmatch(r"[a-zA-Z0-9._\-]+( [a-zA-Z0-9._\-]+)*", username):
            return username
    return None

def validate_psn_username(username):
    try:
        user = psnawp_client.user(online_id=username)
        account_id = user.account_id
        user_by_account_id = psnawp_client.user(account_id=account_id)
        if user_by_account_id.online_id.upper() == username.upper():
            return user_by_account_id.online_id
        else:
            return None
    except Exception as e:
        return None

async def add_code(interaction, platform, normalize_func, code, color):
    global count
    async with aiosqlite.connect(f'{database_file}') as conn:
        async with conn.cursor() as db:
            await conn.execute("PRAGMA foreign_keys = ON;")
            normalized_code = normalize_func(code)

            if not normalized_code:
                await interaction.followup.send("🚫 Invalid friend code format or does not exist.", ephemeral=True)
                return

            guild = await client.fetch_guild(SERVER_ID)
            member = await guild.fetch_member(interaction.user.id)
            user_id = f"{interaction.user.id}"
            user_name = f"{interaction.user.name}"
            user_nickname = member.nick if member.nick else interaction.user.display_name

            await db.execute("SELECT * FROM codes WHERE user_id = ? AND platform = ?", (user_id, platform))
            existing_user_code = await db.fetchone()
            if existing_user_code:
                await interaction.followup.send("⚠️ You already have a friend code in the list.", ephemeral=True)
                return

            await db.execute("SELECT * FROM codes WHERE LOWER(code) = ? AND platform = ?", (normalized_code.lower(), platform))
            existing_code = await db.fetchone()
            if existing_code:
                await interaction.followup.send("⚠️ This friend code is already linked to another user.", ephemeral=True)
                return

            await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            existing_user = await db.fetchone()
            if existing_user:
                await db.execute("UPDATE users SET username = ?, alias = ? WHERE user_id = ?", (user_name, user_nickname, user_id))
            else:
                await db.execute("INSERT INTO users (user_id, username, alias) VALUES (?, ?, ?)", (user_id, user_name, user_nickname))

            await db.execute("INSERT INTO codes (user_id, platform, code) VALUES (?, ?, ?)", (user_id, platform, normalized_code))
            await conn.commit()

            logging.info(f"Added friend code for user {user_id} on {platform}: {normalized_code}")
            await interaction.followup.send(f"✅ Your friend code `{normalized_code}` has been added to the list!", ephemeral=True)
            await reload(interaction, platform, color)

            count += 1
            await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{count} friend codes"))

async def remove_friend_code(interaction, platform, color):
    global count
    async with aiosqlite.connect(f'{database_file}') as conn:
        async with conn.cursor() as db:
            await conn.execute("PRAGMA foreign_keys = ON;")
            user_id = f"{interaction.user.id}"

            await db.execute("SELECT * FROM codes WHERE user_id = ? AND platform = ?", (user_id, platform))
            existing_entry = await db.fetchone()
            if not existing_entry:
                await interaction.followup.send("⚠️ You don't have a friend code in the list.", ephemeral=True)
                return

            await db.execute("DELETE FROM codes WHERE platform = ? AND user_id = ?", (platform, user_id))
            await conn.commit()

            logging.info(f"Removed friend code for user {user_id} on {platform}")
            await interaction.followup.send("✅ Your friend code has been removed from the list.", ephemeral=True)

            await reload(interaction, platform, color)

            count -= 1
            await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{count} friend codes"))

client = Client()

@client.event
async def on_guild_channel_delete(channel):
    async with lock:
        async with aiosqlite.connect(f'{database_file}') as conn:
            async with conn.cursor() as db:
                await conn.execute("PRAGMA foreign_keys = ON;")
                await db.execute("DELETE FROM channels WHERE channel_id = ?", (channel.id,))
                await conn.commit()
                logging.info(f"Channel deleted and removed from DB: {channel.id}")

@client.event
async def on_thread_delete(thread):
    async with lock:
        async with aiosqlite.connect(f'{database_file}') as conn:
            async with conn.cursor() as db:
                await conn.execute("PRAGMA foreign_keys = ON;")
                await db.execute("DELETE FROM threads WHERE thread_id = ?", (thread.id,))
                await conn.commit()
                logging.info(f"Thread deleted and removed from DB: {thread.id}")

@client.event
async def on_member_update(before, after):
    if before.nick != after.nick:
        async with lock:
            async with aiosqlite.connect(f'{database_file}') as conn:
                async with conn.cursor() as db:
                    await conn.execute("PRAGMA foreign_keys = ON;")
                    print(f"{before.nick} > {after.nick}")
                    logging.info(f"Member nickname updated: {before.nick} -> {after.nick}")
                    await conn.commit()


@client.tree.command(name="add", description="Add your friend code", guild=GUILD_ID)
@app_commands.describe(platform="Choose a platform")
@app_commands.choices(platform=PLATFORM_CHOICES)
@app_commands.describe(code="Type your friend code")
async def add_platform_code(interaction: discord.Interaction, platform: str, code: str):
    await interaction.response.defer(ephemeral=True)
    user_id = interaction.user.id
    if user_id in active_users1:
        await interaction.followup.send("⚠️ You are already executing a command.", ephemeral=True)
        return
    active_users1.add(user_id)
    async with lock:
        if platform.lower() == "switch":
            try:
                await add_code(interaction, 'switch', normalize_switch_friend_code, code, COLOR_SWITCH)
            except Exception as e:
                logging.error(f"Error adding Switch code: {e}")
                await interaction.followup.send("🚫 An error occurred.", ephemeral=True)
            finally:
                active_users1.discard(user_id)
        elif platform.lower() == "playstation":
            try:
                await add_code(interaction, 'psn', validate_psn_username, code, COLOR_PSN)
            except Exception as e:
                logging.error(f"Error adding PlayStation code: {e}")
                await interaction.followup.send("🚫 An error occurred.", ephemeral=True)
            finally:
                active_users1.discard(user_id)
        elif platform.lower() == "steam":
            try:
                await add_code(interaction, 'steam', normalize_steam_friend_code, code, COLOR_STEAM)
            except Exception as e:
                logging.error(f"Error adding Steam code: {e}")
                await interaction.followup.send("🚫 An error occurred.", ephemeral=True)
            finally:
                active_users1.discard(user_id)
        elif platform.lower() == "epic games":
            try:
                await add_code(interaction, 'epic', normalize_epic_friend_code, code, COLOR_EPIC)
            except Exception as e:
                logging.error(f"Error adding Epic Games code: {e}")
                await interaction.followup.send("🚫 An error occurred.", ephemeral=True)
            finally:
                active_users1.discard(user_id)
        else:
            await interaction.followup.send("🚫 Invalid platform.", ephemeral=True)

@client.tree.command(name="remove", description="Remove your friend code", guild=GUILD_ID)
@app_commands.describe(platform="Choose a platform")
@app_commands.choices(platform=PLATFORM_CHOICES)
async def remove_platform_code(interaction: discord.Interaction, platform: str):
    await interaction.response.defer(ephemeral=True)
    user_id = interaction.user.id
    if user_id in active_users1:
        await interaction.followup.send("⚠️ You are already executing a command.", ephemeral=True)
        return
    active_users1.add(user_id)
    async with lock:
        if platform.lower() == "switch":
            try:
                await remove_friend_code(interaction, 'switch', COLOR_SWITCH)
            except Exception as e:
                logging.error(f"Error removing Switch code: {e}")
                await interaction.followup.send("🚫 An error occurred.", ephemeral=True)
            finally:
                active_users1.discard(user_id)
        elif platform.lower() == "playstation":
            try:
                await remove_friend_code(interaction, 'psn', COLOR_PSN)
            except Exception as e:
                logging.error(f"Error removing PlayStation code: {e}")
                await interaction.followup.send("🚫 An error occurred.", ephemeral=True)
            finally:
                active_users1.discard(user_id)
        elif platform.lower() == "steam":
            try:
                await remove_friend_code(interaction, 'steam', COLOR_STEAM)
            except Exception as e:
                logging.error(f"Error removing Steam code: {e}")
                await interaction.followup.send("🚫 An error occurred.", ephemeral=True)
            finally:
                active_users1.discard(user_id)
        elif platform.lower() == "epic games":
            try:
                await remove_friend_code(interaction, 'epic', COLOR_EPIC)
            except Exception as e:
                logging.error(f"Error removing Epic Games code: {e}")
                await interaction.followup.send("🚫 An error occurred.", ephemeral=True)
            finally:
                active_users1.discard(user_id)
        else:
            await interaction.followup.send("🚫 Invalid platform.", ephemeral=True)
            active_users1.discard(user_id)

@client.tree.command(name="set-channel", description="Set the forum channel where you want the friend codes lists to be", guild=GUILD_ID)
@app_commands.default_permissions(administrator=True)
@app_commands.describe(channel="Select the channel")
async def set_channel(interaction: discord.Interaction, channel: discord.ForumChannel):
    await interaction.response.defer(ephemeral=True)
    user_id = interaction.user.id
    if user_id in active_users1:
        await interaction.followup.send("⚠️ You are already executing a command.", ephemeral=True)
        return
    active_users1.add(user_id)
    async with lock:
        async with aiosqlite.connect(f'{database_file}') as conn:
            async with conn.cursor() as db:
                await conn.execute("PRAGMA foreign_keys = ON;")

                try:
                    if not channel:
                        await interaction.followup.send("🚫 This channel does not exist.", ephemeral=True)
                        return

                    await db.execute("SELECT * FROM channels WHERE server_id = ?", (interaction.guild.id,))
                    row = await db.fetchone()

                    if row:
                        await db.execute("UPDATE channels SET channel_id = ? WHERE server_id = ?", (channel.id, interaction.guild.id))
                    else:
                        await db.execute("INSERT INTO channels (server_id, channel_id) VALUES (?, ?)", (interaction.guild.id, channel.id))

                    await conn.commit()
                    await interaction.followup.send(f"✅ The channel {channel.mention} has been set as the friend codes channel!", ephemeral=True)
                    logging.info(f"Channel set to {channel.id} for guild {interaction.guild.id}.")
                except Exception as e:
                    logging.error(f"Error setting channel: {e}")
                    await interaction.followup.send("🚫 An error occurred.", ephemeral=True)
                finally:
                    active_users1.discard(user_id)

@client.tree.command(name="reload", description="Reload friend codes list", guild=GUILD_ID)
@app_commands.default_permissions(administrator=True)
async def update_lists(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    user_id = interaction.user.id
    if user_id in active_users2:
        await interaction.followup.send("⚠️ You are already executing a command.", ephemeral=True)
        return
    active_users2.add(user_id)
    async with lock:
        async with aiosqlite.connect(f'{database_file}') as conn:
            async with conn.cursor() as db:
                await db.execute("SELECT channel_id FROM channels WHERE server_id = ?", (SERVER_ID,))
                channel_id = await db.fetchone()
                if not channel_id:
                    await interaction.followup.send("🚫 No channel found for this server.", ephemeral=True)
                    return
                try:
                    await update_aliases()
                    await reload(interaction, 'steam', COLOR_STEAM)
                    await reload(interaction, 'epic', COLOR_EPIC)
                    await reload(interaction, 'psn', COLOR_PSN)
                    await reload(interaction, 'switch', COLOR_SWITCH)

                    await interaction.followup.send("✅ Lists successfully updated!", ephemeral=True)
                    logging.info("Friend codes lists reloaded successfully.")
                except Exception as e:
                    logging.error(f"Error reloading lists: {e}")
                    await interaction.followup.send("🚫 An error occurred.", ephemeral=True)
                finally:
                    active_users2.discard(user_id)


@client.tree.command(name="search", description="Get the codes of a specific user in the server", guild=GUILD_ID)
@app_commands.describe(user="Tag the user you want to search")
async def search(interaction: discord.Interaction, user: discord.User):
    await interaction.response.defer(ephemeral=True)
    user_id = interaction.user.id
    if user_id in active_users1:
        await interaction.followup.send("⚠️ You are already executing a command.", ephemeral=True)
        return
    active_users1.add(user_id)
    async with aiosqlite.connect(f'{database_file}') as conn:
        async with conn.cursor() as db:
            try:
                await db.execute("PRAGMA foreign_keys = ON;")

                # Fetch the codes
                await db.execute("SELECT codes.platform, codes.code FROM users JOIN codes ON users.user_id = codes.user_id WHERE codes.user_id = ? ORDER BY codes.platform ASC", (user.id,))
                codes = await db.fetchall()
                if not codes:
                    await interaction.followup.send("🚫 This user has no friend codes.", ephemeral=True)
                    return

                icons = {
                    "switch": ":switch:",
                    "psn": ":psn:",
                    "steam": ":steam:",
                    "epic": ":epic:"
                }

                description = f""
                order = ["switch", "psn", "steam", "epic"]

                for platform in order:
                    found = False
                    for p, code in codes:
                        if p == platform:
                            found = True
                            if platform == "switch":
                                description += f"<{icons[platform]}1335992629615394846> **{code}**\n"
                            elif platform == "psn":
                                description += f"<{icons[platform]}1335992589450743809> **{code}**\n"
                            elif platform == "steam":
                                description += f"<{icons[platform]}1335992726298165439> **{code}**\n"
                            elif platform == "epic":
                                description += f"<{icons[platform]}1335992674779398266> **{code}**\n"
                            break
                    if not found:
                        if platform == "switch":
                            description += f"<{icons[platform]}1329560721545105508> `N/A`\n"
                        elif platform == "psn":
                            description += f"<{icons[platform]}1329560722845466685> `N/A`\n"
                        elif platform == "steam":
                            description += f"<{icons[platform]}1329560719343226962> `N/A`\n"
                        elif platform == "epic":
                            description += f"<{icons[platform]}1329560716352421929> `N/A`"

                embed = discord.Embed(
                    description=description,
                    title = f"{user.display_name}'s Friend Codes",
                    color=0x146ec0
                )
                embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)

                await interaction.followup.send(embed=embed, ephemeral=True)
                logging.info(f"Search command used for user {user.id}.")
            except Exception as e:
                logging.error(f"Error in search command: {e}")
                await interaction.followup.send("🚫 An error occurred.", ephemeral=True)
            finally:
                active_users1.discard(user_id)

@client.tree.command(name="ping", description="Gets current ping to discord", guild=GUILD_ID)
async def ping(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    user_id = interaction.user.id
    if user_id in active_users1:
        await interaction.followup.send("⚠️ You are already executing a command.", ephemeral=True)
        return
    active_users1.add(user_id)

    try:
        latency = round(client.latency * 1000)
        await interaction.followup.send(f"🏓Pong!\nLatency: {latency} ms.", ephemeral=True)
        logging.info("Ping command used.")
    except Exception as e:
        logging.error(f"Error in ping command: {e}")
        await interaction.followup.send("🚫 An error occurred.", ephemeral=True)
    finally:
        active_users1.discard(user_id)

def calculate_sleep_time(target_time_str):
    now = datetime.now(italian_tz)
    target_time = datetime.strptime(target_time_str, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
    target_time = italian_tz.localize(target_time)
    if target_time < now:
        target_time += timedelta(days=1)
    sleep_time = (target_time - now).total_seconds()
    return sleep_time


async def auto_update():
    while True:
        sleep_time = calculate_sleep_time("00:00")
        await asyncio.sleep(sleep_time)
        async with lock:
            async with aiosqlite.connect(f'{database_file}') as conn:
                async with conn.cursor() as db:
                    await db.execute("SELECT channel_id FROM channels WHERE server_id = ?", (SERVER_ID,))
                    channel_id = await db.fetchone()
                    await update_aliases()
                    if channel_id:
                        await reload(None, 'steam', COLOR_STEAM)
                        await reload(None, 'epic', COLOR_EPIC)
                        await reload(None, 'psn', COLOR_PSN)
                        await reload(None, 'switch', COLOR_SWITCH)

                    print(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} Auto update was successfull!')

client.run(BOT_TOKEN)
