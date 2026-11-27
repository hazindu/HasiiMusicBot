<div align="center">

# 🎵 ˹ʜᴀꜱɪɪ ꭙ ᴍᴜꜱɪᴄ˼
### A Modern Telegram Music Bot for High-Quality Voice Chat Streaming

<br>

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
![Repo Views](https://komarev.com/ghpvc/?username=hazindu-HasiiMusicBot&label=Repo%20views&color=0e75b6&style=for-the-badge)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg?style=for-the-badge)](LICENSE)
[![Telegram Support](https://img.shields.io/badge/Telegram-Support-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/Hasindu_Lakshan)

<img src="https://github.com/user-attachments/assets/0a447dfd-961f-4f81-87e1-976392320c49" alt="Hasii Music" width="720" height="auto"/>

Open-source Telegram music bot built with **Python**, **Pyrogram**, **PyTgCalls** and **FFmpeg**.<br>
Delivering fast, reliable and high-quality audio streaming directly to Telegram voice chats.

</div>

---

---

# 📖 About

**˹ʜᴀꜱɪɪ ᴍᴜꜱɪᴄ˼** is a powerful and modern Telegram music bot built for seamless voice chat streaming. It enables users to play music directly in Telegram voice chats using YouTube links, search queries, and live radio stations while offering administrators complete control over playback. Designed with performance, stability, and simplicity in mind, the project combines modern asynchronous technologies to provide a fast, reliable, and highly customizable music streaming experience. Whether you're hosting a small community or managing a large Telegram group, Hasii Music is built to deliver consistent performance with minimal configuration.

---

# ⭐ Why Hasii Music?

Choosing the right Telegram music bot shouldn't mean sacrificing performance, reliability, or ease of deployment. Hasii Music is designed with developers and communities in mind, providing a clean architecture, modern technologies, and powerful features while remaining simple to deploy and maintain.

### Highlights

- 🚀 Fast and lightweight architecture
- 🎵 High-quality voice chat streaming
- 🎧 YouTube search and direct URL playback
- 📻 Built-in live radio support
- 📝 Smart queue management
- 🛡 Powerful administrator controls
- 👥 User authorization system
- 🔄 Automatic voice chat cleanup
- 🐳 Docker and Docker Compose support
- ⚙️ Environment-based configuration
- 📂 Modular and maintainable codebase
- ❤️ Open-source under the GPL-3.0 License

---

# ✨ Features

### 🎵 High-Quality Audio Streaming

Experience smooth and crystal-clear music playback optimized for Telegram voice chats using the Opus codec and FFmpeg.

### 🎧 YouTube Integration

Play music instantly from:

- YouTube links
- Search queries
- Supported playlists

### 📻 Live Radio Streaming

Access and stream a collection of online radio stations directly within Telegram voice chats.

### 📝 Smart Queue Management

Manage playlists effortlessly with a built-in queue system.

- Add songs
- View queue
- Skip tracks
- Clear queue

### ⚡ Optimized Performance

Built with asynchronous libraries for efficient resource usage and responsive performance.

### 🎛 Playback Controls

Complete playback management with support for:

- Play
- Pause
- Resume
- Skip
- Stop
- Seek

### 👥 Authorization System

Restrict playback controls to:

- Chat administrators
- Authorized users
- Bot owner
- Sudo users

### 🔄 Automatic Voice Chat Cleanup

Automatically detects inactive voice chats and leaves them to conserve server resources.

### 🐳 Docker Ready

Deploy effortlessly using Docker or Docker Compose for a consistent production environment.

### 🔧 Easy Configuration

Configure the bot entirely through environment variables without modifying the source code.

---

# 🏗 Tech Stack

| Category | Technology |
|-----------|------------|
| Language | Python 3.10+ |
| Telegram Framework | Pyrogram |
| Voice Chat | PyTgCalls |
| Database | MongoDB |
| Media Processing | FFmpeg |
| Runtime | Deno |
| Containerization | Docker & Docker Compose |
| Version Control | Git |

---

# 📋 Requirements

Before deploying **˹ʜᴀꜱɪɪ ᴍᴜꜱɪᴄ˼**, ensure your system meets the following requirements.

| Software | Version |
|-----------|---------|
| Python | 3.10 or higher |
| FFmpeg | Latest |
| Deno | Latest |
| MongoDB | Atlas or Self-hosted |
| Git | Latest |

### 🔧 Installing Prerequisites (Linux/Ubuntu)

Before starting, install the required runtimes:

```bash
# Install FFmpeg
sudo apt update && sudo apt install ffmpeg -y

# Install Deno
curl -fsSL https://deno.land/x/install/install.sh | sh

```

---

# 🚀 Quick Start

Clone the repository.

```bash
git clone https://github.com/hazindu/HasiiMusicBot.git
```

Move into the project directory.

```bash
cd HasiiMusicBot
```

Install the required dependencies.

```bash
pip install -r requirements.txt
```

Create your environment configuration.

```bash
cp sample.env .env
```

Update the values inside `.env`.


Start the bot in another session.

```bash
bash start
```

---

# ⚙️ Environment Variables

Create a `.env` file in the project's root directory.

```env
# Telegram API
API_ID=
API_HASH=
BOT_TOKEN=

# MongoDB
MONGO_DB_URI=

# Bot Configuration
OWNER_ID=
LOGGER_ID=

# Assistant Account
STRING_SESSION=

# Essential
COOKIE_URL=

# YouTube anti-bot (optional, recommended - see "YouTube Anti-Bot Setup")
YT_PROXY=
POT_PROVIDER_URL=
```

| Variable | Description |
|-----------|-------------|
| `API_ID` | Telegram API ID obtained from **my.telegram.org** |
| `API_HASH` | Telegram API Hash |
| `BOT_TOKEN` | Bot Token received from **@BotFather** |
| `MONGO_DB_URI` | MongoDB connection URI |
| `OWNER_ID` | Telegram User ID of the bot owner |
| `LOGGER_ID` | Group ID used for bot logs |
| `STRING_SESSION` | Pyrogram String Session for the assistant account |
| `COOKIE_URL` | YouTube cookies URL |
| `YT_PROXY` | Proxy used for all yt-dlp traffic, e.g. `socks5://127.0.0.1:1080` (Cloudflare WARP) |
| `POT_PROVIDER_URL` | URL of the bgutil PO token server, e.g. `http://127.0.0.1:4416` |

---

# 🛠 Installation

## Local Installation

Clone the repository.

```bash
git clone https://github.com/hazindu/HasiiMusicBot.git
```

Enter the project directory.

```bash
cd HasiiMusicBot
```

Install Python dependencies.

```bash
pip install -r requirements.txt
```

Create the environment file.

```bash
cp sample.env .env
```

Configure all required environment variables.


Start the bot.

```bash
bash start
```

---

## YouTube Anti-Bot Setup

YouTube often answers server IPs with *"Sign in to confirm you're not a bot"*. Cookies alone only help until the IP gets flagged again, so the bot supports two free helpers:

- **PO token provider (bgutil)** generates the proof-of-origin tokens YouTube expects from yt-dlp.
- **Cloudflare WARP** sends YouTube traffic through a Cloudflare IP instead of your flagged server IP.

Both are optional. When `YT_PROXY` and `POT_PROVIDER_URL` are empty the bot behaves as before.

### Docker Compose

`docker-compose.yml` already starts both helpers and passes the right settings to the bot. No `.env` changes are needed. Do **not** put `127.0.0.1` values for these two variables in `.env` when using Compose; inside a container that address is the bot itself.

### Running the bot without Compose (venv + tmux)

Install Docker (only the helpers run in it).

```bash
curl -fsSL https://get.docker.com | sh
```

Start the helper containers. Both listen on `127.0.0.1` only, so they are not exposed to the internet, and `--restart unless-stopped` brings them back after a reboot.

```bash
docker run -d --name warp --restart unless-stopped \
  --device-cgroup-rule 'c 10:200 rwm' -e WARP_SLEEP=2 \
  --cap-add MKNOD --cap-add AUDIT_WRITE --cap-add NET_ADMIN \
  --sysctl net.ipv6.conf.all.disable_ipv6=0 \
  --sysctl net.ipv4.conf.all.src_valid_mark=1 \
  -v /root/warp-data:/var/lib/cloudflare-warp \
  -p 127.0.0.1:1080:1080 caomingjun/warp:latest

docker run -d --name bgutil-provider --restart unless-stopped --init --net=host \
  brainicism/bgutil-ytdlp-pot-provider:latest --host 127.0.0.1
```

> **Why `--net=host` for bgutil:** the bot passes its proxy (`socks5://127.0.0.1:1080`) to the PO token server, which uses it for its own requests to YouTube. In a normal container `127.0.0.1` is the container itself, so token generation fails. With the host network, `127.0.0.1:1080` reaches WARP, and `--host 127.0.0.1` keeps port 4416 private.

Check that both work (wait about 20 seconds after the first start). The last command asks for a real PO token through WARP and should print JSON with a `poToken` field.

```bash
curl -s -x socks5h://127.0.0.1:1080 https://www.cloudflare.com/cdn-cgi/trace | grep warp   # warp=on
curl -s http://127.0.0.1:4416/ping                                                         # JSON reply
curl -s -X POST http://127.0.0.1:4416/get_pot -H 'Content-Type: application/json' \
  -d '{"proxy":"socks5://127.0.0.1:1080"}'                                                  # {"poToken":...}
```

Add the settings to `.env`.

```env
YT_PROXY=socks5://127.0.0.1:1080
POT_PROVIDER_URL=http://127.0.0.1:4416
```

Update the dependencies and start the bot. yt-dlp also needs Deno for YouTube.

```bash
pip install -U -r requirements.txt
export PATH="$HOME/.deno/bin:$PATH"
bash start
```

On startup the log should show `yt-dlp proxy enabled` and, a few seconds later, `PO token provider working (test token generated)`. yt-dlp warnings about PO tokens, cookies or the proxy also appear in the log, which shows why a download was blocked.

### Starting the bot after a server reboot

The helper containers restart on their own. Check them, then start the bot in tmux.

```bash
docker ps                      # warp and bgutil-provider should be Up
tmux new -s HasiiMusic         # or: tmux attach-session -t HasiiMusic
cd ~/HasiiMusicBot
source hasiimusic/bin/activate
export PATH="$HOME/.deno/bin:$PATH"
bash start
```

Detach with `Ctrl+B`, then `D`. Do not re-run the `docker run` commands; the containers already exist (use `docker start warp bgutil-provider` if they are stopped).

### Updating cookies without a restart

Owners can replace the YouTube cookies while the bot is running (see `/cookies` under Owner Commands). Use cookies from a spare Google account, exported from a private window, and close that window without browsing further so they last longer.

---

## Docker

Build the Docker image.

```bash
docker build -t hasiimusicbot:latest .
```

Run the container.

```bash
docker run -d \
  --restart unless-stopped \
  --env-file .env \
  -v ./HasiiMusic/cookies:/app/HasiiMusic/cookies \
  -v ./downloads:/app/downloads \
  --name hasiimusicbot \
  hasiimusicbot:latest
```

---

## Docker Compose

Deploy using Docker Compose.

```bash
docker compose up -d --build
```

View container logs.

```bash
docker compose logs -f
```

Stop the services.

```bash
docker compose down
```

Restart the services.

```bash
docker compose restart
```

---

# 📖 Commands

## 👤 User Commands

| Command | Description |
|---------|-------------|
| `/play <song/url>` | Play a song from a YouTube URL or search query |
| `/radio` | Browse available radio stations |
| `/queue` | Display the current music queue |
| `/ping` | Check the bot's latency and status |
| `/help` | Show the help menu |

---

## 🛡 Admin Commands

| Command | Description |
|---------|-------------|
| `/pause` | Pause the current playback |
| `/resume` | Resume playback |
| `/skip` | Skip the current track |
| `/next` | Play the next track in the queue |
| `/stop` | Stop playback |
| `/end` | Stop playback and clear the queue |
| `/seek <time>` | Seek to a specific timestamp |
| `/reload` | Reload administrator cache |

---

## 👑 Owner Commands

| Command | Description |
|---------|-------------|
| `/stats` | Display bot statistics |
| `/broadcast` | Broadcast a message to all served chats |
| `/addsudo` | Add a sudo user |
| `/rmsudo` | Remove a sudo user |

| `/maintenance` | Enable or disable maintenance mode |
| `/restart` | Restart the bot |
| `/logs` | Retrieve the latest bot logs |
| `/cookies` | Replace YouTube cookies without restarting: reply to a `.txt` file, pass a paste URL, re-download from `COOKIE_URL`, or use `/cookies status` |

---

# 📂 Project Structure

```text
HasiiMusicBot/
├── HasiiMusic/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cookies/
│   ├── core/
│   ├── helpers/
│   ├── locales/
│   └── plugins/
│
├── config.py
├── sample.env
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── setup
├── start
├── LICENSE
└── Readme.md
```

---

# 🤝 Contributing

Contributions are welcome and greatly appreciated.

Whether you're fixing bugs, improving documentation, optimizing performance, or adding new features, your contributions help make **˹ʜᴀꜱɪɪ ᴍᴜꜱɪᴄ˼** better for everyone.

Please read the [CONTRIBUTING.md](CONTRIBUTING.md) guide before opening an issue or submitting a pull request.

---

# 📞 Support

Need help with deployment or encountered an issue?

Feel free to reach out through the following platforms.

| Platform | Link |
|----------|------|
| 💻 GitHub Repository | https://github.com/hazindu/HasiiMusicBot |
| 📢 Telegram Channel | https://t.me/TheInfinityAI |
| 💬 Telegram Support | https://t.me/Hasindu_Lakshan |

If you discover a bug, please open a GitHub Issue with detailed information so it can be reproduced and fixed quickly.

---

# 🙏 Credits

This project would not have been possible without the amazing open-source community.

Special thanks to:

- **[Anony](https://github.com/AnonymousX1025)** — Inspiration for the original project.
- **[Pyrogram](https://github.com/pyrogram/pyrogram)** — Telegram MTProto framework.
- **[PyTgCalls](https://github.com/pytgcalls/pytgcalls)** — Telegram voice chat streaming library.
- **[FFmpeg](https://ffmpeg.org/)** — Audio processing and transcoding.

Thank you to everyone who has contributed through code, bug reports, feature suggestions, testing, and community support.

---

# 📄 License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.

You are free to use, modify, and distribute this software. However, any derivative works must also be open-source and released under the exact same license. 

For more information, see the [LICENSE](LICENSE) file.

---

<div align="center">

## ⭐ Support the Project

If you find **˹ʜᴀꜱɪɪ ᴍᴜꜱɪᴄ˼** useful, consider giving this repository a ⭐ on GitHub.

Your support helps increase the project's visibility and encourages future development.

<br>

**Made with ❤️ by <a href="https://github.com/hazindu">Hasindu Nagolla</a>**

</div>
