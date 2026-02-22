import re
from difflib import SequenceMatcher
import json
from pathlib import Path

def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()
def parse_flashcards(text: str) -> dict:
    text = text.strip()

    # Try JSON first
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        else:
            raise ValueError("JSON must be an object {key: value}")
    except json.JSONDecodeError:
        pass  # Fall back to text parsing

    # Fallback: text format
    cards = {}
    lines = text.splitlines()

    for i, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue

        if "::" not in line:
            raise ValueError(f"Line {i} missing '::' separator")

        eng, ru = line.split("::", 1)
        cards[eng.strip()] = ru.strip()

    if not cards:
        raise ValueError("No valid flashcards found")

    return cards

def del_mp3s():
    current_dir = Path.cwd()
    for file_path in Path(current_dir).glob('*.mp3'):
        if file_path.is_file():
            file_path.unlink()  # Use unlink() to delete the file

del_mp3s()