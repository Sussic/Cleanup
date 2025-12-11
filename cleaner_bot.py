import os
import asyncio
from datetime import datetime, timedelta, timezone

import discord

# === CONFIG ===
TOKEN = os.getenv("BOT_TOKEN")          # read from env (do NOT paste the token here)

# List of channels to clean
CHANNEL_IDS = [
    1439052099794108470,
    1447026793386082527,
    1447025718725967882
]

CLEAN_OLDER_THAN_DAYS = 7              # delete messages older than 7 days

if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set")

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
# message_content is not required for deletion, only for reading content


client = discord.Client(intents=intents)


async def _cleanup_single_channel(channel: discord.TextChannel, now: datetime) -> int:
    """
    Cleans a single channel and returns the number of deleted messages.
    """
    cutoff_older_than = now - timedelta(days=CLEAN_OLDER_THAN_DAYS)
    bulk_limit_age = timedelta(days=14)  # Discord bulk delete limit

    print(f"[{datetime.now()}] Cleaning channel {channel.id}...")

    to_bulk_delete = []
    deleted_count = 0

    # Only look at messages older than the cutoff
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


@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")
    print(f"Starting one-shot cleanup for {len(CHANNEL_IDS)} channels...")

    now = datetime.now(timezone.utc)
    total_deleted = 0

    for channel_id in CHANNEL_IDS:
        channel = client.get_channel(channel_id)
        if channel is None:
            print(f"Could not find channel with ID {channel_id}")
            continue

        deleted = await _cleanup_single_channel(channel, now)
        total_deleted += deleted

    print(f"Cleanup complete. Deleted {total_deleted} messages in total.")
    # Disconnect the client so the process exits
    await client.close()


def main():
    client.run(TOKEN)


if __name__ == "__main__":
    main()
