"""
simple_answer_evaluation.py

Enkel evalueringsmodul for språkøvelser.

Prinsipp:
- Normaliser kun:
  * store/små bokstaver
  * punktum
  * spørsmålstegn
  * utropstegn
  * ekstra whitespace
- Apostrof beholdes, slik at f.eks. "couldn't" ikke blir ødelagt.

Regler:
1. Sentence similarity >= 0.90:
   -> godkjennes lokalt

2. Sentence similarity mellom 0.50 og 0.90:
   -> AI vurderer om avvikene hovedsakelig ser ut som skrivefeil
      eller om studenten trolig ikke kan svaret

3. Sentence similarity < 0.50:
   -> normalt feil lokalt
   -> MEN går til AI hvis:
      a) akkurat ett ord mangler og alle andre ord matcher 100 %
      b) akkurat ett ekstra ord finnes og alle andre ord matcher 100 %
      c) alle ord finnes og er 100 % riktige, men rekkefølgen er endret

Hovedfunksjon:
    evaluate_answer(
        user_answer=...,
        correct_answer=...,
        target_lang="Russian",
        native_lang="Norwegian",
        api_key="sk-...",
    )

Ingen Streamlit-avhengighet.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal, Optional


TEST_OPENAI_API_KEY = ""
DEFAULT_AI_MODEL = "gpt-4o-mini"


@dataclass
class EvaluationResult:
    is_acceptable: bool
    score: float
    feedback: str
    error_type: Literal[
        "none",
        "minor_spelling",
        "harmless_variation",
        "missing_word",
        "extra_word",
        "word_order",
        "incorrect",
        "unclear",
    ]
    source: Literal["local", "ai", "no_ai"]
    sentence_similarity: float
    reason: str


def normalize(text: str) -> str:
    """
    Forsiktig normalisering.

    Fjerner kun:
    - punktum
    - spørsmålstegn
    - utropstegn
    - store/små bokstaver
    - ekstra whitespace

    Apostrof og øvrige tegn beholdes.
    """
    text = (text or "").casefold()
    text = re.sub(r"[.!?]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(
        None,
        normalize(a),
        normalize(b),
    ).ratio()


def word_similarities(
    user_answer: str,
    correct_answer: str,
) -> list[tuple[str, str, float]]:
    """
    Sammenligner ord i samme posisjon.

    Mest nyttig til debugging/test.
    """
    user_words = normalize(user_answer).split()
    correct_words = normalize(correct_answer).split()

    result = []

    for i in range(max(len(user_words), len(correct_words))):
        user_word = user_words[i] if i < len(user_words) else ""
        correct_word = correct_words[i] if i < len(correct_words) else ""

        score = SequenceMatcher(
            None,
            user_word,
            correct_word,
        ).ratio()

        result.append(
            (user_word, correct_word, score)
        )

    return result


def _exact_word_structure(
    user_answer: str,
    correct_answer: str,
) -> dict:
    """
    Analyserer bare eksakte ord etter normalisering.

    Ingen synonymforståelse eller grammatikk.
    """
    user_words = normalize(user_answer).split()
    correct_words = normalize(correct_answer).split()

    user_counter = Counter(user_words)
    correct_counter = Counter(correct_words)

    same_words_any_order = (
        user_counter == correct_counter
        and user_words != correct_words
    )

    # Ett manglende ord:
    # correct har nøyaktig ett ord mer, og studentens ord kan trekkes
    # fra correct uten andre forskjeller.
    one_missing = False
    missing_word = None

    if len(correct_words) == len(user_words) + 1:
        diff = correct_counter - user_counter
        reverse_diff = user_counter - correct_counter

        if (
            sum(diff.values()) == 1
            and sum(reverse_diff.values()) == 0
        ):
            one_missing = True
            missing_word = next(iter(diff.elements()))

    # Ett ekstra ord.
    one_extra = False
    extra_word = None

    if len(user_words) == len(correct_words) + 1:
        diff = user_counter - correct_counter
        reverse_diff = correct_counter - user_counter

        if (
            sum(diff.values()) == 1
            and sum(reverse_diff.values()) == 0
        ):
            one_extra = True
            extra_word = next(iter(diff.elements()))

    return {
        "user_words": user_words,
        "correct_words": correct_words,
        "same_words_any_order": same_words_any_order,
        "one_missing": one_missing,
        "missing_word": missing_word,
        "one_extra": one_extra,
        "extra_word": extra_word,
    }


def _resolve_api_key(api_key: Optional[str]) -> Optional[str]:
    if api_key and api_key.strip():
        return api_key.strip()

    if TEST_OPENAI_API_KEY.strip():
        return TEST_OPENAI_API_KEY.strip()

    env_key = os.getenv("OPENAI_API_KEY", "").strip()
    return env_key or None


def _evaluate_with_ai(
    *,
    api_key: str,
    user_answer: str,
    correct_answer: str,
    target_lang: str,
    native_lang: str,
    sentence_similarity: float,
    reason: str,
    model: str,
) -> EvaluationResult:
    try:
        from openai import OpenAI
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise RuntimeError(
            "AI-evaluering krever openai og pydantic."
        ) from exc

    class AIResult(BaseModel):
        is_acceptable: bool
        score: float = Field(ge=0.0, le=1.0)
        feedback: str
        error_type: Literal[
            "none",
            "minor_spelling",
            "harmless_variation",
            "missing_word",
            "extra_word",
            "word_order",
            "incorrect",
            "unclear",
        ]

    client = OpenAI(api_key=api_key)

    if reason in {
        "one_missing_word",
        "one_extra_word",
        "same_words_different_order",
    }:
        question = (
            "Is this a reasonable alternative translation despite the "
            "missing/extra word or changed word order?"
        )
    else:
        question = (
            "Do the differences mainly look like spelling/typing mistakes, "
            "or do they suggest the student does not know the answer?"
        )

    prompt = (
        f"Language: {target_lang}\n"
        f"Reference: {correct_answer}\n"
        f"Student: {user_answer}\n"
        f"Similarity: {sentence_similarity:.2f}\n"
        f"Case: {reason}\n"
        f"{question}\n"
        f"Give brief feedback in {native_lang}."
    )

    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You verify language-learning answers. "
                    "Be practical and concise."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        response_format=AIResult,
        temperature=0.0,
    )

    parsed = completion.choices[0].message.parsed

    if parsed is None:
        raise RuntimeError("AI returned no structured result.")

    return EvaluationResult(
        is_acceptable=parsed.is_acceptable,
        score=float(parsed.score),
        feedback=parsed.feedback or "",
        error_type=parsed.error_type,
        source="ai",
        sentence_similarity=sentence_similarity,
        reason=reason,
    )


def evaluate_answer(
    user_answer: str,
    correct_answer: str,
    target_lang: str,
    native_lang: str = "Norwegian",
    api_key: Optional[str] = None,
    *,
    model: str = DEFAULT_AI_MODEL,
) -> EvaluationResult:
    """
    Offentlig hovedfunksjon.
    """

    user = normalize(user_answer)
    correct = normalize(correct_answer)

    # Tomt svar
    if not user:
        return EvaluationResult(
            is_acceptable=False,
            score=0.0,
            feedback="",
            error_type="incorrect",
            source="local",
            sentence_similarity=0.0,
            reason="empty_answer",
        )

    sentence_score = similarity(
        user_answer,
        correct_answer,
    )

    # ---------------------------------------------------------
    # 1. >= 90 % -> lokal godkjenning
    # ---------------------------------------------------------
    if sentence_score >= 0.90:
        return EvaluationResult(
            is_acceptable=True,
            score=sentence_score,
            feedback="",
            error_type=(
                "none"
                if user == correct
                else "minor_spelling"
            ),
            source="local",
            sentence_similarity=sentence_score,
            reason="high_similarity",
        )

    structure = _exact_word_structure(
        user_answer,
        correct_answer,
    )

    reason = None

    # ---------------------------------------------------------
    # 2. 50-90 % -> AI
    # ---------------------------------------------------------
    if 0.50 <= sentence_score < 0.90:
        reason = "medium_similarity"

    # ---------------------------------------------------------
    # 3. < 50 %, men spesielle strukturelle tilfeller -> AI
    # ---------------------------------------------------------
    elif sentence_score < 0.50:
        if structure["one_missing"]:
            reason = "one_missing_word"

        elif structure["one_extra"]:
            reason = "one_extra_word"

        elif structure["same_words_any_order"]:
            reason = "same_words_different_order"

        else:
            return EvaluationResult(
                is_acceptable=False,
                score=sentence_score,
                feedback="",
                error_type="incorrect",
                source="local",
                sentence_similarity=sentence_score,
                reason="low_similarity",
            )

    # ---------------------------------------------------------
    # AI ved tvilstilfeller
    # ---------------------------------------------------------
    resolved_key = _resolve_api_key(api_key)

    if resolved_key:
        return _evaluate_with_ai(
            api_key=resolved_key,
            user_answer=user_answer,
            correct_answer=correct_answer,
            target_lang=target_lang,
            native_lang=native_lang,
            sentence_similarity=sentence_score,
            reason=reason,
            model=model,
        )

    return EvaluationResult(
        is_acceptable=False,
        score=sentence_score,
        feedback="AI required for this comparison.",
        error_type="unclear",
        source="no_ai",
        sentence_similarity=sentence_score,
        reason=reason or "unknown",
    )


if __name__ == "__main__":
    examples = [
        ("I couldn't go.", "I couldn't go"),
        ("I close the door", "I closed the door"),
        ("Сегодня я работаю", "Я сегодня работаю"),
        ("Я люблю кофе", "Я очень люблю кофе"),
        ("I really like coffee", "I like coffee"),
    ]

    for student, reference in examples:
        result = evaluate_answer(
            user_answer=student,
            correct_answer=reference,
            target_lang="English",
            api_key=None,
        )

        print()
        print("Student:   ", student)
        print("Reference: ", reference)
        print("Similarity:", round(result.sentence_similarity, 3))
        print("Source:    ", result.source)
        print("Reason:    ", result.reason)
        print("Accepted:  ", result.is_acceptable)
