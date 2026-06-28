import random
from typing import Optional
from datetime import datetime, timezone
import re
import streamlit as st
from supabase import create_client, Client
from utills import random_cards
import pandas as pd
@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])

def _looks_like_openai_key(key: str) -> bool:
    key = key.strip()
    return key.startswith("sk-") and len(key) >= 20

def submit_ai_key(ai_key: str) -> bool:
    """Store the signed-in user's OpenAI key in the `OpenAI` table.

    Expects an `OpenAI` table with columns `id` (uuid, = auth user id) and `key` (text).
    Returns True on success, False otherwise (and shows a Streamlit error).
    """
    user = st.session_state.get("user")
    if not user:
        st.error("You must be signed in to save an API key.")
        return False

    ai_key = (ai_key or "").strip()
    if not _looks_like_openai_key(ai_key):
        st.error("That doesn't look like a valid OpenAI key (should start with `sk-`).")
        return False

    client = get_supabase()
    try:
        client.table("openAI").upsert(
            {"id": user["id"], "key": ai_key},
            on_conflict="id",
        ).execute()
    except Exception as e:
        st.error(f"Could not save key: {e}")
        return False
    st.session_state.ai_user = True
    st.success("API key saved.")
    return True

def get_user_preferences():
    """Return {'native_language', 'target_language'} for the signed-in user, or None."""
    user = st.session_state.get("user")
    if not user:
        return None
    client = get_supabase()
    try:
        res = (
            client.table("user_preferences")
            .select("native_language, target_language")
            .eq("user_id", user["id"])
            .maybe_single()
            .execute()
        )
        if res and res.data:
            return res.data
    except Exception as e:
        st.error(f"Could not load language preferences: {e}")
    return None


def save_user_preferences(native_language: str, target_language: str) -> bool:
    user = st.session_state.get("user")
    if not user:
        st.error("You must be signed in.")
        return False
    client = get_supabase()
    try:
        client.table("user_preferences").upsert(
            {
                "user_id": user["id"],
                "native_language": native_language,
                "target_language": target_language,
            },
            on_conflict="user_id",
        ).execute()
        return True
    except Exception as e:
        st.error(f"Could not save language preferences: {e}")
        return False


def get_user_data():
    client = get_supabase()
    user = st.session_state.get("user")

    # Avbryt tidlig hvis brukeren ikke er logget inn
    if not user:
        st.session_state.decks = {}
        return

    # 1. Hent OpenAI-nøkkel
    try:
        ai_data = (
            client.table("openAI")
            .select("key")
            .eq("id", user["id"])
            .maybe_single()
            .execute()
        )
        if ai_data and ai_data.data and ai_data.data.get("key"):
            st.session_state.ai_api = ai_data.data["key"]
            st.session_state.ai_user = True
        else:
            st.session_state.ai_api = ""
    except Exception:
        st.session_state.ai_api = ""

    # 2. Hent Decks
    try:
        res = (
            client.table("decks")
            .select("id", "name")
            .eq("user_id", user["id"])
            .eq("language", st.session_state.lang)
            .execute()
        )
        decks_data = {d["name"]: d["id"] for d in res.data}

        if decks_data:
            st.session_state.decks = decks_data

        else:
            st.session_state.decks = {}


    except Exception as e:
        # Tips: Du kan midlertidig skrive st.error(e) her under utvikling
        # for å se om det oppstår andre feil (f.eks. feil språk-streng eller RLS-feil)
        st.session_state.decks = {}
        st.error(e)

def get_deck(deck_id: int) -> dict:
    client = get_supabase()
    deck = (
        client.table("cards")
        .select("id", "phrase_front", "phrase_back", "explanation")
        .eq("deck_id", deck_id)
        .execute()
    )
    cards_dict = {
        card["phrase_front"].strip(): [card["phrase_back"].strip(), card["explanation"], card["id"]]
        for card in deck.data
    }
    return cards_dict

def get_cards_for_decks(deck_ids: list) -> dict:
    """Return flashcards dict {phrase_front: [phrase_back, explanation, id]} for all cards in the given decks."""
    client = get_supabase()
    if not deck_ids:
        return {}
    try:
        res = (
            client.table("cards")
            .select("id, phrase_front, phrase_back, explanation")
            .in_("deck_id", deck_ids)
            .execute()
        )
        return {
            row["phrase_front"].strip(): [row["phrase_back"].strip(), row["explanation"], row["id"]]
            for row in (res.data or [])
        }
    except Exception as e:
        st.error(f"Could not load cards: {e}")
        return {}


def get_cards_by_ids(card_ids: list) -> dict:
    """Return flashcards dict for a specific set of card ids."""
    client = get_supabase()
    if not card_ids:
        return {}
    try:
        res = (
            client.table("cards")
            .select("id, phrase_front, phrase_back, explanation")
            .in_("id", card_ids)
            .execute()
        )
        return {
            row["phrase_front"].strip(): [row["phrase_back"].strip(), row["explanation"], row["id"]]
            for row in (res.data or [])
        }
    except Exception as e:
        st.error(f"Could not load cards: {e}")
        return {}


def get_cards_of_decks(deck_ids: list) -> dict:
    """Return {phrase_front: card_id} for all cards in the given decks."""
    client = get_supabase()
    if not deck_ids:
        return {}
    try:
        res = (
            client.table("cards")
            .select("id, phrase_front")
            .in_("deck_id", deck_ids)
            .execute()
        )
        return {row["phrase_front"]: row["id"] for row in (res.data or [])}
    except Exception as e:
        st.error(f"Could not load cards: {e}")
        return {}

def rename_deck(deck_id: int, new_name: str) -> bool:
    client = get_supabase()
    new_name = (new_name or "").strip()
    if not new_name:
        st.error("Deck name cannot be empty.")
        return False
    try:
        client.table("decks").update({"name": new_name}).eq("id", deck_id).execute()
        return True
    except Exception as e:
        st.error(f"Could not rename deck: {e}")
        return False


def merge_decks(deck_ids: list, new_name: str) -> Optional[int]:
    """Merge ``deck_ids`` into one deck. The first id is the target; cards from
    the others are reassigned, the source decks are deleted, and the target is
    renamed to ``new_name``. Returns the target deck id on success."""
    if not deck_ids or len(deck_ids) < 2:
        return None
    new_name = (new_name or "").strip()
    if not new_name:
        st.error("Merged deck needs a name.")
        return None
    client = get_supabase()
    target_id = deck_ids[0]
    source_ids = deck_ids[1:]
    try:
        client.table("cards").update({"deck_id": target_id}).in_("deck_id", source_ids).execute()
        client.table("decks").delete().in_("id", source_ids).execute()
        client.table("decks").update({"name": new_name}).eq("id", target_id).execute()
        # Source audio is now orphaned and target audio is stale — drop both.
        user = st.session_state.get("user")
        if user:
            try:
                paths = [f"{user['id']}/{did}.mp3" for did in deck_ids]
                client.storage.from_(DECK_AUDIO_BUCKET).remove(paths)
            except Exception:
                pass
        return target_id
    except Exception as e:
        st.error(f"Could not merge decks: {e}")
        return None


def remove_decks(deck_ids: list) -> bool:
    client = get_supabase()
    if not deck_ids:
        return False
    try:
        client.table("cards").delete().in_("deck_id", deck_ids).execute()
        client.table("decks").delete().in_("id", deck_ids).execute()
        return True
    except Exception as e:
        st.error(f"Could not delete decks: {e}")
        return False

def remove_cards(card_ids: list) -> bool:
    client = get_supabase()
    if not card_ids:
        return False
    try:
        client.table("cards").delete().in_("id", card_ids).execute()
        return True
    except Exception as e:
        st.error(f"Could not delete cards: {e}")
        return False

def save_new_deck(name: str) -> bool:
    """
    Vasker og lagrer en ny kortstokk med tilhørende gloser i Supabase.
    Returnerer True ved suksess, False hvis noe feiler.
    """
    # Sjekk for tomme obligatoriske felter
    client = get_supabase()

    try:
        washed_name = name.strip()
        deck_dict = {eng.strip(): ru.strip() for eng, ru in st.session_state.flashcards.items()}

        # 2. Send dataene til RPC-funksjonen i Supabase
        client.rpc(
            "create_deck_with_cards",
            {
                "deck_name": washed_name,
                "deck_language": st.session_state.lang,
                "cards_json": deck_dict
            }
        ).execute()

        st.success(f"🎉 The deck '{washed_name}' with {len(deck_dict)} cards was saved!")
        return True

    except Exception as e:
        st.error(f"Kunne ikke lagre til databasen: {str(e)}")
        return False

def add_attempt(card_id: int, correct_answer: str, user_answer: str, score: float, mode: str) -> bool:
    client = get_supabase()
    try:
        client.table("card_attempts").insert(
            {
                "card_id": card_id,
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "is_correct": score > 0.8,
                "score": score,
                "mode": mode,
                "language": st.session_state.lang,
            }
        ).execute()
        return True
    except Exception as e:
        st.error(f"Could not save attempt: {e}")
        return False


def add_streak_to_card(card_id: int, is_correct: bool) -> bool:
    client = get_supabase()
    try:
        # 1. Fetch current streak and last test timestamp for the card
        response = client.table("cards").select("streak", "last_tested_at").eq("id", card_id).single().execute()
        card = response.data

        if not card:
            st.error("Card not found.")
            return False

        current_streak = card.get("streak") or 0
        last_tested_str = card.get("last_tested_at")

        # Get current time in UTC
        now = datetime.now(timezone.utc)

        # Default value if the card has never been tested before
        hours_since_last_test = 999

        if last_tested_str:
            # Supabase returns timestamps with timezone offset.
            # fromisoformat() handles this and creates a timezone-aware datetime object.
            last_tested = datetime.fromisoformat(last_tested_str)

            # Calculate the total hours between now and the last test
            duration = now - last_tested
            hours_since_last_test = duration.total_seconds() / 3600

        # 2. Logic to calculate the new streak
        if is_correct:
            # Increase streak only if more than 20 hours have passed (or if it's the first time)
            if hours_since_last_test >= 20:
                new_streak = current_streak + 1
            else:
                new_streak = current_streak  # Keep existing streak if testing too frequently
        else:
            new_streak = 0  # Reset to 0 if the answer is wrong

        # 3. Update the cards table with the new streak and timestamp
        client.table("cards").update({
            "streak": new_streak,
            "last_tested_at": now.isoformat()
        }).eq("id", card_id).execute()

        return True

    except Exception as e:
        st.error(f"Could not update streak: {e}")
        return False


def update_user_vocabulary(correct_phrase: str, submitted_phrase: str, language: str, user_id: str):
    """
    Checks each individual word from the correct phrase against the user's submitted answer.
    Updates the word's streak and correct count in Supabase based on exact matches.
    """
    client = get_supabase()

    # 1. Clean the text inputs (convert to lowercase and remove punctuation)
    clean_correct = re.sub(r'[^\w\s]', '', correct_phrase.lower())
    clean_submitted = re.sub(r'[^\w\s]', '', submitted_phrase.lower())

    # Split into words (using set on correct words to avoid processing duplicates)
    correct_words = list(set(clean_correct.split()))
    submitted_words_set = set(clean_submitted.split())

    if not correct_words:
        return

    try:
        # 2. Fetch existing database records for these specific words
        existing_records = client.table("user_vocabulary") \
            .select("word", "correct_count", "current_streak", "last_tested") \
            .eq("user_id", user_id) \
            .eq("language", language) \
            .in_("word", correct_words) \
            .execute()

        # Create a dictionary for quick lookup: {"word": {record_data}}
        vocabulary_history = {row["word"]: row for row in existing_records.data}

        data_to_upsert = []
        now = datetime.now(timezone.utc)

        correct_counter = 0
        failed_counter = 0

        # 3. Analyze each word from the correct phrase
        for word in correct_words:
            # Check if the exact word exists in the user's response
            is_exact_match = word in submitted_words_set

            record = vocabulary_history.get(word)

            if is_exact_match:
                correct_counter += 1
                if record:
                    # Word exists: Update stats
                    old_correct = record["correct_count"]
                    old_streak = record["current_streak"]
                    last_tested_dt = datetime.fromisoformat(record["last_tested"].replace("Z", "+00:00"))

                    # Only increase streak if it is a new day (at least 20 hours passed)
                    hours_since_last = (now - last_tested_dt).total_seconds() / 3600
                    is_new_day = hours_since_last > 20

                    new_streak = min(old_streak + 1, 5) if is_new_day else old_streak
                    new_correct = old_correct + 1
                else:
                    # Brand new word: Initialize stats
                    new_streak = 1
                    new_correct = 1

                data_to_upsert.append({
                    "user_id": user_id,
                    "word": word,
                    "language": language,
                    "correct_count": new_correct,
                    "current_streak": new_streak,
                    "last_tested": now.isoformat()
                })

            else:
                # Word was misspelled, forgotten, or missing
                if record:
                    failed_counter += 1
                    # Word exists in DB: Penalize the streak by dropping 1 level
                    old_correct = record["correct_count"]
                    old_streak = record["current_streak"]

                    new_streak = max(old_streak - 1, 0)

                    data_to_upsert.append({
                        "user_id": user_id,
                        "word": word,
                        "language": language,
                        "correct_count": old_correct,  # Count does not increase
                        "current_streak": new_streak,  # Streak drops
                        "last_tested": now.isoformat()
                    })
                # If the word was wrong AND does not exist in DB yet, we safely ignore it.

        # 4. Push updates to Supabase in a single batch request
        if data_to_upsert:
            client.table("user_vocabulary") \
                .upsert(data_to_upsert, on_conflict="user_id,word,language") \
                .execute()

    except Exception as e:
        st.error(f"Failed to update user vocabulary: {e}")


def save_ai_explanation(card_id: int, explanation: str) -> bool:
    client = get_supabase()
    try:
        client.table("cards").update({"explanation": explanation}).eq("id", card_id).execute()
        return True
    except Exception as e:
        st.error(f"Could not save explanation: {e}")
        return False

DECK_AUDIO_BUCKET = "deck_audio"


def _deck_audio_path(deck_id: int) -> str:
    user = st.session_state.get("user")
    return f"{user['id']}/{deck_id}.mp3"


def deck_audio_exists(deck_id: int) -> bool:
    user = st.session_state.get("user")
    if not user:
        return False
    client = get_supabase()
    try:
        listing = client.storage.from_(DECK_AUDIO_BUCKET).list(user["id"])
        return any(f.get("name") == f"{deck_id}.mp3" for f in (listing or []))
    except Exception:
        return False


def upload_deck_audio(deck_id: int, audio_bytes: bytes) -> bool:
    user = st.session_state.get("user")
    if not user:
        st.error("You must be signed in.")
        return False
    client = get_supabase()
    path = _deck_audio_path(deck_id)
    bucket = client.storage.from_(DECK_AUDIO_BUCKET)
    file_options = {"content-type": "audio/mpeg", "cache-control": "no-cache"}
    try:
        if deck_audio_exists(deck_id):
            try:
                bucket.remove([path])
            except Exception:
                pass
        bucket.upload(path=path, file=audio_bytes, file_options=file_options)
        return True
    except Exception as e:
        st.error(f"Could not upload audio: {e}")
        return False


def get_deck_audio_bytes(deck_id: int) -> Optional[bytes]:
    user = st.session_state.get("user")
    if not user:
        return None
    client = get_supabase()
    try:
        return client.storage.from_(DECK_AUDIO_BUCKET).download(_deck_audio_path(deck_id))
    except Exception:
        return None


def get_deck_cards_ordered(deck_id: int) -> list[tuple[str, str]]:
    client = get_supabase()
    res = (
        client.table("cards")
        .select("phrase_front, phrase_back")
        .eq("deck_id", deck_id)
        .order("id")
        .execute()
    )
    return [(c["phrase_front"].strip(), c["phrase_back"].strip()) for c in (res.data or [])]


def prepare_random_deck():
    client = get_supabase()
    res = (
        client.table("card_attempts")
        .select("tested_at", "user_answer", "correct_answer", "score", "card_id")
        .eq("language", st.session_state.lang)
        .execute()
    )
    df = pd.DataFrame(res.data)
    card_ids = random_cards(df)
    res = (
        client.table("cards")
        .select("id, phrase_front, phrase_back, explanation")
        .in_("id", card_ids)
        .execute()
    )

    cards_dict = {
        card["phrase_front"].strip(): [card["phrase_back"].strip(), card["explanation"], card["id"]]
        for card in res.data
    }
    st.session_state.flashcards = cards_dict