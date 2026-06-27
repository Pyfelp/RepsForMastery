import edge_tts
import asyncio
import io
import tempfile

import streamlit as st
from faster_whisper import WhisperModel
from pydub import AudioSegment
from streamlit_mic_recorder import mic_recorder

from languages import voice_for, whisper_code


def _target_voice() -> str:
    return voice_for(st.session_state.get("lang"))


def _native_voice() -> str:
    return voice_for(st.session_state.get("native_lang"))


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
    """Render a single mp3 reading each card as: front (native), pause, back (target), longer pause."""
    front_voice = _native_voice()
    back_voice = _target_voice()

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
                back_bytes = await _tts_bytes(back, back_voice)
                segments.append(AudioSegment.from_file(io.BytesIO(back_bytes), format="mp3"))
                segments.append(gap_cards)
        return segments

    segments = asyncio.run(_render())
    if not segments:
        return b""
    combined = sum(segments[1:], segments[0])
    buf = io.BytesIO()
    combined.export(buf, format="mp3", bitrate="96k")
    return buf.getvalue()


def play_target(text: str) -> bytes:
    voice = _target_voice()

    async def _tts():
        communicate = edge_tts.Communicate(text=text, voice=voice, rate="-20%")
        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
        return audio_bytes

    return asyncio.run(_tts())


model = WhisperModel("small", device="cpu", compute_type="int8")


def transcribe_target(audio_bytes):
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        f.write(audio_bytes)
        f.flush()
        segments, _ = model.transcribe(f.name, language=whisper_code(st.session_state.get("lang")))
        return " ".join(seg.text for seg in segments)


def rec_audio():
    audio = mic_recorder(
        start_prompt="🎤 Record",
        stop_prompt="⏹️ Stop",
        just_once=True,
    )
    if audio:
        return transcribe_target(audio["bytes"])
