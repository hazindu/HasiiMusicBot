# YouTube "Sign in to confirm you're not a bot" විසඳුම (PO Token + WARP)

මේ guide එක `Sign in to confirm you're not a bot` error එක නවත්තන්න හදපු එකක්.
විසඳුමේ කොටස් දෙකයි:

1. **PO token provider (bgutil)** – yt-dlp එකට YouTube ඉල්ලන "proof of origin" token එක automatically හදලා දෙනවා.
2. **Cloudflare WARP** – YouTube traffic එක Cloudflare IP එකක් හරහා යවනවා. එතකොට YouTube එකට ඔයාගේ flag වුණු VPS IP එක පේන්නේ නැහැ.

දෙකම free. Code එකේ ඒවා පාලනය කරන්නේ `.env` එකේ settings දෙකකින්:

| Setting | තේරුම |
|---|---|
| `YT_PROXY` | yt-dlp traffic යවන proxy එක (උදා: `socks5://warp:1080`) |
| `POT_PROVIDER_URL` | bgutil server එකේ address එක (උදා: `http://bgutil-provider:4416`) |

ඔයා bot එක run කරන විදිහට ගැලපෙන කොටස විතරක් කරන්න: **A (Docker)** හෝ **B (Docker නැතුව)**.

---

## A. Docker Compose එකෙන් run කරනවා නම් (පහසුම ක්‍රමය)

`docker-compose.yml` එකට දැනටමත් `bgutil-provider` සහ `warp` services දෙක එකතු කරලා තියෙනවා.
Bot එකට ඒ settings දෙකත් automatically දීලා තියෙනවා. ඒ නිසා `.env` එකේ මොකුත් වෙනස් කරන්න ඕනේ නැහැ.

### 1. අලුත් code එක server එකට ගන්න
```bash
cd ~/HasiiMusicBot        # ඔයාගේ bot folder එක
git pull
```

### 2. Build කරලා start කරන්න
```bash
docker compose up -d --build
```
පළවෙනි පාර WARP එක Cloudflare එකේ register වෙනවා. ඒකට තත්පර 10–20ක් යනවා.

### 3. හැම දෙයක්ම වැඩද කියලා බලන්න
```bash
# containers තුනම "Up" වෙලාද?
docker compose ps

# WARP වැඩද? පෙන්නන output එකේ "warp=on" තියෙන්න ඕනේ
docker compose exec hasii curl -s -x socks5h://warp:1080 https://www.cloudflare.com/cdn-cgi/trace

# bgutil server එක වැඩද? JSON response එකක් එන්න ඕනේ
docker compose exec hasii curl -s http://bgutil-provider:4416/ping
```

### 4. Bot log එක බලන්න
```bash
docker compose logs -f hasii
```
Start වෙද්දී මේ lines දෙක පේන්න ඕනේ:
```
🌐 yt-dlp proxy enabled: socks5://warp:1080
🛡️ PO token provider reachable.
```
`⚠️ PO token provider not reachable` කියලා ආවොත්, step 3 එකේ commands වලින් `bgutil-provider` container එක check කරන්න.

---

## B. Docker නැතුව VPS එකේ කෙළින්ම run කරනවා නම් (`bash start`)

### 1. bgutil server එක run කරන්න
සරලම විදිහ මේ container එක විතරක් Docker එකෙන් run කරන එක:
```bash
docker run -d --name bgutil-provider --restart unless-stopped --init \
  -p 127.0.0.1:4416:4416 brainicism/bgutil-ytdlp-pot-provider:latest
```
> `127.0.0.1:` කියන කොටස අනිවාර්යයි. ඒක නැත්නම් port එක internet එකට open වෙනවා.

### 2. Cloudflare WARP proxy mode එකෙන් install කරන්න (Ubuntu/Debian)
```bash
curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list
sudo apt update && sudo apt install -y cloudflare-warp

warp-cli registration new
warp-cli mode proxy          # සම්පූර්ණ server එකම නෙවෙයි, proxy එකක් විදිහට විතරයි
warp-cli proxy port 40000
warp-cli connect
```
> **`mode proxy` අනිවාර්යයි.** ඒක නැතුව connect කළොත් server එකේ සම්පූර්ණ network එකම WARP හරහා යනවා. එතකොට SSH connection එක කැඩෙන්න පුළුවන්.

Check කරන්න (output එකේ `warp=on` තියෙන්න ඕනේ):
```bash
curl -s -x socks5h://127.0.0.1:40000 https://www.cloudflare.com/cdn-cgi/trace
```

### 3. `.env` එකට මේ lines දෙක එකතු කරන්න
```
YT_PROXY=socks5://127.0.0.1:40000
POT_PROVIDER_URL=http://127.0.0.1:4416
```

### 4. Python packages update කරලා bot එක restart කරන්න
```bash
pip install -U -r requirements.txt
bash start
```
Docker ක්‍රමයේ (A, step 4) වගේම log එකේ ඒ lines දෙක පේන්න ඕනේ.

> yt-dlp ට YouTube වෙනුවෙන් **deno** (JavaScript runtime) එකත් ඕනේ. Dockerfile එක ඒක install කරනවා. Docker නැත්නම් `curl -fsSL https://deno.land/install.sh | sh` run කරලා install කරගන්න.

---

## Cookies ගැන

- Cookies තාමත් පාවිච්චි කරන්න පුළුවන්. ඒත් දැන් ඒවා ගොඩක් වෙලා පවතින්න ඕනේ.
- Cookies මාරු කරන්න ඕනේ වුණොත් bot එක restart කරන්න ඕනේ නැහැ. `/cookies` command එක පාවිච්චි කරන්න (sudo users ලට විතරයි):
  - `.txt` cookie file එකකට reply කරලා `/cookies`
  - `/cookies https://batbin.me/xxxx`
  - `/cookies status`
- **WARP IP එකෙන් cookies එකට login account එක flag වෙන්න පුළුවන්.** ඒ නිසා ඔයාගේ ප්‍රධාන Google account එක නෙවෙයි, spare account එකක cookies විතරක් පාවිච්චි කරන්න.

---

## ප්‍රශ්න ආවොත්

| ලක්ෂණය | කරන්න |
|---|---|
| WARP දැම්මට පස්සෙත් "not a bot" error එක එනවා | WARP IPs ත් සමහර වෙලාවට YouTube block කරනවා. `docker compose restart warp` කරලා බලන්න. ඒත් හරි නොගියොත් `YT_PROXY` එකට ගෙවන residential proxy එකක් දාන්න. |
| `PO token provider not reachable` | bgutil container එක run වෙනවද බලන්න (`docker ps`). `POT_PROVIDER_URL` එකේ address එක හරිද බලන්න. |
| Downloads හෙමින් යනවා | WARP එක හරහා යද්දී ටිකක් හෙමින් යන්න පුළුවන්. ඒක සාමාන්‍ය දෙයක්. |
| bgutil update වුණාට පස්සේ errors | Plugin version එකයි server version එකයි ගැලපෙන්න ඕනේ. `pip install -U bgutil-ytdlp-pot-provider` කරලා `docker pull brainicism/bgutil-ytdlp-pot-provider:latest` කරන්න. |
| ඕනෙම වෙලාවක YouTube වෙනස් වුණොත් | yt-dlp update කරන්න: `pip install -U --force-reinstall "yt-dlp[default] @ git+https://github.com/yt-dlp/yt-dlp.git"` (Docker නම් `docker compose up -d --build`) |
