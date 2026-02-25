import edge_tts
import asyncio
import tempfile
from faster_whisper import WhisperModel
from streamlit_mic_recorder import mic_recorder
from utills import del_mp3s


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

model = WhisperModel"small", device="cpu", compute_type="int8")
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

