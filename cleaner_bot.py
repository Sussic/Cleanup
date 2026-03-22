import os
import asyncio
from datetime import datetime, timedelta, timezone

import discord

TOKEN = os.getenv("BOT_TOKEN")

CHANNEL_IDS = [
    1439052099794108470,
    1447026793386082527,
    1447025718725967882,
]

DELETE_AFTER_DAYS = 30
RETENTION_WINDOW_DAYS = 1

MAX_RETENTION_DELETES_PER_CHANNEL = 500
MAX_BACKLOG_DELETES_PER_CHANNEL = 200

if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set")

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True

client = discord.Client(intents=intents)


async def delete_messages_in_window(
    channel: discord.TextChannel,
    now: datetime,
    older_than_days: int,
    newer_than_days: int,
    max_deletes: int,
) -> int:
    """
    Delete messages where:
      newer_than_days < age <= older_than_days
    Example:
      older_than_days=31, newer_than_days=30
      => delete messages 30-31 days old
    """
    before_dt = now - timedelta(days=newer_than_days)
    after_dt = now - timedelta(days=older_than_days)

    deleted = 0

    async for message in channel.history(
        limit=None,
        before=before_dt,
        after=after_dt,
        oldest_first=False,
    ):
        try:
            await message.delete()
            deleted += 1

            if deleted % 10 == 0:
                await asyncio.sleep(1)

            if deleted >= max_deletes:
                break

        except discord.HTTPException as e:
            print(f"Failed to delete message {message.id} in {channel.id}: {e}")

    return deleted


async def delete_backlog(
    channel: discord.TextChannel,
    now: datetime,
    older_than_days: int,
    max_deletes: int,
) -> int:
    """
    Delete messages older than older_than_days, capped per run.
    """
    before_dt = now - timedelta(days=older_than_days)
    deleted = 0

    async for message in channel.history(
        limit=None,
        before=before_dt,
        oldest_first=False,
    ):
        try:
            await message.delete()
            deleted += 1

            if deleted % 10 == 0:
                await asyncio.sleep(1)

            if deleted >= max_deletes:
                break

        except discord.HTTPException as e:
            print(f"Failed to delete backlog message {message.id} in {channel.id}: {e}")

    return deleted


async def cleanup_channel(channel: discord.TextChannel, now: datetime) -> int:
    total_deleted = 0

    print(f"Channel {channel.id}: retention cleanup start")
    retention_deleted = await delete_messages_in_window(
        channel=channel,
        now=now,
        older_than_days=DELETE_AFTER_DAYS + RETENTION_WINDOW_DAYS,  # 31
        newer_than_days=DELETE_AFTER_DAYS,                          # 30
        max_deletes=MAX_RETENTION_DELETES_PER_CHANNEL,
    )
    total_deleted += retention_deleted
    print(f"Channel {channel.id}: retention deleted {retention_deleted}")

    print(f"Channel {channel.id}: backlog cleanup start")
    backlog_deleted = await delete_backlog(
        channel=channel,
        now=now,
        older_than_days=DELETE_AFTER_DAYS + RETENTION_WINDOW_DAYS,  # >31 days
        max_deletes=MAX_BACKLOG_DELETES_PER_CHANNEL,
    )
    total_deleted += backlog_deleted
    print(f"Channel {channel.id}: backlog deleted {backlog_deleted}")

    return total_deleted


@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")
    now = datetime.now(timezone.utc)
    total_deleted = 0

    for channel_id in CHANNEL_IDS:
        channel = client.get_channel(channel_id)
        if channel is None:
            try:
                channel = await client.fetch_channel(channel_id)
            except discord.HTTPException as e:
                print(f"Could not fetch channel {channel_id}: {e}")
                continue

        if not isinstance(channel, discord.TextChannel):
            print(f"Channel {channel_id} is not a text channel, skipping.")
            continue

        deleted = await cleanup_channel(channel, now)
        total_deleted += deleted

    print(f"Cleanup complete. Deleted {total_deleted} messages in total.")
    await client.close()


def main():
    client.run(TOKEN)


if __name__ == "__main__":
    main()
