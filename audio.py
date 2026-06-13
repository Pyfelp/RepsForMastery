import edge_tts
import asyncio
import io
import tempfile
from faster_whisper import WhisperModel
from langdetect import detect, DetectorFactory, LangDetectException
from pydub import AudioSegment
from streamlit_mic_recorder import mic_recorder
from utills import del_mp3s

DetectorFactory.seed = 0


VOICE = "ru-RU-DmitryNeural"  # Mannsstemme
# VOICE = "ru-RU-SvetlanaNeural"  # Kvinne


def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        return loop.run_until_complete(coro)




VOICE = "ru-RU-DmitryNeural"
EN_VOICE = "en-US-AriaNeural"
NB_VOICE = "nb-NO-PernilleNeural"


def _front_voice(text: str) -> str:
    """Pick a TTS voice for a single front-of-card text."""
    t = (text or "").strip()
    if not t:
        return EN_VOICE
    if any(ch in t.lower() for ch in "æøå"):
        return NB_VOICE
    try:
        lang = detect(t)
    except LangDetectException:
        return EN_VOICE
    if lang in ("no", "nb", "nn", "da"):
        return NB_VOICE
    return EN_VOICE


def _deck_front_voice(fronts: list[str]) -> str:
    """Pick one voice for the whole deck by looking at all front texts together.

    Short individual cards are unreliable for langdetect; pooling them stabilizes
    the detection and keeps the voice consistent across the deck.
    """
    joined = " ".join(f.strip() for f in fronts if f and f.strip())
    if not joined:
        return EN_VOICE
    if any(ch in joined.lower() for ch in "æøå"):
        return NB_VOICE
    try:
        lang = detect(joined)
    except LangDetectException:
        return EN_VOICE
    if lang in ("no", "nb", "nn", "da"):
        return NB_VOICE
    return EN_VOICE


async def _tts_bytes(text: str, voice: str, rate: str = "-10%") -> bytes:
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    buf = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf += chunk["data"]
    return buf


GAP_SIDES_MS = 500
GAP_CARDS_MS = 1500
GAP_DECKS_MS = 2500


def join_deck_audios(mp3_blobs: list[bytes]) -> bytes:
    """Concatenate several deck mp3s into one, with a longer gap between decks."""
    if not mp3_blobs:
        return b""
    gap = AudioSegment.silent(duration=GAP_DECKS_MS)
    parts: list[AudioSegment] = []
    for blob in mp3_blobs:
        if not blob:
            continue
        parts.append(AudioSegment.from_file(io.BytesIO(blob), format="mp3"))
        parts.append(gap)
    if not parts:
        return b""
    combined = sum(parts[1:], parts[0])
    buf = io.BytesIO()
    combined.export(buf, format="mp3", bitrate="96k")
    return buf.getvalue()


def build_deck_audio(cards: list[tuple[str, str]]) -> bytes:
    """Render a single mp3 reading each card as: front, pause, Russian, longer pause.

    The front voice is decided once for the whole deck based on the pooled front
    texts — this is more reliable than detecting each short card individually.
    """
    front_voice = _deck_front_voice([f for f, _ in cards])

    async def _render():
        segments: list[AudioSegment] = []
        gap_sides = AudioSegment.silent(duration=GAP_SIDES_MS)
        gap_cards = AudioSegment.silent(duration=GAP_CARDS_MS)
        for front, back in cards:
            if front:
                front_bytes = await _tts_bytes(front, front_voice)
                segments.append(AudioSegment.from_file(io.BytesIO(front_bytes), format="mp3"))
                segments.append(gap_sides)
            if back:
                ru_bytes = await _tts_bytes(back, VOICE)
                segments.append(AudioSegment.from_file(io.BytesIO(ru_bytes), format="mp3"))
                segments.append(gap_cards)
        return segments

    segments = asyncio.run(_render())
    if not segments:
        return b""
    combined = sum(segments[1:], segments[0])
    buf = io.BytesIO()
    combined.export(buf, format="mp3", bitrate="96k")
    return buf.getvalue()


def play_russian(ru_txt: str) -> bytes:
    async def _tts():
        communicate = edge_tts.Communicate(
            text=ru_txt,
            voice=VOICE,
            rate="-20%"
        )

        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]

        return audio_bytes

    return asyncio.run(_tts())

model = WhisperModel("small", device="cpu", compute_type="int8")
def transcribe_ru(audio_bytes):
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        f.write(audio_bytes)
        f.flush()

        segments, _ = model.transcribe(
            f.name,
            language="ru"
        )

        return " ".join(seg.text for seg in segments)
def rec_audio():
    audio = mic_recorder(
        start_prompt="🎤 Record",
        stop_prompt="⏹️ Stop",
        just_once=True
    )
    if audio:
        audio_bytes = audio["bytes"]
        spoken = transcribe_ru(audio_bytes)

        return spoken

