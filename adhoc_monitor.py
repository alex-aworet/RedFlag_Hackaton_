from scapy.all import AsyncSniffer, UDP, IP
import time, subprocess

IFACE = "en0"
SERVER_PORT = 27312
OFFSET = 1500           # d’après ta capture
PEER_MIN, PEER_MAX = OFFSET, OFFSET + 4000   # fenêtre de 1500–5500 (à ajuster)
# Liste de commandes à lancer (chaque commande est une liste d'arguments)
CMDS = [
    ["your_environment/voice_detection/bin/python",
     "live_voice_detection.py"],
    ["your_environment/voice_detection/bin/python",
     "run.py"]
]
DEBOUNCE = 5
_last = 0

def launch(ctx):
    global _last
    now = time.time()
    if now - _last < DEBOUNCE: return
    # Lancer toutes les commandes de CMDS
    for cmd in CMDS:
        try:
            print("→ Lancement hook:", " ".join(cmd), "| ctx:", ctx)
            subprocess.Popen(cmd)
        except Exception as e:
            print("Erreur en lançant le hook:", e)
    _last = now

def on_pkt(p):
    if UDP not in p or IP not in p: return
    sip, dip = p[IP].src, p[IP].dst
    sport, dport = int(p[UDP].sport), int(p[UDP].dport)
    print(f"[{time.strftime('%H:%M:%S')}] UDP {sip}:{sport} -> {dip}:{dport}")
    launch({"src": sip, "dst": dip, "sport": sport, "dport": dport})

if __name__ == "__main__":
    bpf = f"udp and (port {SERVER_PORT} or portrange {PEER_MIN}-{PEER_MAX})"
    print("Interface:", IFACE)
    print("Filtre BPF:", bpf)
    sniffer = AsyncSniffer(filter=bpf, prn=on_pkt, store=False, iface=IFACE)
    sniffer.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        sniffer.stop()
