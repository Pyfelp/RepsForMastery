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
