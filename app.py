import streamlit as st
from modes import train, prep, load_cards, get_ai, goto, manage_decks
from auth import auth_gate, logout_button

st.set_page_config(page_title="Reps for Mastery", layout="centered")

if not auth_gate():
    st.stop()

logout_button()

st.title("🇷🇺 Reps for Mastery - Russian")

# ---------------------------
# SESSION STATE INIT
# ---------------------------
if "mode" not in st.session_state:
    st.session_state.mode = "prepare"
if "prev_mode" not in st.session_state:
    st.session_state.prev_mode = ""
if "lang" not in st.session_state:
    st.session_state.lang = "ru"
if "deck" not in st.session_state:
    st.session_state.deck = ""
if "shuffle" not in st.session_state:
    st.session_state.shuffle = True
if "cards" not in st.session_state:
    st.session_state.cards = []
if "flashcards" not in st.session_state:
    st.session_state.flashcards = {}
if "score" not in st.session_state:
    st.session_state.score = 0
if "ai_api" not in st.session_state:
    st.session_state.ai_api = ""
if "ai_user" not in st.session_state:
    st.session_state.ai_user = False
if "index" not in st.session_state:
    st.session_state.index = 0

if "stats" not in st.session_state:
    st.session_state.stats = {}
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "user_input" not in st.session_state:
    st.session_state.user_input = ""
if "ui_answer" not in st.session_state:
    st.session_state.ui_answer = ""
if "tts_audio" not in st.session_state:
    st.session_state.tts_audio = None
if "tts_for_index" not in st.session_state:
    st.session_state.tts_for_index = None
if "decks" not in st.session_state:
    st.session_state.decks = []
if "attempt_added" not in st.session_state:
    st.session_state.attempt_added = False

# ---------------------------
# Sidebar setting buttorns
# ---------------------------
with st.sidebar:
    if st.button("AI functionality"):
        st.session_state.prev_mode = st.session_state.mode
        goto("get_ai")
    if st.button("Manage decks"):
        st.session_state.prev_mode = st.session_state.mode
        goto("manage_decks")

def main():
    st.divider()

    mode = st.session_state.mode

    if mode == "train":
        train()
    elif mode == "prepare":
        prep()
    elif mode == "get_ai":
        get_ai()
    elif mode == "manage_decks":
        manage_decks()
    elif mode == "load":
        load_cards()
    else:
        st.session_state.mode = "prepare"
        st.rerun()

if __name__ == "__main__":
    main()
