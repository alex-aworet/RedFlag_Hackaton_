# watcher.py
import asyncio
import aiofiles
from mistral import ask
from utils_classification import parse_contents
from main import main_sanction

async def tail_file(file_path: str):
    last_pos = 0
    running = True

    async with aiofiles.open(file_path, 'r') as f:
        while running:
            await f.seek(last_pos)
            new_text = await f.read()
            last_pos = await f.tell()

            if new_text:
                # 1) Demande au modèle
                result = parse_contents(ask(new_text))
                try:
                    valeur = int(result)
                except ValueError:
                    print(f"⚠️ Résultat invalide : {result}")
                    await asyncio.sleep(3)
                    continue

                # 2) Traite un seul score
                running = main_sanction(valeur)

            await asyncio.sleep(3)

async def main():
    file_path = "transcription.txt"  # ton fichier
    await tail_file(file_path)

if __name__ == "__main__":
    asyncio.run(main())
