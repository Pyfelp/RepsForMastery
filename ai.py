from openai import OpenAI


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
