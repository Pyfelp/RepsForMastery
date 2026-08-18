"""
similarity_answer_evaluation.py

AI-fri evaluering av språk-svar.

Prinsipp:
- Ingen grammatikkregler.
- Ingen språkspesifikke regler.
- Ingen AI.
- Resultatet bygger bare på tekstlig similarity.

Normalisering:
- casefold/lowercase
- fjerner kun . ? !
- beholder apostrof, aksenter og øvrige tegn
- komprimerer whitespace

Scorer:
1. sentence_similarity
2. ordered_word_similarity
3. unordered_word_similarity
4. word_count_similarity

Final score er en vektet kombinasjon.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher


DEFAULT_ACCEPT_THRESHOLD = 0.90


@dataclass
class WordMatch:
    student_word: str
    reference_word: str
    similarity: float
    student_index: int
    reference_index: int


@dataclass
class SimilarityEvaluation:
    is_acceptable: bool
    score: float
    sentence_similarity: float
    ordered_word_similarity: float
    unordered_word_similarity: float
    word_count_similarity: float
    normalized_student: str
    normalized_reference: str
    word_matches: list[WordMatch] = field(default_factory=list)
    student_word_count: int = 0
    reference_word_count: int = 0
    threshold: float = DEFAULT_ACCEPT_THRESHOLD


def normalize(text: str) -> str:
    text = (text or "").casefold()
    text = re.sub(r"[.!?]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def sentence_similarity(
    student: str,
    reference: str,
) -> float:
    return _similarity(
        normalize(student),
        normalize(reference),
    )


def _ordered_word_similarity(
    student_words: list[str],
    reference_words: list[str],
) -> float:
    max_len = max(
        len(student_words),
        len(reference_words),
        1,
    )

    total = 0.0

    for i in range(max_len):
        student_word = (
            student_words[i]
            if i < len(student_words)
            else ""
        )
        reference_word = (
            reference_words[i]
            if i < len(reference_words)
            else ""
        )

        total += _similarity(
            student_word,
            reference_word,
        )

    return total / max_len


def _best_unordered_word_matches(
    student_words: list[str],
    reference_words: list[str],
) -> list[WordMatch]:
    remaining_student = set(
        range(len(student_words))
    )
    remaining_reference = set(
        range(len(reference_words))
    )

    matches: list[WordMatch] = []

    while remaining_student and remaining_reference:
        best = None

        for si in remaining_student:
            for ri in remaining_reference:
                score = _similarity(
                    student_words[si],
                    reference_words[ri],
                )

                candidate = (
                    score,
                    -abs(si - ri),
                    si,
                    ri,
                )

                if best is None or candidate > best:
                    best = candidate

        if best is None:
            break

        score, _, si, ri = best

        matches.append(
            WordMatch(
                student_word=student_words[si],
                reference_word=reference_words[ri],
                similarity=score,
                student_index=si,
                reference_index=ri,
            )
        )

        remaining_student.remove(si)
        remaining_reference.remove(ri)

    return matches


def _unordered_word_similarity(
    student_words: list[str],
    reference_words: list[str],
) -> tuple[float, list[WordMatch]]:
    matches = _best_unordered_word_matches(
        student_words,
        reference_words,
    )

    denominator = max(
        len(student_words),
        len(reference_words),
        1,
    )

    score = (
        sum(match.similarity for match in matches)
        / denominator
    )

    return score, matches


def _word_count_similarity(
    student_words: list[str],
    reference_words: list[str],
) -> float:
    longest = max(
        len(student_words),
        len(reference_words),
        1,
    )

    shortest = min(
        len(student_words),
        len(reference_words),
    )

    return shortest / longest


def evaluate_answer(
    user_answer: str,
    correct_answer: str,
    *,
    accept_threshold: float = DEFAULT_ACCEPT_THRESHOLD,
    sentence_weight: float = 0.50,
    ordered_word_weight: float = 0.15,
    unordered_word_weight: float = 0.30,
    word_count_weight: float = 0.05,
) -> SimilarityEvaluation:
    weights = (
        sentence_weight
        + ordered_word_weight
        + unordered_word_weight
        + word_count_weight
    )

    if abs(weights - 1.0) > 1e-9:
        raise ValueError(
            "Similarity weights must sum to 1.0"
        )

    if not 0.0 <= accept_threshold <= 1.0:
        raise ValueError(
            "accept_threshold must be between 0 and 1"
        )

    student = normalize(user_answer)
    reference = normalize(correct_answer)

    student_words = student.split()
    reference_words = reference.split()

    sentence_score = _similarity(
        student,
        reference,
    )

    ordered_score = _ordered_word_similarity(
        student_words,
        reference_words,
    )

    unordered_score, matches = (
        _unordered_word_similarity(
            student_words,
            reference_words,
        )
    )

    count_score = _word_count_similarity(
        student_words,
        reference_words,
    )

    final_score = (
        sentence_score * sentence_weight
        + ordered_score * ordered_word_weight
        + unordered_score * unordered_word_weight
        + count_score * word_count_weight
    )

    final_score = max(
        0.0,
        min(final_score, 1.0),
    )

    return SimilarityEvaluation(
        is_acceptable=(
            final_score >= accept_threshold
        ),
        score=final_score,
        sentence_similarity=sentence_score,
        ordered_word_similarity=ordered_score,
        unordered_word_similarity=unordered_score,
        word_count_similarity=count_score,
        normalized_student=student,
        normalized_reference=reference,
        word_matches=matches,
        student_word_count=len(student_words),
        reference_word_count=len(reference_words),
        threshold=accept_threshold,
    )


if __name__ == "__main__":
    examples = [
        (
            "I ussually work from home",
            "I usually work from home",
        ),
        (
            "Yesterday I bought a new car",
            "I bought a new car yesterday",
        ),
        (
            "The man bites the dog",
            "The dog bites the man",
        ),
        (
            "Я люблю кофе",
            "Я очень люблю кофе",
        ),
    ]

    for student, reference in examples:
        result = evaluate_answer(
            student,
            reference,
        )

        print()
        print("Student:   ", student)
        print("Reference: ", reference)
        print("Accepted:  ", result.is_acceptable)
        print("Final:     ", round(result.score, 3))
        print(
            "Sentence:  ",
            round(result.sentence_similarity, 3),
        )
        print(
            "Ordered:   ",
            round(result.ordered_word_similarity, 3),
        )
        print(
            "Unordered: ",
            round(result.unordered_word_similarity, 3),
        )
        print(
            "Word count:",
            round(result.word_count_similarity, 3),
        )
