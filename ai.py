from openai import OpenAI

def explain_phrase(sentence, api_key):
    """
    Takes a Russian sentence and returns a concise English explanation
    and word breakdown using OpenAI.
    """
    client = OpenAI(api_key=api_key)

    # The prompt instructs the model to be brief and structured.
    prompt = (
        f"Analyze the following Russian sentence: '{sentence}'. "
        "Give a short bulleted list of the key words and their meanings. Keep the entire "
        "response very concise. Example with russian word: - Я: I" 
        "In the end with header Grammar Notes  you may include short info on grammar"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # You can also use "gpt-3.5-turbo" for lower cost
            messages=[
                {"role": "system",
                 "content": "You are a helpful linguistic assistant specializing in Russian-English translation."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3  # Lower temperature for more focused, factual answers
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"An error occurred: {e}"


