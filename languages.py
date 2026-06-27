LANGUAGES = {
    "ru": "Russian",
    "en": "English",
    "de": "German",
    "es": "Spanish",
    "no": "Norwegian",
    "uk": "Ukrainian",
}

FLAGS = {
    "ru": "🇷🇺",
    "en": "🇬🇧",
    "de": "🇩🇪",
    "es": "🇪🇸",
    "no": "🇳🇴",
    "uk": "🇺🇦",
}

# edge_tts voice per language
VOICES = {
    "ru": "ru-RU-DmitryNeural",
    "en": "en-US-AriaNeural",
    "de": "de-DE-KatjaNeural",
    "es": "es-ES-ElviraNeural",
    "no": "nb-NO-PernilleNeural",
    "uk": "uk-UA-PolinaNeural",
}

# faster-whisper language codes
WHISPER_CODES = {
    "ru": "ru",
    "en": "en",
    "de": "de",
    "es": "es",
    "no": "no",
    "uk": "uk",
}


def language_name(code: str) -> str:
    return LANGUAGES.get(code, code or "")


def voice_for(code: str) -> str:
    return VOICES.get(code, VOICES["en"])


def whisper_code(code: str) -> str:
    return WHISPER_CODES.get(code, "en")
