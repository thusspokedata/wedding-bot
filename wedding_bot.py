#!/usr/bin/env python3
import os, sys, time, signal, threading
from meshtastic.serial_interface import SerialInterface
from pubsub import pub

PORT       = os.environ.get("MESH_PORT", "/dev/ttyUSB0")
BOT        = os.environ.get("BOT_NAME", "wedding-bot")
PUBLIC_CH  = int(os.environ.get("PUBLIC_CH", "1"))  # canal público (1)
PFX        = "!"
t0         = time.time()
LOCK       = threading.Lock()
IF         = None

def human_uptime():
    s = int(time.time() - t0)
    d, s = divmod(s, 86400); h, s = divmod(s, 3600); m, s = divmod(s, 60)
    return (f"{d}d " if d else "") + f"{h}h {m}m {s}s"

def send(txt, dest, ch):
    # dest: '^all' (broadcast) o '!nodeid' (DM) — nunca None
    with LOCK:
        IF.sendText(txt, destinationId=dest, channelIndex=ch)

def on_text(packet=None, interface=None, **kwargs):
    # packet/interface son los nombres que publica meshtastic.receive.text
    if not packet: 
        return
    d = packet.get("decoded", {}) or {}
    t = d.get("text")
    if isinstance(t, (bytes, bytearray)):
        t = t.decode("utf-8", "ignore")
    if not t or not t.startswith(PFX):
        return

    from_id = packet.get("fromId")
    to_id   = packet.get("toId")
    ch      = packet.get("channel", 0)  # índice del canal del mensaje
    is_broadcast = (to_id == "^all")

    # Solo contestar en el canal público si es broadcast; DM en cualquier canal
    if is_broadcast and ch != PUBLIC_CH:
        return

    cmd, *args = t[len(PFX):].strip().split(maxsplit=1)
    arg = args[0] if args else ""
    reply = {
        "ping":   "pong 🏓",
        "uptime": f"Laufzeit: {human_uptime()}",
        "id":     f"Bot: {BOT}",
        "help":   "Befehle: !ping, !echo <text>, !uptime, !id, !help",
    }.get(cmd.lower())
    if cmd.lower() == "echo":
        reply = f"echo: {arg or 'kein Text'}"
    if reply is None:
        reply = "Unbekannter Befehl. !help"

    dest = from_id if not is_broadcast else "^all"
    send(reply, dest, ch)

def main():
    global IF
    IF = SerialInterface(devPath=PORT, debugOut=False)
    pub.subscribe(on_text, "meshtastic.receive.text")
    try:
        send("wedding-bot ist online. Tippe !help", "^all", PUBLIC_CH)
    except Exception:
        pass

    def goodbye(*_):
        try:
            send("wedding-bot geht schlafen. Bis bald.", "^all", PUBLIC_CH)
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
