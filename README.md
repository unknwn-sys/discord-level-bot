# Discord Level Bot

A production-ready Discord leaderboard and leveling bot built with Python, `discord.py`, PostgreSQL, `asyncpg`, and Pillow. The bot is designed for active Discord communities that need persistent progression, polished rank surfaces, automatic leaderboard posting, and safe database migrations.
- Hourly automatic leaderboard posting to an optional configured channel
 Hourly automatic leaderboard posting to an optional configured channel
 Level-up announcements sent only to a dedicated bot commands channel
- PostgreSQL persistence with startup-safe schema migration for existing databases

## Architecture

- [bot.py](/home/ben/Desktop/discord-level-bot/bot.py): bot lifecycle, logging, database setup, and cog loading
- [config.py](/home/ben/Desktop/discord-level-bot/config.py): environment-driven runtime configuration including the level cap and hourly leaderboard channel
- [database/db.py](/home/ben/Desktop/discord-level-bot/database/db.py): asyncpg database access, startup migrations, and XP update flows
- [cogs](/home/ben/Desktop/discord-level-bot/cogs): Discord event listeners, slash commands, and background tasks
- [utils](/home/ben/Desktop/discord-level-bot/utils): XP math, cooldown tracking, embeds, and rank card rendering

## XP Progression

- Maximum level: `50`
- Level threshold formula: `total_xp_required = (5 * level^2) + (50 * level) + 100`
- Message XP by level:
  - Level 1: `1 XP`
  - Level 2: `2 XP`
  - Level 3: `3 XP`
  - Continue scaling up to level 10
5. Optionally set `BOT_COMMANDS_CHANNEL_ID` for level-up announcements and `LEADERBOARD_CHANNEL_ID` for hourly leaderboard posts.
  - Level 10 and above: `10 XP`
- Message XP cooldown: `60 seconds`
3. Set `DISCORD_TOKEN`, `DATABASE_URL`, and optional config vars like `BOT_COMMANDS_CHANNEL_ID` and `LEADERBOARD_CHANNEL_ID`.
- Daily message XP cap: `200 XP`
- Voice XP and daily reward XP bypass the daily message XP cap

## Project Structure

```text
discord-level-bot/
├── assets/
│   └── rankcard/
├── cogs/
│   ├── __init__.py
│   ├── leaderboard.py
│   ├── leveling.py
│   ├── profile.py
│   └── rewards.py
├── database/
│   ├── __init__.py
│   ├── db.py
│   └── schema.sql
├── utils/
│   ├── __init__.py
│   ├── cooldown.py
│   ├── embeds.py
│   ├── rankcard.py
│   └── xp.py
├── .env.example
├── .gitignore
├── bot.py
├── config.py
├── Procfile
├── README.md
├── requirements.txt
└── runtime.txt
```

## Installation

1. Create and activate a Python 3.13 virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env`.
4. Set `DISCORD_TOKEN` and `DATABASE_URL`.
5. Optionally set `LEADERBOARD_CHANNEL_ID` for hourly leaderboard posts.
6. Start the bot with `python bot.py`.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | Yes | Discord bot token |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `COMMAND_PREFIX` | No | Legacy prefix, default `!` |
| `XP_COOLDOWN` | No | Message XP cooldown in seconds, default `60` |
| `DAILY_REWARD` | No | Daily reward XP, default `100` |
| `DAILY_XP_CAP` | No | Daily message XP cap, default `200` |
| `MAX_LEVEL` | No | Level cap, default `50` |
| `VOICE_XP_REWARD` | No | Voice XP granted per interval, default `10` |
| `VOICE_XP_INTERVAL_MINUTES` | No | Voice XP interval length, default `5` |
| `LEADERBOARD_CHANNEL_ID` | No | Channel ID for hourly leaderboard posting |
| `EMBED_COLOR` | No | Embed accent color as an integer or hex literal |

## Database Setup

The schema lives in [database/schema.sql](/home/ben/Desktop/discord-level-bot/database/schema.sql). On startup the bot creates missing tables and safely adds any new columns required for updated features like daily message XP tracking. Existing data is preserved.

## Commands

- `/rank [user]`: View level, total XP, XP needed for next level, rank, and daily XP usage
- `/rankcard [user]`: Generate a rank card with XP and daily progress
- `/profile`: View level, XP, rank, messages, voice minutes, daily streak, and daily XP progress
- `/leaderboard`: View the top 10 XP earners with ranked fields
- `/daily`: Claim a daily XP reward every 24 hours

## Automatic Leaderboard Posting

Set `LEADERBOARD_CHANNEL_ID` to a valid text channel ID to enable daily leaderboard embeds. The task runs at 00:00 UTC (GMT+00:00). The task starts automatically when the bot is ready, handles missing channels safely, and logs posting failures.

## Neon PostgreSQL Setup

1. Create a Neon project and database.
2. Copy the PostgreSQL connection string with `sslmode=require`.
3. Set it as `DATABASE_URL` locally and in Heroku.
4. Start the bot once so it can apply the schema and migrations.

## Heroku Deployment

1. Create a Heroku app.
2. Provision Heroku Postgres or use Neon.
3. Set `DISCORD_TOKEN`, `DATABASE_URL`, and optional config vars like `LEADERBOARD_CHANNEL_ID`.
4. Connect the repository or push with Git.
5. Deploy the app.
6. Scale the worker dyno using the included [Procfile](/home/ben/Desktop/discord-level-bot/Procfile).

## Troubleshooting

- If slash commands do not appear, confirm the bot was invited with `applications.commands` and wait for global command sync.
- If rank cards fail, verify Pillow is installed and the bot can fetch member avatars.
- If the daily leaderboard does not post, confirm `LEADERBOARD_CHANNEL_ID` is valid and the bot can send messages in that channel.
- If the bot stops awarding message XP, check whether the user has hit the 200 XP daily message cap or the level 50 cap.

## License

© r2026 Rynex Security

[Visit Rynex Security](https://rynexsecurity.com)
