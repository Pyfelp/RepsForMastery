import streamlit as st
from auth import auth_gate, logout_button

st.set_page_config(page_title="Reps for Mastery", layout="centered")

if not auth_gate():
    st.stop()

# ---------------------------
# SESSION STATE INIT
# ---------------------------
_DEFAULTS = {
    "lang": "ru",
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

logout_button()
st.title("🇷🇺 Reps for Mastery - Russian")


# ---------------------------
# NAVIGATION
# ---------------------------
decks_page = st.Page("views/decks.py", title="Decks", icon="🗂", default=True)
train_page = st.Page("views/train.py", title="Train", icon="🧠")
listen_page = st.Page("views/listen.py", title="Listen", icon="🔊")
load_page = st.Page("views/load_cards.py", title="New deck", icon="📥")
ai_page = st.Page("views/get_ai.py", title="AI settings", icon="🤖")

sections = {
    "Decks": [decks_page, load_page],
    "Session": [train_page, listen_page],
    "Settings": [ai_page],
}

pg = st.navigation(sections)
pg.run()
