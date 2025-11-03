cat > ~/wedding_bot.py <<'PY'
#!/usr/bin/env python3
import os, sys, time, signal, threading, requests
from meshtastic.serial_interface import SerialInterface
from pubsub import pub

# === Configuration ===
PORT       = os.environ.get("MESH_PORT", "/dev/ttyUSB0")    # LoRa serial port
BOT        = os.environ.get("BOT_NAME", "wedding-bot")      # Bot name
PUBLIC_CH  = int(os.environ.get("PUBLIC_CH", "1"))          # Public channel index
PFX        = "!"
t0         = time.time()
LOCK       = threading.Lock()
IF         = None

# === Runtime telemetry store ===
TELEMETRY = {}

# === Newsdata API key (set NEWSDATA_KEY env var) ===
NEWSDATA_KEY = os.environ.get("NEWSDATA_KEY", "")

# === Helper: uptime formatter ===
def human_uptime():
    s = int(time.time() - t0)
    d, s = divmod(s, 86400); h, s = divmod(s, 3600); m, s = divmod(s, 60)
    return (f"{d}d " if d else "") + f"{h}h {m}m {s}s"

# === Helper: send message safely ===
def send(txt, dest, ch):
    """Send a text to either broadcast (^all) or a private node (!nodeid)."""
    with LOCK:
        IF.sendText(txt, destinationId=dest, channelIndex=ch)

# === Helper: get BTC price ===
def btc_price():
    """Fetch current Bitcoin price in USD using CoinGecko API."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            timeout=5
        )
        r.raise_for_status()
        price = r.json()["bitcoin"]["usd"]
        return f"₿ BTC/USD: ${price:,.2f}"
    except Exception:
        return "⚠️ Unable to fetch BTC price (no internet or API error)"

# === Helper: get latest telemetry summary ===
def traffic_status():
    """Return a short summary of channel utilization and airUtilTx."""
    if not TELEMETRY:
        return "📡 No telemetry yet."
    last = list(TELEMETRY.values())[-1]
    air = last.get("airUtilTx", 0)
    util = last.get("channelUtilization", 0)
    return f"📊 Channel use: tx={air:.2f}%, util={util:.2f}%"

# === Helper: live weather for Wedding (Open-Meteo) ===
def weather_now():
    """Fetch current T/RH for Wedding via Open-Meteo."""
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=52.55075&longitude=13.373845&current=temperature_2m,relative_humidity_2m",
            timeout=5
        )
        r.raise_for_status()
        cur = r.json().get("current", {})
        t = cur.get("temperature_2m")
        h = cur.get("relative_humidity_2m")
        if t is None or h is None:
            return "🌦️ weather unavailable"
        return f"🌡️ {t:.1f}°C  💧{h:.0f}%  (Wedding)"
    except Exception:
        return "🌦️ weather fetch error"

# === Helper: short news via newsdata.io (≤200 chars) ===
def newsdata_headlines(query="berlin"):
    if not NEWSDATA_KEY:
        return "🗞️ set NEWSDATA_KEY first"
    try:
        url = (
            "https://newsdata.io/api/1/news"
            f"?apikey={NEWSDATA_KEY}&q={requests.utils.quote(query)}"
            "&language=de,en&country=de"
        )
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        results = r.json().get("results", [])[:3]
        titles = [a.get("title","").strip() for a in results if a.get("title")]
        if not titles:
            return "🗞️ no recent headlines"
        text = " • ".join(titles)
        return text[:200] + ("…" if len(text) > 200 else "")
    except Exception:
        return "⚠️ news unavailable"

# === Handle telemetry packets ===
def on_telemetry(packet=None, interface=None, **kwargs):
    """Keep the last telemetry packet for reporting channel usage."""
    d = packet.get("decoded", {}) if packet else {}
    t = d.get("telemetry", {}).get("deviceMetrics", {})
    n = packet.get("fromId") if packet else None
    if t and n:
        TELEMETRY[n] = t

# === Core message handler ===
def on_text(packet=None, interface=None, **kwargs):
    """Handle every incoming text message and decide if we should reply."""
    if not packet:
        return
    d = packet.get("decoded", {}) or {}
    t = d.get("text")
    if isinstance(t, (bytes, bytearray)):
        t = t.decode("utf-8", "ignore")
    if not t:
        return

    from_id = packet.get("fromId")
    to_id   = packet.get("toId")
    ch      = packet.get("channel", 0)
    is_broadcast = (to_id == "^all")

    # Only reply publicly if broadcast came on PUBLIC_CH.
    # For any other channel (e.g. private), force DM even if user sent broadcast.
    reply_public = (is_broadcast and ch == PUBLIC_CH)

    text_lower = t.lower().strip()
    cmd, arg = None, ""

    # Determine command (with or without prefix)
    if text_lower.startswith(PFX):
        parts = text_lower[len(PFX):].split(maxsplit=1)
        cmd = parts[0] if parts else ""
        arg = parts[1] if len(parts) > 1 else ""
    else:
        if text_lower.startswith("ping"):
            cmd = "ping"
        elif text_lower.startswith("echo"):
            cmd = "echo"; arg = text_lower[5:] if len(text_lower) > 5 else ""
        elif "uptime" in text_lower:
            cmd = "uptime"
        elif text_lower.strip() == "id" or "who" in text_lower:
            cmd = "id"
        elif "btc" in text_lower or "bitcoin" in text_lower:
            cmd = "btc"
        elif "traffic" in text_lower:
            cmd = "traffic"
        elif "weather" in text_lower or "wetter" in text_lower:
            cmd = "weather"
        elif text_lower.startswith("news") or "nachrichten" in text_lower:
            cmd = "news"
            try:
                arg = text_lower.split(maxsplit=1)[1]
            except IndexError:
                arg = "berlin"
        elif "help" in text_lower or "hilfe" in text_lower:
            cmd = "help"

    if not cmd:
        return  # ignore unrelated chat

    # Execute command
    if cmd == "ping":
        reply = "pong 🏓"
    elif cmd == "uptime":
        reply = f"Laufzeit: {human_uptime()}"
    elif cmd == "id":
        reply = f"Bot: {BOT}"
    elif cmd == "echo":
        reply = f"echo: {arg or 'kein Text'}"
    elif cmd == "btc":
        reply = btc_price()
    elif cmd == "traffic":
        reply = traffic_status()
    elif cmd == "weather":
        reply = weather_now()
    elif cmd == "news":
        reply = newsdata_headlines(arg or "berlin")
    elif cmd == "help":
        reply = "Commands: ping, echo <text>, uptime, id, btc, traffic, weather, news <q>, help"
    else:
        reply = "Unknown command. Try 'help'."

    # If not PUBLIC_CH, reply by DM; only broadcast on PUBLIC_CH.
    dest = "^all" if reply_public else from_id
    send(reply, dest, ch)

# === Bot entry point ===
def main():
    global IF
    IF = SerialInterface(devPath=PORT, debugOut=False)
    pub.subscribe(on_text, "meshtastic.receive.text")
    pub.subscribe(on_telemetry, "meshtastic.receive.telemetry")

    #try:
    #    send("🤖 wedding-bot is online. Tippe 'help' für Befehle.", "^all", PUBLIC_CH)
    #except Exception:
    #    pass

    def goodbye(*_):
        #try:
        #    send("👋 wedding-bot geht schlafen. Bis bald.", "^all", PUBLIC_CH)
        #except Exception:
        #    pass
        try:
            IF.close()
        finally:
            sys.exit(0)

    signal.signal(signal.SIGINT, goodbye)
    signal.signal(signal.SIGTERM, goodbye)

    while True:
        time.sleep(0.5)

if __name__ == "__main__":
    main()
PY
chmod +x ~/wedding_bot.py