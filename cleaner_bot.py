import os
import asyncio
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

# === CONFIG ===
TOKEN = "MTQzOTA1MTY5MDQ5NzE1MTE4OA.GhjF6z.Jk4qqfFkrA_tHfRXS9OLLhNDCh-y-keUZvoplc"          # <- paste your bot token here
CHANNEL_ID = 1439052099794108470        # <- channel ID to clean (int)
CLEAN_OLDER_THAN_DAYS = 0              # delete messages older than this
CHECK_EVERY_MINUTES = 60               # how often to run the cleanup


intents = discord.Intents.default()
intents.message_content = True  # may be required for some bots to read messages
intents.messages = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    if not cleanup_old_messages.is_running():
        cleanup_old_messages.start()
    print("Cleanup loop started.")


@tasks.loop(minutes=CHECK_EVERY_MINUTES)
async def cleanup_old_messages():
    await bot.wait_until_ready()

    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print(f"Could not find channel with ID {CHANNEL_ID}")
        return

    now = datetime.now(timezone.utc)
    cutoff_older_than = now - timedelta(days=CLEAN_OLDER_THAN_DAYS)
    cutoff_discord_limit = now - timedelta(days=14)  # can't bulk delete older than this

    print(f"[{datetime.now()}] Cleaning channel {channel.id}...")

    # We only want messages:
    #   created_at < cutoff_older_than (older than X days)
    #   and created_at > cutoff_discord_limit (younger than 14 days)
    to_delete_batch = []
    deleted_count = 0

    async for message in channel.history(limit=None, before=cutoff_older_than, oldest_first=False):
        # stop if we hit messages older than 14 days (Discord bulk delete limit)
        if message.created_at < cutoff_discord_limit:
            break

        to_delete_batch.append(message)

        # Discord bulk delete max is 100 messages
        if len(to_delete_batch) == 100:
            await channel.delete_messages(to_delete_batch)
            deleted_count += len(to_delete_batch)
            to_delete_batch.clear()
            await asyncio.sleep(1)  # small delay to avoid rate limits

    # Delete any remaining messages not yet deleted
    if to_delete_batch:
        await channel.delete_messages(to_delete_batch)
        deleted_count += len(to_delete_batch)

    print(f"Cleanup complete. Deleted {deleted_count} messages.")


# Optional: command to trigger manual cleanup
@bot.command(name="clean")
@commands.has_permissions(manage_messages=True)
async def cleanweek(ctx):
    # Try to delete the user's command message
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass  # bot doesn't have permission
    except discord.HTTPException:
        pass  # some other deletion error, ignore

    # Send a status message
    status_msg = await ctx.send("Starting manual cleanup of messages older than 7 days...")

    # Run the cleanup once
    await cleanup_old_messages()

    # Edit the status so you see it's done (optional)
    try:
        await status_msg.edit(content="Manual cleanup finished.")
    except discord.HTTPException:
        pass

    # Wait a few seconds, then delete the status message too
    await asyncio.sleep(5)
    try:
        await status_msg.delete()
    except discord.HTTPException:
        pass



bot.run(TOKEN)
