import os
import sys
import time
import json
import queue
import tempfile
from collections import deque
from datetime import datetime

import sounddevice as sd
import soundfile as sf
import numpy as np
import webrtcvad
import replicate
from dotenv import dotenv_values

# === À PERSONNALISER ===
OUTPUT_TXT = "transcription.txt"
SAMPLE_RATE = 16000                 # webrtcvad exige 8/16/32/48 kHz. On utilise 16 kHz.
DEVICE = None                       # None = micro par défaut
LANGUAGE = "french"
MODEL_REF = "vaibhavs10/incredibly-fast-whisper:3ab86df6c8f54c11309d4d1f930ac292bad43ace52d10c80d87eb258b3c9f79c"

# === Paramètres VAD (webrtcvad) ===
VAD_AGGRESSIVENESS = 2              # 0..3 (3 = plus agressif/strict)
FRAME_MS = 20                       # 10/20/30 ms autorisés par webrtcvad
MIN_SPEECH_MS = 200                 # durée minimale “voix” pour déclencher parole
MIN_SILENCE_MS = 600                # silence pour considérer la fin de l’énoncé
PREROLL_MS = 200                    # audio conservé avant le déclenchement (ne pas couper l’attaque)
POST_PAD_MS = 150                   # petit pad en fin (stabilité des modèles)
MAX_UTTERANCE_SECONDS = 120         # flush forcé si trop long (conf/conf call)

# --- Astuce périphériques ---
if "--list" in sys.argv:
    print(sd.query_devices())
    sys.exit(0)

# --- Auth Replicate via .env ---
config = dotenv_values(".env")
REPLICATE_API_TOKEN = config.get("REPLICATE_API_TOKEN")
replicate_client = None
if REPLICATE_API_TOKEN:
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
    replicate_client = replicate.Client(api_token=REPLICATE_API_TOKEN)

# File thread-safe pour récupérer l'audio depuis le callback
audio_q = queue.Queue()

def audio_callback(indata, frames, time_info, status):
    if status:
        print(f"[audio] {status}", file=sys.stderr)
    # indata est bytes (int16 mono) avec RawInputStream
    audio_q.put(bytes(indata))

def write_wav_tmp(audio_np_i16, samplerate):
    """Écrit un wav mono à partir d'un np.int16 (shape [N,1]) et renvoie le chemin."""
    # convertit en float32 -1..1 pour soundfile, sortie PCM_16
    audio_f32 = (audio_np_i16.astype(np.float32) / 32768.0)
    fd, path = tempfile.mkstemp(prefix="utt_", suffix=".wav")
    os.close(fd)
    sf.write(path, audio_f32, samplerate, subtype="PCM_16")
    return path

def transcribe_with_replicate(wav_path):
    base_inputs = {"audio": open(wav_path, "rb"), "language": LANGUAGE}
    runner = replicate_client.run if replicate_client else replicate.run
    try:
        inputs1 = dict(base_inputs)
        inputs1["task"] = "transcribe"
        out = runner(MODEL_REF, input=inputs1)
    except Exception:
        out = runner(MODEL_REF, input=base_inputs)

    text = ""
    if isinstance(out, str):
        text = out
    elif isinstance(out, dict):
        if isinstance(out.get("text"), str):
            text = out["text"]
        elif isinstance(out.get("segments"), list):
            text = " ".join(seg.get("text", "") for seg in out["segments"])
    elif isinstance(out, list):
        if all(isinstance(x, str) for x in out):
            text = " ".join(out)
        else:
            parts = []
            for x in out:
                if isinstance(x, dict) and "text" in x:
                    parts.append(x["text"])
            text = " ".join(parts)
    return (text or "").strip()

def main():
    print("Initialisation écoute micro + VAD (webrtcvad) + envoi complet par prise de parole…")
    if MODEL_REF.endswith(":latest"):
        print(f"ℹ️ MODELE: {MODEL_REF} (pense à figer une version :owner/model:hash)")

    # journal
    with open(OUTPUT_TXT, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 80 + "\n")
        f.write(f"Session démarrée: {datetime.now().isoformat(timespec='seconds')}\n")
        f.write("=" * 80 + "\n")

    # tailles
    assert FRAME_MS in (10, 20, 30), "webrtcvad supporte des frames de 10/20/30 ms"
    bytes_per_sample = 2  # int16
    frame_bytes = int(SAMPLE_RATE * (FRAME_MS / 1000.0)) * bytes_per_sample  # ex: 320 * 2 = 640
    min_speech_frames = int(np.ceil(MIN_SPEECH_MS / FRAME_MS))
    min_silence_frames = int(np.ceil(MIN_SILENCE_MS / FRAME_MS))
    preroll_frames = int(np.ceil(PREROLL_MS / FRAME_MS))
    post_pad_samples = int(SAMPLE_RATE * (POST_PAD_MS / 1000.0))
    max_utt_samples = SAMPLE_RATE * MAX_UTTERANCE_SECONDS

    # VAD
    vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)

    # buffers
    preroll = deque(maxlen=preroll_frames)  # bytes frames
    current_frames = []                     # bytes frames de l’énoncé en cours
    leftover_bytes = b""                    # bytes restants d’un bloc à l’autre

    # états
    in_speech = False
    voice_cnt = 0
    silence_cnt = 0

    # On choisit un blocksize multiple de frame_bytes pour limiter les découpes
    # Pour RawInputStream, blocksize est en frames (échantillons), pas en bytes.
    # Prenons ~100 ms par bloc → (SAMPLE_RATE * 0.1) frames
    blocksize_frames = int(SAMPLE_RATE * 0.1)  # ~100 ms

    print("Micro en écoute. Parle normalement.")
    print("Ctrl+C pour arrêter. Utilise --list pour voir/choisir un micro spécifique.\n")

    def flush_utterance():
        nonlocal current_frames
        if not current_frames:
            return
        # concatène toutes les frames bytes -> np.int16 mono shape [N,1]
        pcm = b"".join(current_frames)
        current_frames = []
        # post pad (silence)
        if post_pad_samples > 0:
            pcm += (b"\x00\x00") * post_pad_samples

        audio_np = np.frombuffer(pcm, dtype=np.int16).reshape(-1, 1)
        if audio_np.size == 0:
            return

        wav_path = write_wav_tmp(audio_np, SAMPLE_RATE)
        try:
            print("\n⏫ Envoi de l’énoncé à Whisper…")
            text = transcribe_with_replicate(wav_path)
            if text:
                print(f"📝 {text}")
                with open(OUTPUT_TXT, "a", encoding="utf-8") as f:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    f.write(f"[{timestamp}] {text}\n")
            else:
                print("… (aucun texte détecté)")
        except Exception as e:
            print(f"❌ Erreur Replicate: {e}", file=sys.stderr)
        finally:
            try:
                os.remove(wav_path)
            except OSError:
                pass

    with sd.RawInputStream(samplerate=SAMPLE_RATE,
                           blocksize=blocksize_frames,
                           device=DEVICE,
                           dtype="int16",
                           channels=1,
                           callback=audio_callback):
        try:
            while True:
                data = audio_q.get()
                if not data:
                    continue

                # Préfixe avec les restes pour reformer des frames exactes
                data = leftover_bytes + data
                total_len = len(data)

                # Nombre de frames complètes disponibles
                n_full = total_len // frame_bytes
                end = n_full * frame_bytes

                # Reste conservé pour le prochain tour
                leftover_bytes = data[end:]

                # Itère sur chaque frame complète
                for i in range(n_full):
                    start = i * frame_bytes
                    fr_bytes = data[start:start + frame_bytes]

                    # VAD attend PCM16 mono little-endian
                    is_speech = vad.is_speech(fr_bytes, SAMPLE_RATE)

                    if not in_speech:
                        # accumule en preroll
                        preroll.append(fr_bytes)
                        if is_speech:
                            voice_cnt += 1
                        else:
                            voice_cnt = 0
                        if voice_cnt >= min_speech_frames:
                            # déclenche la parole
                            in_speech = True
                            silence_cnt = 0
                            current_frames = list(preroll)
                            preroll.clear()
                            current_frames.append(fr_bytes)
                    else:
                        # en parole
                        current_frames.append(fr_bytes)

                        # garde-fou durée max
                        utt_samples = (len(b"".join(current_frames)) // bytes_per_sample)
                        if utt_samples >= max_utt_samples:
                            print("ℹ️ Limite d’énoncé atteinte, flush forcé.")
                            in_speech = False
                            voice_cnt = 0
                            silence_cnt = 0
                            flush_utterance()
                            continue

                        if is_speech:
                            silence_cnt = 0
                        else:
                            silence_cnt += 1
                            if silence_cnt >= min_silence_frames:
                                # fin d’énoncé
                                in_speech = False
                                voice_cnt = 0
                                silence_cnt = 0
                                flush_utterance()

        except KeyboardInterrupt:
            print("\nArrêt demandé. Finalisation…")
            if current_frames:
                flush_utterance()
            print(f"Transcription sauvegardée dans: {OUTPUT_TXT}")
        except Exception as e:
            print(f"\nErreur: {e}", file=sys.stderr)
            time.sleep(0.5)

if __name__ == "__main__":
    main()
