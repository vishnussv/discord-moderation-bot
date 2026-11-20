# Moderation + Welcome Discord Bot — All in One (Powerful v2)

One file (`bot.py`) does everything: welcome, goodbye, auto-role, moderation, auto-mod, logging, leveling, economy, tickets, giveaways, polls, and fun — **43 slash commands**.

## What's inside

**Welcome**
- Welcome embed in your welcome channel + welcome DM
- Goodbye message when someone leaves
- Auto-role for new members (set `WELCOME_ROLE_ID` in `.env`)

**Moderation — slash commands**
- `/warn` / `/warnings` / `/clearwarns` — 3 warns = auto-kick
- `/kick` `/ban` `/unban` `/timeout`
- `/purge` — delete 1–100 messages
- `/lock` `/unlock` `/slowmode`

**Auto-Mod (automatic, no command needed)**
- Bad-word filter — edit `BANNED_WORDS` at the top of `bot.py`
- Blocks Discord invite links
- Caps-spam filter
- Anti-spam — 6 messages in 6 seconds = 60-second timeout

**Logging**
- Joins, leaves, warns, kicks, bans, deleted + edited messages
- Set with `/setlog #channel`

**Info**
- `/help` `/ping` `/userinfo` `/serverinfo`

**Setup commands (Admin)**
- `/setwelcome #channel`
- `/setlog #channel`

## NEW in Powerful v2

**Leveling (automatic)**
- Earn 15–25 XP per message, level-up announcements
- `/rank` `/leaderboard` — saved in `levels.json`

**Economy**
- Earn coins by chatting, `/daily` (+500), `/work` (100–300/hr)
- `/balance` `/pay` `/coinflip` `/slots`

**Tickets**
- `/ticket <reason>` — creates a private channel, `/close` to delete it

**Giveaways**
- `/giveaway <minutes> <prize>` — react 🎉 to enter, auto-picks a winner

**Anti-raid + extra moderation**
- Raid alert when 8+ people join in 10 seconds
- Mass-mention blocker, `/mute` `/unmute` `/softban` `/nick` `/lockdown on|off` `/addrole` `/announce` `/reactionrole` `/history`

**Utility + Fun**
- `/poll <question> <option1, option2...>` `/remind <minutes> <text>` `/afk <reason>`
- `/eightball` `/avatar` `/rps`

**Data files:** `levels.json`, `economy.json`, `afk.json`, `warns.json`, `config.json` — all saved automatically, no database needed.

## 1. Create the bot on Discord (5 minutes)

1. Go to https://discord.com/developers/applications → **New Application** → name it
2. Left menu → **Bot** → **Reset Token** → copy the token
3. On the same Bot page, turn ON these Privileged Gateway Intents:
   - **Server Members Intent**
   - **Message Content Intent**
4. Left menu → **OAuth2 → URL Generator**
   - Scopes: check `bot` + `applications.commands`
   - Bot Permissions: check `Administrator` (easiest), or at minimum: Manage Roles, Kick Members, Ban Members, Moderate Members, Manage Messages, Manage Channels, Read Messages, Send Messages, Embed Links
   - Copy the URL at the bottom, open it, pick your server, authorize

## 2. Run it

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and paste your DISCORD_TOKEN
python bot.py
```

You should see `Logged in as ...` in the terminal.

On Windows, use `py bot.py` if `python` doesn't work.

## 3. Set it up in Discord

In your server, run:
- `/setwelcome #welcome` — where welcome/goodbye messages go
- `/setlog #mod-log` — where mod logs go

Then test: `/ping`, `/help`

## Hosting — keep it online 24/7

The bot only works while `bot.py` is running. Options:
- **Your PC:** leave the terminal open
- **Free hosting:** Railway, Render, Replit, or a VPS — upload this folder, set `DISCORD_TOKEN` as an environment variable, run `python bot.py`

## Editing

- Bad words: edit `BANNED_WORDS` in `bot.py`
- To allow links: the link filter is already commented out in `on_message` — uncomment it to block links for non-mods
- Warns are saved in `warns.json`, settings in `config.json`

## Never share

Never share your `DISCORD_TOKEN` or your `.env` file. If it leaks, reset it in the Developer Portal.
