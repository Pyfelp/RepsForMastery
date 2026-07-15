from typing import List
from openai import OpenAI
from pydantic import BaseModel, Field


class Weakness(BaseModel):
    topic: str = Field(description="Category of the mistake, e.g. 'Case Inflection', 'Spelling'.")
    input_method: str = Field(description="Must be either 'writing' or 'speaking'.")
    description: str = Field(description="Concise explanation of what the user is doing wrong.")
    example_user_answer: str = Field(description="A concrete wrong answer from the data.")
    example_correct_answer: str = Field(description="The correct answer for that example.")


class PerformanceAnalysis(BaseModel):
    current_level: str = Field(description="Estimated CEFR level (A1, A2, B1, B2, C1, C2).")
    primary_weaknesses: List[Weakness] = Field(description="Up to 3 main weaknesses from the data.")
    speaking_vs_writing_summary: str = Field(description="One-sentence comparison of speaking vs. writing performance.")
    next_steps: List[str] = Field(description="Exactly 2 short, actionable practice tips.")


def analyze_user_performance(
    openai_key: str,
    native_lang: str,
    target_lang: str,
    vocab_count: int,
    attempts_data: list,
) -> PerformanceAnalysis:
    """Run AI performance analysis and return a structured PerformanceAnalysis."""
    client = OpenAI(api_key=openai_key)

    system_instruction = (
        "You are an expert AI language mentor. Analyze the JSON list of a user's recent "
        "language learning practice history. The data includes their answers, correct answers, "
        "whether it was graded correct, and the input method ('writing' or 'speaking'). "
        "Identify recurring mistake patterns, evaluate their current language level, "
        "and separate issues caused by speech-to-text pronunciation problems vs. grammar/spelling. "
        "When analyzing errors for languages with flexible word order (like Russian), "
        "do not penalize variations in word order as a weakness unless it genuinely changes the meaning or violates grammatical rules. "
        "If the user's answer conveys the exact same meaning and is grammatically acceptable in the target language, "
        "treat it as correct in your qualitative analysis, even if it does not match the flashcard's exact baseline translation."
        f"All descriptive text inside the JSON fields must be written in {native_lang}."
    )

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": system_instruction},
            {
                "role": "user",
                "content": (
                    f"The user has a verified mastered vocabulary of {vocab_count} words in {target_lang}. "
                    f"Here is their recent practice history: {attempts_data}"
                ),
            },
        ],
        response_format=PerformanceAnalysis,
        temperature=0.2,
    )

    return completion.choices[0].message.parsed


def explain_phrase(sentence, api_key, target_language: str = "", native_language: str = ""):
    """
    Takes a sentence in the target language and returns a concise explanation
    in the user's native language, with a word-by-word breakdown.
    """
    client = OpenAI(api_key=api_key)

    target = target_language or "the target language"
    native = native_language or "English"

    prompt = (
        f"Analyze the following {target} sentence: '{sentence}'.\n\n"
        f"INSTRUCTIONS:\n"
        f"1. Write your entire response in {native}.\n"
        f"2. Provide a short bulleted list of key words with their meanings and any "
        f"relevant grammatical information (case, gender, number, tense, aspect, mood) "
        f"that applies to {target}.\n"
        f"3. For any word whose form depends on gender, number, or speaker/listener, "
        f"show the alternative forms in parentheses.\n\n"
        f"Format example:\n"
        f"- word (meaning): part of speech, grammatical notes. (alt forms if relevant)\n"
        f"- ...\n\n"
        f"Grammar Notes:\n"
        f"Briefly explain what governs the key grammatical choices in this sentence."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a helpful linguistic assistant specializing in "
                        f"{target}-to-{native} explanation."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"An error occurred: {e}"

class AnswerEvaluation(BaseModel):
    is_acceptable: bool = Field(description="True if the user's answer is a valid translation/meaning, even with typos or minor reordering.")
    score: float = Field(description="A score between 0.0 and 1.0. 1.0 means perfect or completely acceptable alternative.")
    feedback: str = Field(description="A very short, helpful correction in the user's native language if they made a mistake, otherwise empty.")


def evaluate_translation(
        openai_key: str,
        user_answer: str,
        correct_answer: str,
        native_lang: str,
        target_lang: str
) -> AnswerEvaluation:
    """Evaluates the user's answer against the correct answer using semantic comparison."""
    client = OpenAI(api_key=openai_key)

    prompt = f"""
    You are a professional language teacher. Evaluate the user's translation attempt.
    Target Language: {target_lang}
    Correct Answer (Key): {correct_answer}
    User's Answer: {user_answer}
    User's Native Language (for feedback): {native_lang}

    Criteria:
    - If the meaning is completely correct but words are slightly reordered or a minor synonymous word is used, give a high score (0.85 - 1.0) and set is_acceptable to True.
    - If there are minor spelling mistakes but the word is obvious, give a score around 0.8 and set is_acceptable to True.
    - If the meaning changes substantially or a critical word is missing, set is_acceptable to False and lower the score.
    - Keep feedback concise and constructive in the user's native language.
    """

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",  # Rask og billig modell, perfekt for dette
        messages=[
            {"role": "system", "content": "You are a precise language evaluation assistant."},
            {"role": "user", "content": prompt}
        ],
        response_format=AnswerEvaluation,
    )

    return completion.choices[0].message.parsed