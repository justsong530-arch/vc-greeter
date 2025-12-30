# main.py
import os
import asyncio
import logging
from typing import Optional

import discord
from discord.ext import commands

# logging (Railway logs will show this)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("vc-bot")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))            # optional: numeric ID of the guild
VOICE_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID")) # required: numeric ID of the VC to join
RECONNECT_DELAY = int(os.getenv("RECONNECT_DELAY", "10"))

if not DISCORD_TOKEN or not VOICE_CHANNEL_ID:
    log.critical("DISCORD_TOKEN and VOICE_CHANNEL_ID must be set in environment variables.")
    raise SystemExit("Missing required environment variables")

intents = discord.Intents.default()
# no privileged intents needed for voice presence only
bot = commands.Bot(command_prefix="!", intents=intents)

async def ensure_connected():
    await bot.wait_until_ready()
    log.info("ensure_connected task started")
    while not bot.is_closed():
        try:
            # prefer get_guild if GUILD_ID provided, otherwise find channel by ID using bot.get_channel
            if GUILD_ID:
                guild = bot.get_guild(GUILD_ID)
                if guild is None:
                    log.warning(f"Guild {GUILD_ID} not found, retrying in {RECONNECT_DELAY}s")
                    await asyncio.sleep(RECONNECT_DELAY)
                    continue
                channel = guild.get_channel(VOICE_CHANNEL_ID)
            else:
                channel = bot.get_channel(VOICE_CHANNEL_ID)

            if channel is None:
                log.warning(f"Voice channel {VOICE_CHANNEL_ID} not found, retrying in {RECONNECT_DELAY}s")
                await asyncio.sleep(RECONNECT_DELAY)
                continue

            # if already connected to this guild, reuse connection
            voice_client: Optional[discord.VoiceClient] = discord.utils.get(bot.voice_clients, guild=channel.guild)
            if voice_client and voice_client.is_connected():
                log.info("Already connected - sleeping and monitoring")
                await asyncio.sleep(60)
                continue

            log.info(f"Connecting to voice channel: {channel.name} ({channel.id})")
            voice_client = await channel.connect(reconnect=True, timeout=30)
            log.info("Connected. Now staying silent and monitoring connection.")

            # monitor connection — if it disconnects, loop will attempt reconnect
            while voice_client and voice_client.is_connected():
                await asyncio.sleep(30)

        except Exception as exc:
            log.exception("Error in ensure_connected loop (will retry): %s", exc)
            # attempt to cleanup any broken vc
            try:
                vc = discord.utils.get(bot.voice_clients, guild=bot.get_guild(GUILD_ID)) if GUILD_ID else None
                if vc and vc.is_connected():
                    await vc.disconnect(force=True)
            except Exception:
                pass
            await asyncio.sleep(RECONNECT_DELAY)

@bot.event
async def on_ready():
    log.info(f"Bot ready: {bot.user} (ID: {bot.user.id})")

# optional simple command to check status
@bot.command(name="vcstatus")
async def vcstatus(ctx):
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc and vc.is_connected():
        await ctx.send(f"Connected in `{vc.channel.name}` (id: {vc.channel.id})")
    else:
        await ctx.send("Not connected to voice channel.")

if __name__ == "__main__":
    bot.loop.create_task(ensure_connected())
    bot.run(DISCORD_TOKEN)
