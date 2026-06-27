import streamlit as st
from auth import auth_gate, logout_button
from db import get_user_preferences
from languages import FLAGS, language_name

st.set_page_config(page_title="Reps for Mastery", layout="centered")

if not auth_gate():
    st.stop()

# ---------------------------
# SESSION STATE INIT
# ---------------------------
_DEFAULTS = {
    "lang": None,
    "native_lang": None,
    "deck": "",
    "shuffle": True,
    "cards": [],
    "flashcards": {},
    "score": 0,
    "ai_api": "",
    "ai_user": False,
    "index": 0,
    "stats": {},
    "submitted": False,
    "user_input": "",
    "ui_answer": "",
    "tts_audio": None,
    "tts_for_index": None,
    "decks": [],
    "attempt_added": False,
    "selected_deck_ids": [],
    "selected_deck_names": [],
    "selected_card_ids": [],
    "training_started": False,
}
for _k, _v in _DEFAULTS.items():
    st.session_state.setdefault(_k, _v)

# Load language preferences once per session.
if not st.session_state.get("prefs_loaded"):
    prefs = get_user_preferences()
    if prefs:
        st.session_state.native_lang = prefs.get("native_language")
        st.session_state.lang = prefs.get("target_language")
    st.session_state.prefs_loaded = True

logout_button()

target = st.session_state.get("lang")
if target:
    st.title(f"{FLAGS.get(target, '🌐')} Reps for Mastery — {language_name(target)}")
else:
    st.title("🌐 Reps for Mastery")


# ---------------------------
# NAVIGATION
# ---------------------------
prefs_page = st.Page("views/preferences.py", title="Languages", icon="🌐")

has_prefs = bool(st.session_state.get("lang") and st.session_state.get("native_lang"))

if not has_prefs:
    pg = st.navigation([st.Page("views/preferences.py", title="Choose languages", icon="🌐", default=True)])
    pg.run()
else:
    decks_page = st.Page("views/decks.py", title="Decks", icon="🗂", default=True)
    train_page = st.Page("views/train.py", title="Train", icon="🧠")
    listen_page = st.Page("views/listen.py", title="Listen", icon="🔊")
    load_page = st.Page("views/load_cards.py", title="New deck", icon="📥")
    ai_page = st.Page("views/get_ai.py", title="AI settings", icon="🤖")

    sections = {
        "Decks": [decks_page, load_page],
        "Session": [train_page, listen_page],
        "Settings": [ai_page, prefs_page],
    }

    pg = st.navigation(sections)
    pg.run()
