# FREE HOSTING — MADEBYSSV Discord Bot

Your bot is ready to deploy. It has 213 commands, super UI theme, and a
built-in keep-alive web server (no extra install needed).

**You still need your bot token.** Get it first:
Discord Developer Portal > your app > Bot > Reset Token.
Turn ON: Server Members Intent + Message Content Intent.
Never paste the token in chat or in a public repo — put it in the
host's Environment Variables as `DISCORD_TOKEN`.

## Option 1 — Railway (recommended, easiest free start)

1. Go to railway.app, sign in with GitHub.
2. New Project > Deploy from GitHub repo — push this folder to GitHub first,
   OR: New Project > Empty Project > add a service from your repo.
3. In the service, go to Variables and add:
   - `DISCORD_TOKEN` = your bot token
4. Railway auto-detects Python from `requirements.txt` and runs
   `python bot.py` (see `railway.json`).
5. Check Logs — you should see `Logged in as ...`
6. Free tier: $5 trial for 30 days, then ~$1/month credit. A tiny bot
   usually fits, but it stops when credit runs out.

## Option 2 — Render (free, sleeps sometimes)

1. Push this folder to GitHub.
2. Go to render.com > New > Web Service > pick your repo.
3. Build Command: `pip install -r requirements.txt`
   Start Command: `python bot.py`
4. Add Environment Variable: `DISCORD_TOKEN` = your bot token
5. Deploy. Copy your Render URL, e.g. `https://madebyssv-discord-bot.onrender.com`
6. Keep it awake (free tier sleeps after 15 min with no traffic):
   Go to uptimerobot.com (free), add an HTTP monitor for your Render URL,
   every 5 minutes. The bot's built-in keep-alive server answers it.
7. Free tier: 750 hours/month, but it sleeps — UptimeRobot is the workaround.

## Option 3 — Fly.io / Oracle Cloud (true 24/7 free, harder)

- Fly.io: `fly launch` with the included `Dockerfile`, 3 shared VMs free.
- Oracle Cloud Always Free: create a small VPS, install Python, upload
  `bot.py`, run it with `systemd` or `tmux`. Full control, more setup.

## Option 4 — Your own PC (free, only while on)

```
pip install -r requirements.txt
python bot.py
```
Keep the terminal open. Bot goes offline when the PC sleeps / shuts down.

## After it is online

In Discord, run:
```
/setwelcome #welcome
/setlog #mod-log
/ping
/help
```

## Files in this folder

- `bot.py` — the whole bot, single file (213 commands)
- `requirements.txt` — discord.py, python-dotenv, yt-dlp
- `Procfile` — for Railway / Heroku-style hosts
- `railway.json` — Railway deploy config
- `render.yaml` — Render deploy config
- `Dockerfile` — for Fly.io / Docker hosts
- `runtime.txt` — Python 3.12
