import random

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

def save_ai_explanation(card_id: int, explanation: str) -> bool:
    client = get_supabase()
    try:
        client.table("cards").update({"explanation": explanation}).eq("id", card_id).execute()
        return True
    except Exception as e:
        st.error(f"Could not save explanation: {e}")
        return False

def prepare_random_deck():
    client = get_supabase()
    res = (
        client.table("card_attempts")
        .select("tested_at", "user_answer", "correct_answer", "score", "card_id")
        .eq("language", "ru")
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