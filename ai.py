from typing import List, Literal
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
    is_acceptable: bool = Field(
        description=(
            "True when the essential intended meaning is preserved "
            "and there is no major semantic error."
        )
    )

    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Graded answer quality from 0.0 to 1.0."
    )

    feedback: str = Field(
        description=(
            "Brief feedback in the student's native language. "
            "May be empty for a fully correct answer."
        )
    )

    error_type: Literal[
        "none",
        "minor_spelling",
        "minor_grammar",
        "harmless_variation",
        "missing_optional_information",
        "missing_required_information",
        "wrong_word",
        "opposite_meaning",
        "partial_meaning",
        "unclear_meaning",
    ]


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
    You are a language-learning answer evaluator.

    Your task is to compare a student's answer with a reference answer in the target language.

    The reference answer is one valid answer, but it is not necessarily the only valid way to express the intended meaning.

    INPUT

    Target language: {target_lang}
    Student's native language: {native_lang}
    Reference answer: {correct_answer}
    Student answer: {user_answer}

    CORE PRINCIPLE
    
    Evaluate whether the student's answer communicates the same essential meaning as the reference answer.
    
    Do not grade based only on exact wording or text similarity.
    
    EVALUATION PROCESS

        1. Determine the essential meaning of the reference answer.
        
        2. Determine the meaning communicated by the student's answer.
        
        3. Compare the two meanings.
        
        4. Identify whether the differences are:
        
           * harmless variations,
           * minor language errors,
           * missing optional information,
   * partially correct meaning,
   * or meaning-changing errors.

    ACCEPTABLE ANSWERS
    
    An answer may be accepted when:
    
    * It communicates the same essential meaning as the reference answer.
    * The word order is different but remains grammatically possible or understandable.
    * It omits a word that is not necessary for the essential meaning.
    * It uses a synonym or another natural expression with the same meaning.
    * It contains grammar errors, but the intended meaning remains clear.
    * It contains minor spelling mistakes, provided the intended word is still unambiguous.
    
    Do not require the student to reproduce the reference answer exactly.
    
    MEANING-CHANGING ERRORS
    
    Do not accept an answer as fully correct when:
    
    * A word has been replaced with a word that has a different meaning.
    * A similar-looking word is used, but it is actually a different word.
    * An antonym or opposite action is used.
    * The subject, object, action, negation, time, quantity, or another essential detail is changed.
    * A necessary word is omitted and this changes or removes essential meaning.
    * The answer only communicates part of the required meaning.
    * The intended meaning cannot be determined reliably.
    
    Important:
    
    Visual or phonetic similarity between words is not evidence that they have the same meaning.
    
    For example, if the reference uses a word meaning “close” and the student uses a similar-looking word meaning “open”, this is a major semantic error, not a typo.
    
    GRAMMAR
    
    Grammar mistakes should not automatically make an answer incorrect.
    
    If the intended meaning is clear and matches the reference answer, the answer may still be accepted.
    
    Reduce the score according to how much the grammar error affects clarity, precision, or naturalness.
    
    SCORING
    
    Return a score between 0.0 and 1.0.
    
    Use these guidelines:
    
    * 0.95–1.00:
      Same essential meaning. Fully correct or only harmless differences.
    
    * 0.85–0.94:
      Same essential meaning, but with a minor spelling, grammar, or wording issue.
    
    * 0.70–0.84:
      Meaning is mostly correct and clearly understandable, but there is a noticeable error or missing detail.
    
    * 0.40–0.69:
      Partially correct. Some essential meaning is present, but an important detail is wrong or missing.
    
    * 0.10–0.39:
      Mostly incorrect. Only a small part of the intended meaning is preserved.
    
    * 0.00–0.09:
      Incorrect, unrelated, opposite in meaning, or impossible to interpret.
    
    ACCEPTANCE RULE
    
    Set `is_acceptable` to true when:
    
    * the essential meaning is preserved,
    * the student's intended meaning is clear,
    * and there is no major meaning-changing error.
    
    Normally, answers with a score of 0.70 or higher may be acceptable.
    
    However, a score above 0.70 does not override a major semantic error.
    
    For example, an answer containing the opposite action must not be accepted even if the rest of the sentence is correct.
    
    FEEDBACK
    
    Write the feedback in {native_lang}.
    
    The feedback must:
    
    * be brief,
    * explain the most important difference,
    * be encouraging but accurate,
    * and avoid criticizing harmless word-order or wording variations.
    
    If the answer is fully correct, the feedback may be empty.
    
    If the answer is accepted with an error, briefly explain the error.
    
    If the answer is not accepted, identify the word or detail that changes the meaning.
    
    OUTPUT
    
    Return only the structured result with:
    
    * `is_acceptable`: boolean
    * `score`: number between 0.0 and 1.0
    * `feedback`: short feedback in {native_lang}
    * `error_type`: one of:
    
      * `none`
      * `minor_spelling`
      * `minor_grammar`
      * `harmless_variation`
      * `missing_optional_information`
      * `missing_required_information`
      * `wrong_word`
      * `opposite_meaning`
      * `partial_meaning`
      * `unclear_meaning`                           

    """

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "You are an empathetic language teacher. You strictly penalize wrong meanings and antonyms, "
                "but you are forgiving toward minor typos/spelling errors as long as the intended word and overall meaning are obvious."
            )},
            {"role": "user", "content": prompt}
        ],
        response_format=AnswerEvaluation,
    )

    return completion.choices[0].message.parsed