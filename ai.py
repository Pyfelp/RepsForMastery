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
    You are a strict language teacher grading a translation exercise.

    Target Language: {target_lang}
    Correct Answer: {correct_answer}
    Student's Answer: {user_answer}
    Feedback Language: {native_lang}

    Your job: decide if the student's answer conveys the SAME MEANING as the correct answer.

    STRICT RULES:
    1. MEANING IS EVERYTHING. Even if only one word differs, if that word changes the meaning, the answer is WRONG.
    2. ANTONYMS ARE ALWAYS WRONG. Words with opposite meanings (open/close, give/take, buy/sell, come/go, start/stop) are never acceptable substitutions, even if the rest of the sentence is identical.
    3. Minor spelling errors on an otherwise correct word are acceptable (score ~0.8).
    4. Word reordering that does not change meaning is acceptable.
    5. If wrong, always provide a short, specific explanation in {native_lang} pointing to the exact mistake.

    EXAMPLE OF A WRONG ANSWER:
    Correct: "Ольга, можешь закрыть окно?" (Can you close the window?)
    Student: "Ольга, можешь открыть окно?" (Can you open the window?)
    → is_acceptable: false, score: 0.1 — "открыть" (open) is the opposite of "закрыть" (close). These mean completely different things.

    Now evaluate the student's answer above.
    """

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "You are a strict language exam grader. Your only job is to judge whether the student's answer "
                "has the EXACT SAME MEANING as the correct answer. One wrong word = wrong answer. "
                "Never accept antonyms (opposite-meaning words) as correct, even if the sentence structure matches."
            )},
            {"role": "user", "content": prompt}
        ],
        response_format=AnswerEvaluation,
    )

    return completion.choices[0].message.parsed