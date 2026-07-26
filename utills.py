import re
from difflib import SequenceMatcher
from typing import Optional, Tuple
import json
from pathlib import Path
import pandas as pd
import numpy as np
import unicodedata



def normalize(text: str) -> str:
    """
    Normalizes text before local comparison.

    - Unicode normalization
    - Lowercase
    - Removes punctuation
    - Collapses repeated whitespace
    """
    text = unicodedata.normalize("NFKC", text or "")
    text = text.casefold()
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)

    return text.strip()
def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()
def local_answer_evaluation(
    user_answer: str,
    correct_answer: str,
) -> Optional[Tuple[bool, float]]:
    """
    Evaluates only cases that are safe to decide without AI.

    Returns:
        (is_acceptable, score) when the result is safe locally.
        None when semantic AI evaluation is needed.
    """
    normalized_user = normalize(user_answer)
    normalized_correct = normalize(correct_answer)

    if not normalized_user:
        return False, 0.0

    # Exact answer after punctuation, case and whitespace normalization.
    if normalized_user == normalized_correct:
        return True, 1.0

    user_words = normalized_user.split()
    correct_words = normalized_correct.split()

    # Only attempt typo handling when the number of words is identical.
    # Word omissions, additions and reordered words must be checked semantically.
    if len(user_words) != len(correct_words):
        return None

    differing_pairs = [
        (user_word, correct_word)
        for user_word, correct_word in zip(user_words, correct_words)
        if user_word != correct_word
    ]

    # More than one changed word is too uncertain for local approval.
    if len(differing_pairs) != 1:
        return None

    user_word, correct_word = differing_pairs[0]

    # Avoid treating very short words as typos.
    # Example: "я" and "ты" are both short but semantically different.
    if len(user_word) < 4 or len(correct_word) < 4:
        return None

    word_similarity = SequenceMatcher(
        None,
        user_word,
        correct_word,
    ).ratio()

    length_difference = abs(len(user_word) - len(correct_word))

    # A conservative typo rule:
    # - same word position
    # - only one differing word
    # - maximum length difference of one character
    # - very high textual similarity
    if length_difference <= 1 and word_similarity >= 0.88:
        return True, 0.90

    return None
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



def random_cards(df, antall_kort=10):
    """Genererer en liste med card_id basert på lav score OG hvor lenge siden

    det er forrige forsøk (gamle kort prioriteres).
    """
    # 1. Sørg for riktig tidsformat
    df["tested_at"] = pd.to_datetime(df["tested_at"])

    # 2. Finn nyeste forsøk per kort (vi bryr oss om hvor lenge siden *siste* tegn til liv var)
    siste_forsok = df.sort_values("tested_at").groupby("card_id").last().reset_index()

    # 3. Beregn alder i dager (eller timer) siden dette siste forsøket
    naa = pd.Timestamp.now(tz="UTC")
    siste_forsok["alder_dager"] = (naa - siste_forsok["tested_at"]).dt.total_seconds() / (3600 * 24)

    # 4. Beregn feil_vekt (lavere score gir høyere vekt)
    siste_forsok["feil_vekt"] = 1.0 - siste_forsok["score"]

    # 5. Kombiner alder og feil (Additiv eller multiplikativ tilnærming)
    # Vi legger til 1 på dager for å unngå at helt nye kort får 0 i tidsvekt.
    # Her vil enten LANG TID eller LAV SCORE trekke prioriteringen opp.
    siste_forsok["prioritet"] = (siste_forsok["alder_dager"] + 1) * (siste_forsok["feil_vekt"] + 0.5)

    # Hvis appen er helt ny og alle har 0 i prioritet, gi alle lik sjanse
    if siste_forsok["prioritet"].sum() == 0:
        siste_forsok["prioritet"] = 1.0

    # 6. Gjør om til sannsynligheter som summerer seg til 1
    sannsynlighet = siste_forsok["prioritet"] / siste_forsok["prioritet"].sum()

    # 7. Trekk unike kort basert på denne nye sannsynligheten
    antall_trekk = min(antall_kort, len(siste_forsok))
    valgte_kort = np.random.choice(
        siste_forsok["card_id"], size=antall_trekk, replace=False, p=sannsynlighet
    )

    return list(valgte_kort)