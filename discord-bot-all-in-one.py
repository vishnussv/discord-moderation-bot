"""
MADEBYSSV — ALL-IN-ONE Discord Bot — SINGLE FILE  •  SUPER UI THEME
================================================
THIS ONE FILE IS THE WHOLE BOT. No other files needed.
No .env, no requirements.txt, no config files to set up.

Everything is inside:
  Welcome + Goodbye + Auto-role | Moderation | Auto-Mod + Anti-raid
  Leveling + XP | Economy | Tickets | Giveaways | Polls | Reminders
  AFK | Fun | Music | Logging | Reaction Roles | Lockdown

HOW TO RUN (2 minutes):
  1. pip install discord.py yt-dlp
     (yt-dlp is only for music — the bot works without it)
  2. Paste your bot token below where it says PASTE_YOUR_TOKEN_HERE
  3. python discord-bot-all-in-one.py
     On Windows: py discord-bot-all-in-one.py

  Get a token: https://discord.com/developers/applications
  -> New Application -> Bot -> Reset Token
  Turn ON: Server Members Intent + Message Content Intent
  Invite it: OAuth2 -> URL Generator -> bot + applications.commands

  In Discord, then run: /setwelcome #welcome  and  /setlog #mod-log
  All data (warns, levels, coins) is saved automatically to
  warns.json / levels.json / economy.json next to this file.
"""

import os
import json
import re
import time
import random
import asyncio
from collections import defaultdict, deque
from datetime import timedelta, datetime

import discord
from discord import app_commands
from discord.ext import commands

# Optional: .env support if you use it, but NOT required.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# >>> PASTE YOUR BOT TOKEN HERE (or set DISCORD_TOKEN env var) <<<
TOKEN = os.getenv("DISCORD_TOKEN") or "PASTE_YOUR_TOKEN_HERE"
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", "0") or 0)
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0") or 0)
WELCOME_ROLE_ID = int(os.getenv("WELCOME_ROLE_ID", "0") or 0)
GUILD_ID = int(os.getenv("GUILD_ID", "0") or 0)

# Music is optional — bot works fine without yt-dlp, music commands will just say so.
try:
    import yt_dlp
    HAS_YTDLP = True
except Exception:
    yt_dlp = None
    HAS_YTDLP = False
music_queues = {}  # guild_id -> list of {title, url}

WARNS_FILE = "warns.json"
CONFIG_FILE = "config.json"

# ---------- Config / storage ----------
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

config = load_json(CONFIG_FILE, {})
if WELCOME_CHANNEL_ID:
    config.setdefault("welcome_channel_id", WELCOME_CHANNEL_ID)
if LOG_CHANNEL_ID:
    config.setdefault("log_channel_id", LOG_CHANNEL_ID)
if WELCOME_ROLE_ID:
    config.setdefault("welcome_role_id", WELCOME_ROLE_ID)

warns = load_json(WARNS_FILE, {})  # {guild_id: {user_id: [ {reason, moderator, time} ]}}
LEVELS_FILE = "levels.json"
ECONOMY_FILE = "economy.json"
AFK_FILE = "afk.json"
levels = load_json(LEVELS_FILE, {})
economy = load_json(ECONOMY_FILE, {})
afk_data = load_json(AFK_FILE, {})
join_tracker = defaultdict(lambda: deque(maxlen=20))
xp_cooldown = {}
active_giveaways = {}  # message_id -> {channel_id, prize, ends_at, host_id}
active_polls = {}

def get_level_data(guild_id, user_id):
    g = levels.setdefault(str(guild_id), {})
    return g.setdefault(str(user_id), {"xp": 0, "level": 1})

def xp_for_next(level):
    return 100 + (level - 1) * 50

def get_balance(guild_id, user_id):
    g = economy.setdefault(str(guild_id), {})
    u = g.setdefault(str(user_id), {"coins": 100, "last_daily": "", "last_work": 0})
    return u

# Bad words — edit this list to fit your server
BANNED_WORDS = [
    "badword1", "badword2",
]
INVITE_RE = re.compile(r"(discord\.gg/|discord\.com/invite/|discordapp\.com/invite/)", re.I)
LINK_RE = re.compile(r"https?://\S+|www\.\S+", re.I)

# Anti-spam: user_id -> deque of timestamps
spam_tracker = defaultdict(lambda: deque(maxlen=10))

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ---------- SUPER UI THEME — MADEBYSSV (applied to ALL embeds) ----------
BRAND = "MADEBYSSV"
TAGLINE = "ONE DASHBOARD. COMPLETE CONTROL."
THEME_COLOR = 0x00D4FF      # electric blue
THEME_DARK = 0x0B0F1A
THEME_SUCCESS = 0x00FF88
THEME_ERROR = 0xFF3B5C
THEME_WARNING = 0xFFB800
THEME_GOLD = 0xFFD700
THEME_PURPLE = 0x7C3AED

def themed_embed(title=None, description=None, color=THEME_COLOR, **kwargs):
    """Every embed in the bot goes through here — one super UI theme."""
    embed = discord.Embed(title=title, description=description, color=color, **kwargs)
    embed.set_footer(text=f"{BRAND}  •  {TAGLINE}")
    embed.timestamp = discord.utils.utcnow()
    return embed

def success_embed(title, description):
    return themed_embed(title=f"✅  {title}", description=description, color=THEME_SUCCESS)

def error_embed(title, description):
    return themed_embed(title=f"❌  {title}", description=description, color=THEME_ERROR)



def get_config(guild_id, key, default=0):
    g = config.get(str(guild_id), {})
    if g and key in g:
        return g[key]
    return config.get(key, default)


def set_config(guild_id, key, value):
    config.setdefault(str(guild_id), {})[key] = value
    config[key] = value
    save_json(CONFIG_FILE, config)


async def log(guild, title, description, color=THEME_COLOR):
    channel_id = get_config(guild.id, "log_channel_id", 0) if guild else 0
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if not channel:
        return
    embed = themed_embed(title=title, description=description, color=color)
    embed.timestamp = discord.utils.utcnow()
    try:
        await channel.send(embed=embed)
    except Exception:
        pass


def is_mod(member: discord.Member):
    return member.guild_permissions.manage_messages or member.guild_permissions.kick_members


# ---------- Startup ----------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"In {len(bot.guilds)} server(s)")
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            print(f"Synced commands to guild {GUILD_ID}")
        else:
            await bot.tree.sync()
            print("Synced global commands (can take up to 1 hour to appear)")
    except Exception as e:
        print(f"Sync failed: {e}")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, name="for new members | /help"))
    if not getattr(bot, "_giveaway_started", False):
        bot._giveaway_started = True
        bot.loop.create_task(giveaway_loop())


# ---------- Welcome / Goodbye ----------
@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    # Anti-raid: 8+ joins in 10 seconds = raid alert
    now = time.time()
    dq = join_tracker[guild.id]
    dq.append(now)
    recent = [t for t in dq if now - t < 10]
    if len(recent) >= 8:
        await log(guild, "🚨 Possible Raid Detected",
                  f"{len(recent)} members joined in 10 seconds. Latest: {member.mention}\n"
                  "Consider `/lockdown on` until it calms down.", THEME_ERROR)
        dq.clear()
    # Auto-role
    role_id = get_config(guild.id, "welcome_role_id", 0)
    if role_id:
        role = guild.get_role(role_id)
        if role:
            try:
                await member.add_roles(role, reason="Welcome auto-role")
            except Exception:
                pass

    channel_id = get_config(guild.id, "welcome_channel_id", 0)
    if channel_id:
        channel = guild.get_channel(channel_id)
        if channel:
            embed = themed_embed(
                title=f"✦  Welcome to {guild.name}  ✦",
                description=(
                    f"Hey {member.mention}, welcome to the crew! 👋\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "Please read the rules, grab your roles, and enjoy your stay!"
                ),
                color=THEME_COLOR,
            )
            embed.set_author(name=BRAND, icon_url=guild.icon.url if guild.icon else None)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="👤  Member", value=member.mention, inline=True)
            embed.add_field(name="🔢  Member #", value=f"**{guild.member_count}**", inline=True)
            embed.add_field(name="📅  Joined Discord", value=member.created_at.strftime("%d %b %Y"), inline=True)
            embed.timestamp = discord.utils.utcnow()
            try:
                await channel.send(embed=embed)
            except Exception:
                pass

    # Welcome DM (fails silently if DMs are closed)
    try:
        await member.send(
            f"Welcome to **{guild.name}**! 🎉\n"
            "Thanks for joining. Check the rules channel and have fun!"
        )
    except Exception:
        pass

    await log(guild, "Member Joined", f"{member.mention} ({member}) joined the server.",
              THEME_SUCCESS)


@bot.event
async def on_member_remove(member: discord.Member):
    guild = member.guild
    channel_id = get_config(guild.id, "welcome_channel_id", 0)
    if channel_id:
        channel = guild.get_channel(channel_id)
        if channel:
            try:
                await channel.send(f"👋 {member.mention} ({member}) has left the server.")
            except Exception:
                pass
    await log(guild, "Member Left", f"{member} left the server.", THEME_WARNING)


# ---------- Auto-Mod ----------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    # Let commands still work
    await bot.process_commands(message)

    # AFK: clear on return, notify when mentioned user is AFK
    uid = str(message.author.id)
    if uid in afk_data:
        afk_data.pop(uid, None)
        save_json(AFK_FILE, afk_data)
        try:
            await message.channel.send(f"Welcome back {message.author.mention}, I removed your AFK.", delete_after=8)
        except Exception:
            pass
    for user in message.mentions:
        if str(user.id) in afk_data:
            info = afk_data[str(user.id)]
            await message.channel.send(f"💤 {user.mention} is AFK: {info.get('reason','')} (since {info.get('since','')})", delete_after=10)
            break

    # XP / Leveling: 15-25 XP per message, max once per 60s
    now_xp = time.time()
    if now_xp - xp_cooldown.get(message.author.id, 0) >= 60:
        xp_cooldown[message.author.id] = now_xp
        data = get_level_data(message.guild.id, message.author.id)
        data["xp"] += random.randint(15, 25)
        need = xp_for_next(data["level"])
        if data["xp"] >= need:
            data["level"] += 1
            data["xp"] -= need
            save_json(LEVELS_FILE, levels)
            try:
                await message.channel.send(f"🎉 {message.author.mention} leveled up to **Level {data['level']}**!")
            except Exception:
                pass
        save_json(LEVELS_FILE, levels)
        # Small coin reward for chatting
        bal = get_balance(message.guild.id, message.author.id)
        bal["coins"] += random.randint(2, 5)
        save_json(ECONOMY_FILE, economy)

    # Mass-mention protection
    if len(message.mentions) >= 5 or len(message.role_mentions) >= 3:
        try:
            await message.delete()
        except Exception:
            pass
        await log(message.guild, "Auto-Mod: Mass Mention",
                  f"{message.author.mention} tried to mass-mention in {message.channel.mention}.", THEME_ERROR)
        return

    if is_mod(message.author):
        return

    content = message.content.lower()
    reason = None

    # Bad words
    for word in BANNED_WORDS:
        if word and word.lower() in content:
            reason = f"Used banned word: `{word}`"
            break

    # Discord invites
    if not reason and INVITE_RE.search(message.content):
        reason = "Posted a Discord invite link"

    # Links (remove this block if you want to allow links)
    # if not reason and LINK_RE.search(message.content):
    #     reason = "Posted a link"

    # Caps spam
    if not reason and len(message.content) >= 15:
        letters = [c for c in message.content if c.isalpha()]
        if letters and sum(c.isupper() for c in letters) / len(letters) > 0.8:
            reason = "Excessive caps"

    if reason:
        try:
            await message.delete()
        except Exception:
            pass
        try:
            await message.channel.send(
                f"{message.author.mention}, your message was removed: {reason}.",
                delete_after=8,
            )
        except Exception:
            pass
        await log(message.guild, "Auto-Mod: Message Deleted",
                  f"**User:** {message.author.mention}\n**Channel:** {message.channel.mention}\n"
                  f"**Reason:** {reason}\n**Message:** {message.content[:500]}",
                  THEME_ERROR)
        return

    # Anti-spam: 6 messages in 6 seconds = timeout 60s
    now = time.time()
    dq = spam_tracker[message.author.id]
    dq.append(now)
    recent = [t for t in dq if now - t < 6]
    if len(recent) >= 6:
        dq.clear()
        try:
            await message.author.timeout(timedelta(seconds=60), reason="Spam (auto-mod)")
            await message.channel.send(
                f"{message.author.mention} has been timed out for 60s for spamming.",
                delete_after=10,
            )
        except Exception:
            pass
        await log(message.guild, "Auto-Mod: Spam Timeout",
                  f"{message.author.mention} timed out for 60s for spamming.",
                  THEME_ERROR)


@bot.event
async def on_message_delete(message: discord.Message):
    if message.author.bot or not message.guild:
        return
    await log(message.guild, "Message Deleted",
              f"**Author:** {message.author.mention}\n**Channel:** {message.channel.mention}\n"
              f"**Content:** {message.content[:1000] or '(no text / embed / attachment)'}",
              THEME_WARNING)


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if before.author.bot or not before.guild or before.content == after.content:
        return
    await log(before.guild, "Message Edited",
              f"**Author:** {before.author.mention}\n**Channel:** {before.channel.mention}\n"
              f"**Before:** {before.content[:500]}\n**After:** {after.content[:500]}",
              THEME_GOLD)


# ---------- Helper for warns ----------
def add_warn(guild_id, user_id, reason, moderator):
    g = warns.setdefault(str(guild_id), {})
    u = g.setdefault(str(user_id), [])
    u.append({"reason": reason, "moderator": str(moderator), "time": time.strftime("%Y-%m-%d %H:%M")})
    save_json(WARNS_FILE, warns)
    return len(u)


# ---------- Slash commands ----------
@bot.tree.command(name="help", description="Show all bot commands")
async def help_cmd(interaction: discord.Interaction):
    embed = themed_embed(
        title="✦  MADEBYSSV  •  COMMAND CENTER  ✦",
        description="**ONE DASHBOARD. COMPLETE CONTROL.**\n━━━━━━━━━━━━━━━━━━━━\n213 commands total — 93 slash (/) + 120 prefix (!), one super theme.",
        color=THEME_COLOR,
    )
    if interaction.guild and interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.add_field(name="👋  WELCOME", value="Auto welcome + goodbye + auto-role\n`/setwelcome`", inline=True)
    embed.add_field(name="🛡️  MODERATION", value="`/warn` `/kick` `/ban` `/unban`\n`/timeout` `/mute` `/softban` `/purge`", inline=True)
    embed.add_field(name="🔒  CHANNEL", value="`/lock` `/unlock` `/slowmode`\n`/lockdown` `/announce`", inline=True)
    embed.add_field(name="🏆  LEVELING", value="`/rank` `/leaderboard`\nXP for chatting, auto level-ups", inline=True)
    embed.add_field(name="💰  ECONOMY", value="`/balance` `/daily` `/work`\n`/coinflip` `/slots` `/pay`", inline=True)
    embed.add_field(name="🎫  TICKETS & GIVEAWAYS", value="`/ticket` `/close`\n`/giveaway` `/poll`", inline=True)
    embed.add_field(name="🎵  MUSIC", value="`/play` `/skip` `/stop`\n`/queue` `/nowplaying`", inline=True)
    embed.add_field(name="😄  FUN & UTILITY", value="`/remind` `/afk` `/eightball`\n`/avatar` `/rps` `/ping`", inline=True)
    embed.add_field(name="⚙️  SETUP  •  ADMIN", value="`/setwelcome` `/setlog`\n`/reactionrole` `/addrole` `/history`", inline=True)
    embed.add_field(name="🤖  AUTO-MOD  •  ALWAYS ON", value="Bad words • invites • caps • spam • mass-mentions • anti-raid", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="theme", description="Show the MADEBYSSV super UI theme")
async def theme_cmd(interaction: discord.Interaction):
    embed = themed_embed(
        title="✦  SUPER UI THEME  ✦",
        description="**MADEBYSSV** — electric blue on dark.\n\n`#00D4FF`  Electric Blue  •  `#00FF88`  Success\n`#FF3B5C`  Error  •  `#FFB800`  Warning  •  `#FFD700`  Gold\n\nEvery embed, welcome card, ticket, giveaway, rank and log uses this one theme.",
        color=THEME_COLOR,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="ping", description="Check if the bot is online")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! 🏓 `{round(bot.latency * 1000)}ms`")


@bot.tree.command(name="userinfo", description="Show info about a user")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = themed_embed(title=f"{member}", color=THEME_COLOR)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Joined server", value=member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "Unknown")
    embed.add_field(name="Account created", value=member.created_at.strftime("%Y-%m-%d"))
    embed.add_field(name="Roles", value=", ".join(r.mention for r in member.roles[1:]) or "None")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="serverinfo", description="Show info about this server")
async def serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    embed = themed_embed(title=g.name, color=THEME_COLOR)
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    embed.add_field(name="Members", value=g.member_count)
    embed.add_field(name="Channels", value=len(g.channels))
    embed.add_field(name="Roles", value=len(g.roles))
    embed.add_field(name="Created", value=g.created_at.strftime("%Y-%m-%d"))
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="warn", description="Warn a member")
@app_commands.describe(member="Member to warn", reason="Reason for the warning")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason given"):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ You need Manage Messages to use this.", ephemeral=True)
        return
    count = add_warn(interaction.guild.id, member.id, reason, interaction.user)
    await interaction.response.send_message(f"⚠️ {member.mention} has been warned ({count} total). Reason: {reason}")
    await log(interaction.guild, "Member Warned",
              f"**User:** {member.mention}\n**By:** {interaction.user.mention}\n**Reason:** {reason}\n**Total warns:** {count}",
              THEME_GOLD)
    # Auto-kick at 3 warns
    if count >= 3:
        try:
            await member.kick(reason="3 warnings reached")
            await interaction.followup.send(f"🚨 {member.mention} was kicked automatically after 3 warnings.")
        except Exception:
            pass


@bot.tree.command(name="warnings", description="Show warnings for a member")
async def warnings(interaction: discord.Interaction, member: discord.Member):
    user_warns = warns.get(str(interaction.guild.id), {}).get(str(member.id), [])
    if not user_warns:
        await interaction.response.send_message(f"{member.mention} has no warnings. ✅", ephemeral=True)
        return
    text = "\n".join(f"{i+1}. {w['reason']} — by {w['moderator']} ({w['time']})" for i, w in enumerate(user_warns))
    await interaction.response.send_message(f"⚠️ Warnings for {member.mention}:\n{text}", ephemeral=True)


@bot.tree.command(name="clearwarns", description="Clear all warnings for a member")
async def clearwarns(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ You need Manage Messages to use this.", ephemeral=True)
        return
    warns.get(str(interaction.guild.id), {}).pop(str(member.id), None)
    save_json(WARNS_FILE, warns)
    await interaction.response.send_message(f"✅ Cleared warnings for {member.mention}")


@bot.tree.command(name="kick", description="Kick a member")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason given"):
    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("❌ You need Kick Members to use this.", ephemeral=True)
        return
    await member.kick(reason=reason)
    await interaction.response.send_message(f"👢 {member.mention} was kicked. Reason: {reason}")
    await log(interaction.guild, "Member Kicked", f"**User:** {member}\n**By:** {interaction.user.mention}\n**Reason:** {reason}", THEME_WARNING)


@bot.tree.command(name="ban", description="Ban a member")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason given"):
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("❌ You need Ban Members to use this.", ephemeral=True)
        return
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🔨 {member.mention} was banned. Reason: {reason}")
    await log(interaction.guild, "Member Banned", f"**User:** {member}\n**By:** {interaction.user.mention}\n**Reason:** {reason}", THEME_ERROR)


@bot.tree.command(name="unban", description="Unban a user by ID or name")
async def unban(interaction: discord.Interaction, user_id: str):
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("❌ You need Ban Members to use this.", ephemeral=True)
        return
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(f"✅ {user} was unbanned.")
    except Exception as e:
        await interaction.response.send_message(f"❌ Could not unban: {e}", ephemeral=True)


@bot.tree.command(name="timeout", description="Timeout a member")
@app_commands.describe(member="Member to timeout", minutes="Minutes (default 10)", reason="Reason")
async def timeout_cmd(interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "No reason given"):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ You need Timeout Members to use this.", ephemeral=True)
        return
    await member.timeout(timedelta(minutes=minutes), reason=reason)
    await interaction.response.send_message(f"⏱️ {member.mention} timed out for {minutes} min. Reason: {reason}")


@bot.tree.command(name="purge", description="Delete a number of messages")
@app_commands.describe(amount="How many messages to delete (1-100)")
async def purge(interaction: discord.Interaction, amount: int):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ You need Manage Messages to use this.", ephemeral=True)
        return
    amount = max(1, min(100, amount))
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Deleted {len(deleted)} messages.", ephemeral=True)


@bot.tree.command(name="lock", description="Lock this channel")
async def lock(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("❌ You need Manage Channels to use this.", ephemeral=True)
        return
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message("🔒 Channel locked.")


@bot.tree.command(name="unlock", description="Unlock this channel")
async def unlock(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("❌ You need Manage Channels to use this.", ephemeral=True)
        return
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message("🔓 Channel unlocked.")


@bot.tree.command(name="slowmode", description="Set slowmode in seconds (0 = off)")
async def slowmode(interaction: discord.Interaction, seconds: int):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("❌ You need Manage Channels to use this.", ephemeral=True)
        return
    await interaction.channel.edit(slowmode_delay=max(0, min(21600, seconds)))
    await interaction.response.send_message(f"🐢 Slowmode set to {seconds}s." if seconds else "🐢 Slowmode off.")


@bot.tree.command(name="setwelcome", description="Set the welcome channel (Admin)")
async def setwelcome(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    set_config(interaction.guild.id, "welcome_channel_id", channel.id)
    await interaction.response.send_message(f"✅ Welcome channel set to {channel.mention}")


@bot.tree.command(name="setlog", description="Set the mod-log channel (Admin)")
async def setlog(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    set_config(interaction.guild.id, "log_channel_id", channel.id)
    await interaction.response.send_message(f"✅ Log channel set to {channel.mention}")


# ---------- POWER UP: Leveling / Economy / Tickets / Giveaways / Polls / Fun ----------
# Reaction-role handler
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.member and payload.member.bot:
        return
    roles_map = config.get("reaction_roles", {}).get(str(payload.message_id))
    if not roles_map:
        return
    role_id = roles_map.get(str(payload.emoji))
    if not role_id:
        return
    guild = bot.get_guild(payload.guild_id)
    role = guild.get_role(role_id) if guild else None
    if role and payload.member:
        try:
            await payload.member.add_roles(role, reason="Reaction role")
        except Exception:
            pass

async def giveaway_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            now = time.time()
            finished = [mid for mid, g in active_giveaways.items() if now >= g["ends_at"]]
            for mid in finished:
                g = active_giveaways.pop(mid)
                channel = bot.get_channel(g["channel_id"])
                if not channel:
                    continue
                try:
                    msg = await channel.fetch_message(mid)
                except Exception:
                    continue
                users = []
                for reaction in msg.reactions:
                    if str(reaction.emoji) == "🎉":
                        async for u in reaction.users():
                            if not u.bot:
                                users.append(u)
                if users:
                    winner = random.choice(users)
                    await channel.send(f"🎉 **Giveaway ended!** {winner.mention} won **{g['prize']}**!")
                else:
                    await channel.send(f"🎉 Giveaway for **{g['prize']}** ended — no one entered.")
        except Exception as e:
            print(f"Giveaway loop error: {e}")
        await asyncio.sleep(30)

# --- Leveling ---
@bot.tree.command(name="rank", description="Show your level and XP")
async def rank(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    data = get_level_data(interaction.guild.id, member.id)
    need = xp_for_next(data["level"])
    pct = int(data['xp']/need*100)
    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
    embed = themed_embed(title=f"✦  {member.display_name}'s Rank  ✦", description=f"`{bar}`  **{pct}%**", color=THEME_GOLD)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🏆  Level", value=f"**{data['level']}**", inline=True)
    embed.add_field(name="✨  XP", value=f"**{data['xp']} / {need}**", inline=True)
    embed.add_field(name="🪙  Coins", value=f"**{get_balance(interaction.guild.id, member.id)['coins']}**", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard", description="Top 10 members by level")
async def leaderboard(interaction: discord.Interaction):
    g = levels.get(str(interaction.guild.id), {})
    if not g:
        await interaction.response.send_message("No XP yet — start chatting!", ephemeral=True)
        return
    top = sorted(g.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)[:10]
    lines = []
    for i, (uid, d) in enumerate(top, 1):
        member = interaction.guild.get_member(int(uid))
        name = member.display_name if member else f"User {uid}"
        lines.append(f"{i}. **{name}** — Level {d['level']} ({d['xp']} XP)")
    await interaction.response.send_message("🏆 **Leaderboard**\n" + "\n".join(lines))

# --- Economy ---
@bot.tree.command(name="balance", description="Check your coins")
async def balance(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    bal = get_balance(interaction.guild.id, member.id)
    await interaction.response.send_message(f"💰 {member.mention} has **{bal['coins']} coins**.")

@bot.tree.command(name="daily", description="Claim your daily coins (500)")
async def daily(interaction: discord.Interaction):
    bal = get_balance(interaction.guild.id, interaction.user.id)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if bal.get("last_daily") == today:
        await interaction.response.send_message("❌ You already claimed your daily today. Come back tomorrow!", ephemeral=True)
        return
    bal["last_daily"] = today
    bal["coins"] += 500
    save_json(ECONOMY_FILE, economy)
    await interaction.response.send_message(f"🎁 Daily claimed! +500 coins. Balance: **{bal['coins']}**")

@bot.tree.command(name="work", description="Work and earn coins (once per hour)")
async def work(interaction: discord.Interaction):
    bal = get_balance(interaction.guild.id, interaction.user.id)
    now = time.time()
    if now - bal.get("last_work", 0) < 3600:
        mins = int((3600 - (now - bal["last_work"])) / 60)
        await interaction.response.send_message(f"⏰ You need to rest! Try again in {mins} min.", ephemeral=True)
        return
    bal["last_work"] = now
    earned = random.randint(100, 300)
    bal["coins"] += earned
    save_json(ECONOMY_FILE, economy)
    jobs = ["coded a bot", "fixed a bug", "designed a logo", "moderated the chat", "helped a member"]
    await interaction.response.send_message(f"💼 You {random.choice(jobs)} and earned **{earned} coins**! Balance: **{bal['coins']}**")

@bot.tree.command(name="coinflip", description="Bet coins on a coin flip")
@app_commands.describe(amount="Coins to bet", choice="heads or tails")
async def coinflip(interaction: discord.Interaction, amount: int, choice: str):
    bal = get_balance(interaction.guild.id, interaction.user.id)
    if amount <= 0 or amount > bal["coins"]:
        await interaction.response.send_message("❌ Invalid bet — check your balance.", ephemeral=True)
        return
    result = random.choice(["heads", "tails"])
    if choice.lower() == result:
        bal["coins"] += amount
        msg = f"🪙 It's **{result}**! You won **{amount}** coins!"
    else:
        bal["coins"] -= amount
        msg = f"🪙 It's **{result}**! You lost **{amount}** coins."
    save_json(ECONOMY_FILE, economy)
    await interaction.response.send_message(f"{msg} Balance: **{bal['coins']}**")

@bot.tree.command(name="slots", description="Play slots — 50 coins per spin")
async def slots(interaction: discord.Interaction):
    bal = get_balance(interaction.guild.id, interaction.user.id)
    if bal["coins"] < 50:
        await interaction.response.send_message("❌ You need 50 coins to play slots.", ephemeral=True)
        return
    bal["coins"] -= 50
    symbols = ["🍒", "🍋", "⭐", "💎", "🔔", "7️⃣"]
    result = [random.choice(symbols) for _ in range(3)]
    if len(set(result)) == 1:
        win = 500
        bal["coins"] += win
        msg = f"🎰 {' '.join(result)}\n**JACKPOT! +{win} coins!**"
    elif len(set(result)) == 2:
        win = 100
        bal["coins"] += win
        msg = f"🎰 {' '.join(result)}\nNice! +{win} coins!"
    else:
        msg = f"🎰 {' '.join(result)}\nNo luck this time."
    save_json(ECONOMY_FILE, economy)
    await interaction.response.send_message(f"{msg} Balance: **{bal['coins']}**")

@bot.tree.command(name="pay", description="Give coins to another member")
async def pay(interaction: discord.Interaction, member: discord.Member, amount: int):
    if member.bot or member.id == interaction.user.id:
        await interaction.response.send_message("❌ You can't pay that user.", ephemeral=True)
        return
    bal = get_balance(interaction.guild.id, interaction.user.id)
    if amount <= 0 or amount > bal["coins"]:
        await interaction.response.send_message("❌ Invalid amount.", ephemeral=True)
        return
    bal["coins"] -= amount
    other = get_balance(interaction.guild.id, member.id)
    other["coins"] += amount
    save_json(ECONOMY_FILE, economy)
    await interaction.response.send_message(f"💸 {interaction.user.mention} gave **{amount} coins** to {member.mention}!")

# --- Tickets ---
@bot.tree.command(name="ticket", description="Open a support ticket")
@app_commands.describe(reason="What do you need help with?")
async def ticket(interaction: discord.Interaction, reason: str = "No reason given"):
    guild = interaction.guild
    existing = discord.utils.get(guild.channels, name=f"ticket-{interaction.user.name.lower()}")
    if existing:
        await interaction.response.send_message(f"❌ You already have a ticket: {existing.mention}", ephemeral=True)
        return
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    channel = await guild.create_text_channel(f"ticket-{interaction.user.name}", overwrites=overwrites, reason="Support ticket")
    embed = themed_embed(title="🎫 Support Ticket", description=f"**Opened by:** {interaction.user.mention}\n**Reason:** {reason}\n\nStaff will be with you soon. Use `/close` to close this ticket.", color=THEME_COLOR)
    await channel.send(embed=embed)
    await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

@bot.tree.command(name="close", description="Close this ticket channel")
async def close(interaction: discord.Interaction):
    if not interaction.channel.name.startswith("ticket-"):
        await interaction.response.send_message("❌ This isn't a ticket channel.", ephemeral=True)
        return
    await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
    await asyncio.sleep(5)
    try:
        await interaction.channel.delete(reason="Ticket closed")
    except Exception:
        pass

# --- Giveaway ---
@bot.tree.command(name="giveaway", description="Start a giveaway (mods only)")
@app_commands.describe(minutes="How long it runs (minutes)", prize="What is the prize?")
async def giveaway(interaction: discord.Interaction, minutes: int, prize: str):
    if not is_mod(interaction.user):
        await interaction.response.send_message("❌ Mods only.", ephemeral=True)
        return
    embed = themed_embed(title="🎉 GIVEAWAY 🎉", description=f"**Prize:** {prize}\n**Hosted by:** {interaction.user.mention}\n**Ends:** <t:{int(time.time() + minutes*60)}:R>\n\nReact with 🎉 to enter!", color=THEME_GOLD)
    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()
    await msg.add_reaction("🎉")
    active_giveaways[msg.id] = {"channel_id": interaction.channel.id, "prize": prize, "ends_at": time.time() + minutes * 60, "host_id": interaction.user.id}

# --- Polls, Reminders, AFK ---
@bot.tree.command(name="poll", description="Create a poll (up to 5 options, comma separated)")
async def poll(interaction: discord.Interaction, question: str, options: str):
    opts = [o.strip() for o in options.split(",") if o.strip()][:5]
    if len(opts) < 2:
        await interaction.response.send_message("❌ Give at least 2 options, separated by commas.", ephemeral=True)
        return
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    text = "\n".join(f"{emojis[i]} {opt}" for i, opt in enumerate(opts))
    embed = themed_embed(title=f"📊 {question}", description=text, color=THEME_COLOR)
    embed.set_footer(text=f"Poll by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()
    for i in range(len(opts)):
        await msg.add_reaction(emojis[i])

@bot.tree.command(name="remind", description="Remind yourself after X minutes")
async def remind(interaction: discord.Interaction, minutes: int, text: str):
    if minutes < 1 or minutes > 1440:
        await interaction.response.send_message("❌ Use 1–1440 minutes.", ephemeral=True)
        return
    await interaction.response.send_message(f"⏰ I'll remind you in {minutes} min: *{text}*", ephemeral=True)
    await asyncio.sleep(minutes * 60)
    try:
        await interaction.user.send(f"⏰ **Reminder:** {text}")
    except Exception:
        await interaction.channel.send(f"⏰ {interaction.user.mention} **Reminder:** {text}")

@bot.tree.command(name="afk", description="Set yourself AFK")
async def afk(interaction: discord.Interaction, reason: str = "AFK"):
    afk_data[str(interaction.user.id)] = {"reason": reason, "since": datetime.utcnow().strftime("%Y-%m-%d %H:%M")}
    save_json(AFK_FILE, afk_data)
    await interaction.response.send_message(f"💤 {interaction.user.mention} is now AFK: {reason}")

# --- Fun ---
@bot.tree.command(name="eightball", description="Ask the magic 8-ball")
async def eightball(interaction: discord.Interaction, question: str):
    answers = ["Yes!", "Definitely!", "Probably yes", "Maybe", "Ask again later", "Probably not", "Nope", "Definitely not!"]
    await interaction.response.send_message(f"🎱 **{question}**\n{random.choice(answers)}")

@bot.tree.command(name="avatar", description="Show someone's avatar")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = themed_embed(title=f"{member.display_name}'s avatar", color=THEME_COLOR)
    embed.set_image(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rps", description="Play rock, paper, scissors")
async def rps(interaction: discord.Interaction, choice: str):
    choice = choice.lower()
    if choice not in ["rock", "paper", "scissors"]:
        await interaction.response.send_message("❌ Choose rock, paper, or scissors.", ephemeral=True)
        return
    bot_choice = random.choice(["rock", "paper", "scissors"])
    wins = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
    if choice == bot_choice:
        result = "It's a tie!"
    elif wins[choice] == bot_choice:
        result = "You win! 🎉"
    else:
        result = "I win! 😎"
    await interaction.response.send_message(f"You: **{choice}** vs Me: **{bot_choice}**\n{result}")

# --- Extra moderation ---
@bot.tree.command(name="mute", description="Mute a member (timeout 10 min)")
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "No reason"):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ You need Timeout Members.", ephemeral=True)
        return
    await member.timeout(timedelta(minutes=minutes), reason=reason)
    await interaction.response.send_message(f"🔇 {member.mention} muted for {minutes} min.")

@bot.tree.command(name="unmute", description="Unmute a member")
async def unmute(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ You need Timeout Members.", ephemeral=True)
        return
    await member.timeout(None, reason="Unmuted")
    await interaction.response.send_message(f"🔊 {member.mention} unmuted.")

@bot.tree.command(name="softban", description="Ban then immediately unban (clears messages)")
async def softban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("❌ You need Ban Members.", ephemeral=True)
        return
    await member.ban(reason=reason, delete_message_days=1)
    await interaction.guild.unban(member)
    await interaction.response.send_message(f"🧹 {member.mention} was soft-banned (messages cleared).")

@bot.tree.command(name="nick", description="Change a member's nickname")
async def nick(interaction: discord.Interaction, member: discord.Member, nickname: str):
    if not interaction.user.guild_permissions.manage_nicknames:
        await interaction.response.send_message("❌ You need Manage Nicknames.", ephemeral=True)
        return
    await member.edit(nick=nickname)
    await interaction.response.send_message(f"✅ {member.mention}'s nickname is now **{nickname}**.")

@bot.tree.command(name="lockdown", description="Lock or unlock the whole server")
@app_commands.describe(mode="on to lock all channels, off to unlock")
async def lockdown(interaction: discord.Interaction, mode: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    lock = mode.lower() == "on"
    for channel in interaction.guild.text_channels:
        try:
            await channel.set_permissions(interaction.guild.default_role, send_messages=not lock)
        except Exception:
            pass
    await interaction.response.send_message("🚨 **Server lockdown ON** — no one can send messages." if lock else "✅ Lockdown lifted.")

@bot.tree.command(name="addrole", description="Give a role to a member")
async def addrole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("❌ You need Manage Roles.", ephemeral=True)
        return
    await member.add_roles(role)
    await interaction.response.send_message(f"✅ Gave {role.mention} to {member.mention}.")

@bot.tree.command(name="announce", description="Send an announcement embed to a channel")
async def announce(interaction: discord.Interaction, channel: discord.TextChannel, title: str, message: str):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ You need Manage Messages.", ephemeral=True)
        return
    embed = themed_embed(title=title, description=message, color=THEME_COLOR)
    embed.set_footer(text=f"Announced by {interaction.user.display_name}")
    await channel.send(embed=embed)
    await interaction.response.send_message(f"📢 Announcement sent to {channel.mention}", ephemeral=True)

@bot.tree.command(name="reactionrole", description="Make a message give a role on reaction (Admin)")
async def reactionrole(interaction: discord.Interaction, channel: discord.TextChannel, emoji: str, role: discord.Role, text: str = "React to get a role!"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    msg = await channel.send(text)
    await msg.add_reaction(emoji)
    config.setdefault("reaction_roles", {}).setdefault(str(msg.id), {})[str(emoji)] = role.id
    save_json(CONFIG_FILE, config)
    await interaction.response.send_message(f"✅ Reaction role set up in {channel.mention}", ephemeral=True)

@bot.tree.command(name="history", description="Show a member's warns + level")
async def history(interaction: discord.Interaction, member: discord.Member):
    user_warns = warns.get(str(interaction.guild.id), {}).get(str(member.id), [])
    lvl = get_level_data(interaction.guild.id, member.id)
    bal = get_balance(interaction.guild.id, member.id)
    embed = themed_embed(title=f"📋 History — {member.display_name}", color=THEME_COLOR)
    embed.add_field(name="Warns", value=len(user_warns))
    embed.add_field(name="Level", value=f"{lvl['level']} ({lvl['xp']} XP)")
    embed.add_field(name="Coins", value=bal["coins"])
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------- Music (all-in-one, optional yt-dlp + FFmpeg) ----------
async def play_next(interaction_or_guild, guild):
    queue = music_queues.get(guild.id, [])
    vc = guild.voice_client
    if not queue or not vc:
        return
    song = queue.pop(0)
    ydl_opts = {"format": "bestaudio/best", "quiet": True, "noplaylist": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(song["url"], download=False)
            url = info["url"]
            title = info.get("title", song["title"])
    except Exception as e:
        print(f"Music error: {e}")
        return
    def after(error):
        if error:
            print(f"Player error: {error}")
        asyncio.run_coroutine_threadsafe(play_next(None, guild), bot.loop)
    try:
        vc.play(discord.FFmpegPCMAudio(url, before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"), after=after)
        music_queues[guild.id] = queue
        # Announce in the last used channel if we can
        channel = getattr(play_next, "_last_channel", None)
        if channel:
            asyncio.run_coroutine_threadsafe(channel.send(f"🎵 Now playing: **{title}**"), bot.loop)
    except Exception as e:
        print(f"FFmpeg error (is FFmpeg installed?): {e}")

@bot.tree.command(name="play", description="Play music from YouTube (join a voice channel first)")
async def play(interaction: discord.Interaction, song: str):
    if not HAS_YTDLP:
        await interaction.response.send_message("❌ Music needs yt-dlp: run `pip install yt-dlp` and install FFmpeg, then restart the bot.", ephemeral=True)
        return
    if not interaction.user.voice:
        await interaction.response.send_message("❌ Join a voice channel first!", ephemeral=True)
        return
    await interaction.response.defer()
    play_next._last_channel = interaction.channel
    vc = interaction.guild.voice_client
    if not vc:
        vc = await interaction.user.voice.channel.connect()
    # Resolve title
    ydl_opts = {"format": "bestaudio/best", "quiet": True, "noplaylist": True, "default_search": "ytsearch"}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(song, download=False)
            if "entries" in info:
                info = info["entries"][0]
            title = info.get("title", song)
            url = info.get("webpage_url", song)
    except Exception:
        title, url = song, song
    queue = music_queues.setdefault(interaction.guild.id, [])
    queue.append({"title": title, "url": url})
    if vc.is_playing() or vc.is_paused():
        await interaction.followup.send(f"➕ Added to queue: **{title}** (#{len(queue)} in queue)")
    else:
        await interaction.followup.send(f"🎵 Now playing: **{title}**")
        await play_next(interaction, interaction.guild)

@bot.tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await interaction.response.send_message("⏭️ Skipped!")
    else:
        await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

@bot.tree.command(name="stop", description="Stop music and leave voice")
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    music_queues[interaction.guild.id] = []
    if vc:
        await vc.disconnect()
    await interaction.response.send_message("⏹️ Stopped and left voice.")

@bot.tree.command(name="queue", description="Show the music queue")
async def queue_cmd(interaction: discord.Interaction):
    queue = music_queues.get(interaction.guild.id, [])
    if not queue:
        await interaction.response.send_message("📭 Queue is empty. Use `/play <song>`", ephemeral=True)
        return
    text = "\n".join(f"{i+1}. {s['title']}" for i, s in enumerate(queue[:10]))
    await interaction.response.send_message(f"🎵 **Queue:**\n{text}")

@bot.tree.command(name="nowplaying", description="Show what's playing now")
async def nowplaying(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        await interaction.response.send_message("🎵 Music is playing right now. Use `/queue` to see what's next.")
    else:
        await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)


# ---------- 200+ COMMANDS EXPANSION ----------
# Discord allows max 100 slash commands per bot, so this bot has
# 97 slash commands + 115 prefix (!) commands = 212 total commands.
# Slash: /joke  |  Prefix: !joke  — both work, same bot, one file.
JOKES_200 = [
    "Why did the developer go broke? Because he used up all his cache!",
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "There are only 10 kinds of people: those who understand binary and those who don't.",
    "Why did the Python programmer get kicked out of the party? He kept indenting!",
    "How do you comfort a JavaScript bug? You console it!",
    "Why did the computer go to the doctor? It had a virus!",
    "What do you call a fish without eyes? A fsh!",
    "Why did the scarecrow win an award? He was outstanding in his field!",
    "I told my computer I needed a break, now it won't stop sending me KitKat ads!",
    "Why did the database admin leave his wife? She had one-to-many relationships!",
]
FACTS_200 = [
    "Honey never spoils. Archaeologists found 3000-year-old honey still good to eat!",
    "Octopuses have three hearts!",
    "Bananas are berries, but strawberries are not!",
    "The first computer bug was a real moth found in 1947!",
    "Sharks existed before trees!",
    "A day on Venus is longer than a year on Venus!",
    "The Eiffel Tower grows taller in summer!",
    "Wombat poop is cube-shaped!",
    "There are more possible chess games than atoms in the universe!",
    "Your brain generates enough electricity to power a light bulb!",
]
QUOTES_200 = [
    "The best way to predict the future is to invent it. — Alan Kay",
    "Code is like humor. When you have to explain it, it's bad. — Cory House",
    "First, solve the problem. Then, write the code. — John Johnson",
    "Simplicity is the soul of efficiency. — Austin Freeman",
    "Stay hungry, stay foolish. — Steve Jobs",
    "The only way to do great work is to love what you do. — Steve Jobs",
    "It does not matter how slowly you go as long as you do not stop. — Confucius",
    "Dream big, start small, act now.",
    "Success is not final, failure is not fatal. — Winston Churchill",
    "Believe you can and you're halfway there. — Theodore Roosevelt",
]
TRIVIA_200 = [
    ("What is the capital of France?", "Paris"),
    ("How many sides does a hexagon have?", "6"),
    ("What planet is known as the Red Planet?", "Mars"),
    ("What is 7 x 8?", "56"),
    ("Who wrote Romeo and Juliet?", "William Shakespeare"),
    ("What is the largest ocean?", "Pacific Ocean"),
    ("How many minutes are in 2 hours?", "120"),
    ("What gas do plants absorb?", "Carbon dioxide"),
    ("What is the chemical symbol for gold?", "Au"),
    ("How many continents are there?", "7"),
]

# --- NEW SLASH COMMANDS (48) ---
@bot.tree.command(name="joke", description="Get a random joke")
async def slash_joke(interaction: discord.Interaction):
    await interaction.response.send_message(f'😂 {random.choice(JOKES_200)}')

@bot.tree.command(name="fact", description="Get a random fact")
async def slash_fact(interaction: discord.Interaction):
    await interaction.response.send_message(f'🧠 **Did you know?** {random.choice(FACTS_200)}')

@bot.tree.command(name="quote", description="Get an inspirational quote")
async def slash_quote(interaction: discord.Interaction):
    await interaction.response.send_message(f'💬 {random.choice(QUOTES_200)}')

@bot.tree.command(name="fortune", description="Get your fortune")
async def slash_fortune(interaction: discord.Interaction):
    await interaction.response.send_message(f'🔮 Your fortune: {random.choice(["Great luck is coming!", "A new opportunity is near.", "Be patient, good things take time.", "Today is your lucky day!", "Someone is thinking of you."])}')

@bot.tree.command(name="advice", description="Get random advice")
async def slash_advice(interaction: discord.Interaction):
    await interaction.response.send_message(f'💡 Advice: {random.choice(["Drink more water.", "Take a break, you earned it.", "Learn one new thing today.", "Be kind to yourself.", "Backup your code!"])}')

@bot.tree.command(name="dance", description="Dance!")
async def slash_dance(interaction: discord.Interaction):
    await interaction.response.send_message(f'💃 {interaction.user.mention} is dancing! 🕺')

@bot.tree.command(name="cry", description="Cry")
async def slash_cry(interaction: discord.Interaction):
    await interaction.response.send_message(f'😭 {interaction.user.mention} is crying... *hugs*')

@bot.tree.command(name="laugh", description="Laugh out loud")
async def slash_laugh(interaction: discord.Interaction):
    await interaction.response.send_message(f'😂 {interaction.user.mention} is laughing so hard!')

@bot.tree.command(name="flip", description="Flip a coin")
async def slash_flip(interaction: discord.Interaction):
    await interaction.response.send_message(f'🪙 It landed on **{random.choice(["Heads", "Tails"])}**!')

@bot.tree.command(name="botinfo", description="Show info about this bot")
async def slash_botinfo(interaction: discord.Interaction):
    await interaction.response.send_message(embed=themed_embed(title='✦  MADEBYSSV BOT  ✦', description=f'**Commands:** {len(bot.tree.get_commands()) + len(bot.commands)} total — {len(bot.tree.get_commands())} slash + {len(bot.commands)} prefix\n**Servers:** {len(bot.guilds)}\n**Latency:** {round(bot.latency*1000)}ms\n**Made by:** MADEBYSSV', color=THEME_COLOR))

@bot.tree.command(name="uptime", description="Show how long the bot has been online")
async def slash_uptime(interaction: discord.Interaction):
    await interaction.response.send_message(f'⏰ I have been online since this session started. Latency: {round(bot.latency*1000)}ms')

@bot.tree.command(name="invite", description="Get the bot invite link")
async def slash_invite(interaction: discord.Interaction):
    await interaction.response.send_message('🔗 Invite me: go to Discord Developer Portal > OAuth2 > URL Generator > bot + applications.commands', ephemeral=True)

@bot.tree.command(name="membercount", description="Show member count")
async def slash_membercount(interaction: discord.Interaction):
    await interaction.response.send_message(f'👥 This server has **{interaction.guild.member_count}** members!')

@bot.tree.command(name="shop", description="Show the coin shop")
async def slash_shop(interaction: discord.Interaction):
    await interaction.response.send_message(embed=themed_embed(title='🛒  Coin Shop', description='🎖️ **VIP Role** — 5000 coins\n⭐ **Star Badge** — 1000 coins\n🎨 **Custom Color** — 2000 coins\n\nUse `/balance` to check coins. Shop items are for fun — ask an admin to give you the role!', color=THEME_GOLD))

@bot.tree.command(name="inventory", description="Show your inventory / coins")
async def slash_inventory(interaction: discord.Interaction):
    bal = get_balance(interaction.guild.id, interaction.user.id)
    await interaction.response.send_message(f'🎒 {interaction.user.mention} — Coins: **{bal["coins"]}** | Level: **{get_level_data(interaction.guild.id, interaction.user.id)["level"]}**')

@bot.tree.command(name="beg", description="Beg for coins")
async def slash_beg(interaction: discord.Interaction):
    earned = random.randint(10, 100)
    bal = get_balance(interaction.guild.id, interaction.user.id)
    bal['coins'] += earned
    save_json(ECONOMY_FILE, economy)
    await interaction.response.send_message(f'🙏 Someone gave you **{earned} coins**! Balance: **{bal["coins"]}**')

@bot.tree.command(name="fish", description="Go fishing for coins")
async def slash_fish(interaction: discord.Interaction):
    fish = random.choice(['🐟 Fish', '🐠 Tropical Fish', '🦈 Shark!', '👢 Old Boot', '💰 Treasure Chest'])
    earned = random.randint(20, 200) if 'Boot' not in fish else 0
    bal = get_balance(interaction.guild.id, interaction.user.id)
    bal['coins'] += earned
    save_json(ECONOMY_FILE, economy)
    await interaction.response.send_message(f'🎣 You caught: **{fish}**! +{earned} coins. Balance: **{bal["coins"]}**')

@bot.tree.command(name="hunt", description="Go hunting for coins")
async def slash_hunt(interaction: discord.Interaction):
    animal = random.choice(['🦌 Deer', '🐰 Rabbit', '🦊 Fox', '🐻 Bear!', '🐦 Bird'])
    earned = random.randint(20, 250)
    bal = get_balance(interaction.guild.id, interaction.user.id)
    bal['coins'] += earned
    save_json(ECONOMY_FILE, economy)
    await interaction.response.send_message(f'🏹 You hunted a **{animal}**! +{earned} coins. Balance: **{bal["coins"]}**')

@bot.tree.command(name="trivia", description="Get a trivia question")
async def slash_trivia(interaction: discord.Interaction):
    q, a = random.choice(TRIVIA_200)
    await interaction.response.send_message(f'❓ **Trivia:** {q}\n||Answer: {a}||')

@bot.tree.command(name="roast", description="Roast a member")
async def slash_roast(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(f'🔥 {interaction.user.mention} roasts {member.mention}: {random.choice(["You are so slow, you make a snail look fast!", "Your code has more bugs than a rainforest!", "You are the reason the WiFi is slow!"])}')

@bot.tree.command(name="compliment", description="Compliment a member")
async def slash_compliment(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(f'💖 {interaction.user.mention} compliments {member.mention}: {random.choice(["You are awesome!", "You have great vibes!", "You are the best!"])}')

@bot.tree.command(name="hug", description="Hug a member")
async def slash_hug(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(f'🤗 {interaction.user.mention} hugs {member.mention}!')

@bot.tree.command(name="slap", description="Slap a member")
async def slash_slap(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(f'👋 {interaction.user.mention} slaps {member.mention}!')

@bot.tree.command(name="pat", description="Pat a member")
async def slash_pat(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(f'🐾 {interaction.user.mention} pats {member.mention}!')

@bot.tree.command(name="kiss", description="Kiss a member")
async def slash_kiss(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(f'💋 {interaction.user.mention} kisss {member.mention}!')

@bot.tree.command(name="wave", description="Wave at a member")
async def slash_wave(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(f'👋 {interaction.user.mention} waves {member.mention}!')

@bot.tree.command(name="poke", description="Poke a member")
async def slash_poke(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(f'👉 {interaction.user.mention} pokes {member.mention}!')

@bot.tree.command(name="tickle", description="Tickle a member")
async def slash_tickle(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(f'😂 {interaction.user.mention} tickles {member.mention}!')

@bot.tree.command(name="cuddle", description="Cuddle a member")
async def slash_cuddle(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(f'🥰 {interaction.user.mention} cuddles {member.mention}!')

@bot.tree.command(name="rob", description="Try to rob a member")
async def slash_rob(interaction: discord.Interaction, member: discord.Member):
    bal = get_balance(interaction.guild.id, interaction.user.id)
    other = get_balance(interaction.guild.id, member.id)
    stolen = random.randint(10, 100) if other['coins'] >= 10 else 0
    other['coins'] -= stolen
    bal['coins'] += stolen
    save_json(ECONOMY_FILE, economy)
    await interaction.response.send_message(f'🦹 {interaction.user.mention} robbed **{stolen} coins** from {member.mention}!')

@bot.tree.command(name="ship", description="Ship yourself with a member")
async def slash_ship(interaction: discord.Interaction, member: discord.Member):
    pct = random.randint(0, 100)
    await interaction.response.send_message(f'💘 {interaction.user.mention} + {member.mention} = **{pct}%** match! {"Perfect match! 💕" if pct > 80 else "Maybe friends? 🙂"}')

@bot.tree.command(name="love", description="Check love compatibility with a member")
async def slash_love(interaction: discord.Interaction, member: discord.Member):
    pct = random.randint(0, 100)
    await interaction.response.send_message(f'❤️ Love between {interaction.user.mention} and {member.mention}: **{pct}%**')

@bot.tree.command(name="reverse", description="Reverse some text")
async def slash_reverse(interaction: discord.Interaction, text: str = ''):
    await interaction.response.send_message(f'🔄 {text[::-1]}')

@bot.tree.command(name="mock", description="mOcK sOmE tExT")
async def slash_mock(interaction: discord.Interaction, text: str = ''):
    await interaction.response.send_message(''.join(c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(text)))

@bot.tree.command(name="shout", description="SHOUT SOME TEXT")
async def slash_shout(interaction: discord.Interaction, text: str = ''):
    await interaction.response.send_message(text.upper() + '!!!')

@bot.tree.command(name="binary", description="Convert text to binary")
async def slash_binary(interaction: discord.Interaction, text: str = ''):
    await interaction.response.send_message(' '.join(format(ord(c), '08b') for c in text) or 'Give me some text!')

@bot.tree.command(name="emojify", description="Convert text to emoji letters")
async def slash_emojify(interaction: discord.Interaction, text: str = ''):
    await interaction.response.send_message(' '.join(f':regional_indicator_{c.lower()}:' if c.isalpha() else c for c in text))

@bot.tree.command(name="choose", description="Choose between options (comma separated)")
async def slash_choose(interaction: discord.Interaction, options: str):
    opts = [o.strip() for o in options.split(',') if o.strip()]
    await interaction.response.send_message(f'🤔 I choose: **{random.choice(opts) if opts else "nothing"}**')

@bot.tree.command(name="roll", description="Roll a dice (sides, default 6)")
async def slash_roll(interaction: discord.Interaction, number: int = 6):
    await interaction.response.send_message(f'🎲 You rolled **{random.randint(1, max(2, number))}**')

@bot.tree.command(name="password", description="Generate a random password")
async def slash_password(interaction: discord.Interaction, length: int = 12):
    import string as _s
    chars = _s.ascii_letters + _s.digits + '!@#$%'
    pw = ''.join(random.choice(chars) for _ in range(max(6, min(32, length))))
    await interaction.response.send_message(f'🔐 Your password: `{pw}`', ephemeral=True)

@bot.tree.command(name="randomcolor", description="Get a random color")
async def slash_randomcolor(interaction: discord.Interaction, text: str = ''):
    await interaction.response.send_message(f'🎨 Random color: **#{random.randint(0, 0xFFFFFF):06X}**')

@bot.tree.command(name="calculate", description="Calculate an expression like 5+3*2")
async def slash_calculate(interaction: discord.Interaction, expression: str):
    try:
        result = eval(expression, {'__builtins__': {}}, {})
        await interaction.response.send_message(f'🧮 `{expression}` = **{result}**')
    except Exception:
        await interaction.response.send_message('❌ Invalid expression. Try like `5+3*2`.', ephemeral=True)

@bot.tree.command(name="horoscope", description="Get a horoscope for a star sign")
async def slash_horoscope(interaction: discord.Interaction, text: str = ''):
    await interaction.response.send_message(f'⭐ Horoscope for **{text}**: {random.choice(["Today is a great day!", "Be brave today.", "Good luck is coming.", "Take a chance!"])}')

@bot.tree.command(name="eightball2", description="Ask the magic 8-ball (alias)")
async def slash_eightball2(interaction: discord.Interaction, text: str = ''):
    await interaction.response.send_message(f'🎱 {random.choice(["Yes!", "No!", "Maybe", "Ask again later", "Definitely!"])}')

# --- PREFIX COMMANDS (115) — use with ! e.g. !ping, !joke, !hug @user ---
@bot.command(name="hug")
async def prefix_hug(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} hugs {target}!')

@bot.command(name="slap")
async def prefix_slap(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} slaps {target}!')

@bot.command(name="pat")
async def prefix_pat(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} pats {target}!')

@bot.command(name="kiss")
async def prefix_kiss(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} kisss {target}!')

@bot.command(name="wave")
async def prefix_wave(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} waves {target}!')

@bot.command(name="poke")
async def prefix_poke(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} pokes {target}!')

@bot.command(name="tickle")
async def prefix_tickle(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} tickles {target}!')

@bot.command(name="cuddle")
async def prefix_cuddle(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} cuddles {target}!')

@bot.command(name="boop")
async def prefix_boop(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} boops {target}!')

@bot.command(name="highfive")
async def prefix_highfive(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} highfives {target}!')

@bot.command(name="dance")
async def prefix_dance(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} dances {target}!')

@bot.command(name="cry")
async def prefix_cry(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} crys {target}!')

@bot.command(name="laugh")
async def prefix_laugh(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} laughs {target}!')

@bot.command(name="sleep")
async def prefix_sleep(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} sleeps {target}!')

@bot.command(name="eat")
async def prefix_eat(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} eats {target}!')

@bot.command(name="drink")
async def prefix_drink(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} drinks {target}!')

@bot.command(name="run")
async def prefix_run(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} runs {target}!')

@bot.command(name="jump")
async def prefix_jump(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} jumps {target}!')

@bot.command(name="smile")
async def prefix_smile(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} smiles {target}!')

@bot.command(name="wink")
async def prefix_wink(ctx, member: discord.Member = None):
    target = member.mention if member else 'everyone'
    await ctx.send(f'✨ {ctx.author.mention} winks {target}!')

@bot.command(name="joke")
async def prefix_joke(ctx, *, text: str = ''):
    await ctx.send(f'😂 {random.choice(JOKES_200)}')

@bot.command(name="fact")
async def prefix_fact(ctx, *, text: str = ''):
    await ctx.send(f'🧠 {random.choice(FACTS_200)}')

@bot.command(name="quote")
async def prefix_quote(ctx, *, text: str = ''):
    await ctx.send(f'💬 {random.choice(QUOTES_200)}')

@bot.command(name="fortune")
async def prefix_fortune(ctx, *, text: str = ''):
    await ctx.send(f'🔮 {random.choice(["Great luck!", "Good things coming!", "Be patient."])}')

@bot.command(name="advice")
async def prefix_advice(ctx, *, text: str = ''):
    await ctx.send(f'💡 {random.choice(["Drink water.", "Take a break.", "Backup your code!"])}')

@bot.command(name="meme")
async def prefix_meme(ctx, *, text: str = ''):
    await ctx.send(f'😂 Meme: {random.choice(JOKES_200)}')

@bot.command(name="trivia")
async def prefix_trivia(ctx, *, text: str = ''):
    q, a = random.choice(TRIVIA_200)
    await ctx.send(f'❓ {q} ||Answer: {a}||')

@bot.command(name="flip")
async def prefix_flip(ctx, *, text: str = ''):
    await ctx.send(f'🪙 {random.choice(["Heads", "Tails"])}')

@bot.command(name="dice")
async def prefix_dice(ctx, *, text: str = ''):
    await ctx.send(f'🎲 {random.randint(1, 6)}')

@bot.command(name="coin")
async def prefix_coin(ctx, *, text: str = ''):
    await ctx.send(f'🪙 {random.choice(["Heads", "Tails"])}')

@bot.command(name="love")
async def prefix_love(ctx, *, text: str = ''):
    await ctx.send(f'❤️ Love: {random.randint(0, 100)}%')

@bot.command(name="ship")
async def prefix_ship(ctx, *, text: str = ''):
    await ctx.send(f'💘 Ship: {random.randint(0, 100)}% match!')

@bot.command(name="roast")
async def prefix_roast(ctx, *, text: str = ''):
    await ctx.send(f'🔥 {random.choice(["You are so slow!", "Nice try!"])}')

@bot.command(name="compliment")
async def prefix_compliment(ctx, *, text: str = ''):
    await ctx.send(f'💖 {random.choice(["You are awesome!", "Great vibes!"])}')

@bot.command(name="password")
async def prefix_password(ctx, *, text: str = ''):
    import string as _s
    await ctx.send('🔐 `' + ''.join(random.choice(_s.ascii_letters + _s.digits) for _ in range(12)) + '`')

@bot.command(name="randomcolor")
async def prefix_randomcolor(ctx, *, text: str = ''):
    await ctx.send(f'🎨 #{random.randint(0, 0xFFFFFF):06X}')

@bot.command(name="choose")
async def prefix_choose(ctx, *, text: str = ''):
    opts = [o.strip() for o in text.split(',') if o.strip()]
    await ctx.send(f'🤔 {random.choice(opts) if opts else "Give options!"}')

@bot.command(name="roll")
async def prefix_roll(ctx, *, text: str = ''):
    await ctx.send(f'🎲 {random.randint(1, 6)}')

@bot.command(name="guess")
async def prefix_guess(ctx, *, text: str = ''):
    await ctx.send(f'🎯 I am thinking of {random.randint(1, 100)}! (use /trivia for games)')

@bot.command(name="eightball")
async def prefix_eightball(ctx, *, text: str = ''):
    await ctx.send(f'🎱 {random.choice(["Yes!", "No!", "Maybe", "Definitely!"])}')

@bot.command(name="ping")
async def prefix_util_ping(ctx):
    await ctx.send(f'🏓 Pong! {round(bot.latency*1000)}ms')

@bot.command(name="avatar")
async def prefix_util_avatar(ctx):
    await ctx.send(ctx.author.display_avatar.url)

@bot.command(name="userinfo")
async def prefix_util_userinfo(ctx):
    await ctx.send(f'👤 {ctx.author} — ID: {ctx.author.id} — Joined: {ctx.author.joined_at}')

@bot.command(name="serverinfo")
async def prefix_util_serverinfo(ctx):
    await ctx.send(f'🏠 {ctx.guild.name} — Members: {ctx.guild.member_count}')

@bot.command(name="botinfo")
async def prefix_util_botinfo(ctx):
    await ctx.send(f'🤖 MADEBYSSV Bot — {len(bot.tree.get_commands())} slash + {len(bot.commands)} prefix commands')

@bot.command(name="uptime")
async def prefix_util_uptime(ctx):
    await ctx.send(f'⏰ Latency: {round(bot.latency*1000)}ms')

@bot.command(name="invite")
async def prefix_util_invite(ctx):
    await ctx.send('🔗 Invite me from the Discord Developer Portal > OAuth2 > URL Generator')

@bot.command(name="membercount")
async def prefix_util_membercount(ctx):
    await ctx.send(f'👥 {ctx.guild.member_count} members')

@bot.command(name="rank")
async def prefix_util_rank(ctx):
    d = get_level_data(ctx.guild.id, ctx.author.id)
    await ctx.send(f'🏆 Level {d["level"]} — {d["xp"]} XP')

@bot.command(name="leaderboard")
async def prefix_util_leaderboard(ctx):
    await ctx.send('🏆 Use /leaderboard for the full leaderboard!')

@bot.command(name="balance")
async def prefix_util_balance(ctx):
    b = get_balance(ctx.guild.id, ctx.author.id)
    await ctx.send(f'💰 You have {b["coins"]} coins')

@bot.command(name="daily")
async def prefix_util_daily(ctx):
    await ctx.send('🎁 Use /daily to claim 500 coins!')

@bot.command(name="work")
async def prefix_util_work(ctx):
    await ctx.send('💼 Use /work to earn coins!')

@bot.command(name="help")
async def prefix_util_help(ctx):
    await ctx.send('🤖 Use /help for all commands! I have 200+ commands.')

@bot.command(name="theme")
async def prefix_util_theme(ctx):
    await ctx.send('✦ MADEBYSSV Super UI Theme — Electric Blue #00D4FF')

@bot.command(name="rules")
async def prefix_util_rules(ctx):
    await ctx.send('📜 Be kind, no spam, no hate. Have fun!')

@bot.command(name="welcome")
async def prefix_util_welcome(ctx):
    await ctx.send(f'👋 Welcome to {ctx.guild.name}!')

@bot.command(name="goodbye")
async def prefix_util_goodbye(ctx):
    await ctx.send('👋 Goodbye!')

@bot.command(name="support")
async def prefix_util_support(ctx):
    await ctx.send('🎫 Use /ticket to open a support ticket!')

@bot.command(name="donate")
async def prefix_util_donate(ctx):
    await ctx.send('💖 Thanks for supporting MADEBYSSV!')

@bot.command(name="warn")
async def prefix_mod_warn(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /warn {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="kick")
async def prefix_mod_kick(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /kick {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="ban")
async def prefix_mod_ban(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /ban {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="unban")
async def prefix_mod_unban(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /unban {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="timeout")
async def prefix_mod_timeout(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /timeout {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="mute")
async def prefix_mod_mute(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /mute {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="unmute")
async def prefix_mod_unmute(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /unmute {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="purge")
async def prefix_mod_purge(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /purge {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="lock")
async def prefix_mod_lock(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /lock {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="unlock")
async def prefix_mod_unlock(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /unlock {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="slowmode")
async def prefix_mod_slowmode(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /slowmode {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="nick")
async def prefix_mod_nick(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /nick {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="softban")
async def prefix_mod_softban(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /softban {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="clearwarns")
async def prefix_mod_clearwarns(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /clearwarns {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="warnings")
async def prefix_mod_warnings(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /warnings {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="lockdown")
async def prefix_mod_lockdown(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /lockdown {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="addrole")
async def prefix_mod_addrole(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /addrole {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="removerole")
async def prefix_mod_removerole(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /removerole {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="announce")
async def prefix_mod_announce(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /announce {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="setwelcome")
async def prefix_mod_setwelcome(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /setwelcome {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="setlog")
async def prefix_mod_setlog(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /setlog {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="ticket")
async def prefix_mod_ticket(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /ticket {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="close")
async def prefix_mod_close(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /close {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="giveaway")
async def prefix_mod_giveaway(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /giveaway {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="poll")
async def prefix_mod_poll(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /poll {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="remind")
async def prefix_mod_remind(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /remind {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="afk")
async def prefix_mod_afk(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /afk {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="play")
async def prefix_mod_play(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /play {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="skip")
async def prefix_mod_skip(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /skip {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="stop")
async def prefix_mod_stop(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /stop {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="queue")
async def prefix_mod_queue(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /queue {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="nowplaying")
async def prefix_mod_nowplaying(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /nowplaying {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="coinflip")
async def prefix_mod_coinflip(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /coinflip {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="slots")
async def prefix_mod_slots(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /slots {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="pay")
async def prefix_mod_pay(ctx, *, args: str = ''):
    await ctx.send(f'⚙️ Use the slash version: /pay {args} — prefix version is a shortcut, slash is recommended!')

@bot.command(name="hello")
async def prefix_extra_hello(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says hello!')

@bot.command(name="hi")
async def prefix_extra_hi(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says hi!')

@bot.command(name="bye")
async def prefix_extra_bye(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says bye!')

@bot.command(name="goodmorning")
async def prefix_extra_goodmorning(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says goodmorning!')

@bot.command(name="goodnight")
async def prefix_extra_goodnight(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says goodnight!')

@bot.command(name="thanks")
async def prefix_extra_thanks(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says thanks!')

@bot.command(name="lol")
async def prefix_extra_lol(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says lol!')

@bot.command(name="wow")
async def prefix_extra_wow(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says wow!')

@bot.command(name="omg")
async def prefix_extra_omg(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says omg!')

@bot.command(name="yay")
async def prefix_extra_yay(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says yay!')

@bot.command(name="sad")
async def prefix_extra_sad(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says sad!')

@bot.command(name="happy")
async def prefix_extra_happy(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says happy!')

@bot.command(name="angry")
async def prefix_extra_angry(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says angry!')

@bot.command(name="bored")
async def prefix_extra_bored(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says bored!')

@bot.command(name="hungry")
async def prefix_extra_hungry(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says hungry!')

@bot.command(name="thirsty")
async def prefix_extra_thirsty(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says thirsty!')

@bot.command(name="tired")
async def prefix_extra_tired(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says tired!')

@bot.command(name="cool")
async def prefix_extra_cool(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says cool!')

@bot.command(name="awesome")
async def prefix_extra_awesome(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says awesome!')

@bot.command(name="nice")
async def prefix_extra_nice(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says nice!')

@bot.command(name="gg")
async def prefix_extra_gg(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says gg!')

@bot.command(name="wp")
async def prefix_extra_wp(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says wp!')

@bot.command(name="brb")
async def prefix_extra_brb(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says brb!')


@bot.command(name="lurk")
async def prefix_extra_lurk(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says lurk!')

@bot.command(name="shoutout")
async def prefix_extra_shoutout(ctx):
    await ctx.send(f'✨ {ctx.author.mention} says shoutout!')

# ---------- FREE HOSTING: keep-alive web server (Render / Railway) ----------
# Render's free web service sleeps after 15 min with no traffic.
# This tiny server (no extra install needed) answers on $PORT so
# UptimeRobot can ping it every 5 min and keep it awake.
# Railway workers ignore PORT and just run the bot.
def _start_keep_alive():
    port = int(os.getenv("PORT", "0") or 0)
    if not port:
        return
    try:
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import threading
        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"MADEBYSSV Bot is online!")
            def log_message(self, *args):
                pass
        threading.Thread(target=HTTPServer(("0.0.0.0", port), _Handler).serve_forever, daemon=True).start()
        print(f"Keep-alive web server on port {port}")
    except Exception as e:
        print(f"Keep-alive failed (bot will still run): {e}")

# ---------- Run — single file, just paste your token above ----------
if __name__ == "__main__":
    if not TOKEN or TOKEN == "PASTE_YOUR_TOKEN_HERE":
        print("ERROR: Paste your bot token at the top of this file where it says PASTE_YOUR_TOKEN_HERE")
        print("Get one at: https://discord.com/developers/applications -> Bot -> Reset Token")
        print("On Railway / Render, set DISCORD_TOKEN as an environment variable instead.")
        raise SystemExit(1)
    _start_keep_alive()
    bot.run(TOKEN)
