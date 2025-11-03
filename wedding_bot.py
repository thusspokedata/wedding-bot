#!/usr/bin/env python3
import os, sys, time, signal, threading, requests
from meshtastic.serial_interface import SerialInterface
from pubsub import pub

# === Configuration ===
PORT       = os.environ.get("MESH_PORT", "/dev/ttyUSB0")    # LoRa serial port
BOT        = os.environ.get("BOT_NAME", "wedding-bot")      # Bot name
PUBLIC_CH  = int(os.environ.get("PUBLIC_CH", "1"))          # Public channel index
PFX        = "!"                                            # Optional command prefix (bot also works without it)
t0         = time.time()
LOCK       = threading.Lock()
IF         = None

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

    # === Determine command (with or without prefix) ===
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
        elif "help" in text_lower or "hilfe" in text_lower:
            cmd = "help"

    if not cmd:
        return  # ignore unrelated chat

    # === Execute command ===
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
    elif cmd == "help":
        reply = "Commands: ping, echo <text>, uptime, id, btc, help"
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

    try:
        send("🤖 wedding-bot is online. Type 'help' for commands.", "^all", PUBLIC_CH)
    except Exception:
        pass

    def goodbye(*_):
        try:
            send("👋 wedding-bot is going offline. See you soon!", "^all", PUBLIC_CH)
        except Exception:
            pass
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
