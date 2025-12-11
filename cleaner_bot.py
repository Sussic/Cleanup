import os
import asyncio
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

# === CONFIG ===
TOKEN = os.getenv("BOT_TOKEN")          # read from env (do NOT paste the token here)

# List of channels to clean
CHANNEL_IDS = [
    1439052099794108470,
    1447026793386082527,
    1447025718725967882
]

CLEAN_OLDER_THAN_DAYS = 7              # delete messages older than 7 days
CHECK_EVERY_MINUTES = 60               # how often to run the cleanup

if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set")

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    if not cleanup_old_messages.is_running():
        cleanup_old_messages.start()
    print("Cleanup loop started.")


async def _cleanup_single_channel(channel: discord.TextChannel, now: datetime) -> int:
    """
    Cleans a single channel and returns the number of deleted messages.
    """
    cutoff_older_than = now - timedelta(days=CLEAN_OLDER_THAN_DAYS)
    bulk_limit_age = timedelta(days=14)  # Discord bulk delete limit

    print(f"[{datetime.now()}] Cleaning channel {channel.id}...")

    to_bulk_delete = []
    deleted_count = 0

    async for message in channel.history(limit=None, before=cutoff_older_than, oldest_first=False):
        age = now - message.created_at

        # Only touch messages older than CLEAN_OLDER_THAN_DAYS
        if age < timedelta(days=CLEAN_OLDER_THAN_DAYS):
            continue

        # If newer than 14 days -> we can bulk delete
        if age <= bulk_limit_age:
            to_bulk_delete.append(message)
            if len(to_bulk_delete) == 100:
                await channel.delete_messages(to_bulk_delete)
                deleted_count += len(to_bulk_delete)
                to_bulk_delete.clear()
                await asyncio.sleep(1)  # avoid rate limits
        else:
            # Older than 14 days -> delete individually
            try:
                await message.delete()
                deleted_count += 1
                await asyncio.sleep(1)  # be gentle with rate limits
            except discord.HTTPException:
                pass

    # Delete any remaining bulk-able messages
    if to_bulk_delete:
        await channel.delete_messages(to_bulk_delete)
        deleted_count += len(to_bulk_delete)

    print(f"Channel {channel.id}: deleted {deleted_count} messages.")
    return deleted_count


@tasks.loop(minutes=CHECK_EVERY_MINUTES)
async def cleanup_old_messages():
    await bot.wait_until_ready()

    now = datetime.now(timezone.utc)
    total_deleted = 0

    print(f"[{datetime.now()}] Starting scheduled cleanup over {len(CHANNEL_IDS)} channels...")

    for channel_id in CHANNEL_IDS:
        channel = bot.get_channel(channel_id)
        if channel is None:
            print(f"Could not find channel with ID {channel_id}")
            continue

        deleted = await _cleanup_single_channel(channel, now)
        total_deleted += deleted

    print(f"Scheduled cleanup complete. Deleted {total_deleted} messages in total.")


@bot.command(name="clean")
@commands.has_permissions(manage_messages=True)
async def cleanweek(ctx: commands.Context):
    try:
        await ctx.message.delete()
    except (discord.Forbidden, discord.HTTPException):
        pass

    status_msg = await ctx.send(
        f"Starting manual cleanup of messages older than {CLEAN_OLDER_THAN_DAYS} days..."
    )

    now = datetime.now(timezone.utc)
    total_deleted = 0

    for channel_id in CHANNEL_IDS:
        channel = bot.get_channel(channel_id)
        if channel is None:
            continue
        deleted = await _cleanup_single_channel(channel, now)
        total_deleted += deleted

    try:
        await status_msg.edit(content=f"Manual cleanup finished. Deleted {total_deleted} messages.")
    except discord.HTTPException:
        pass

    await asyncio.sleep(5)
    try:
        await status_msg.delete()
    except discord.HTTPException:
        pass


bot.run(TOKEN)
