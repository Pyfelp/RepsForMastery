import streamlit as st
from modes import train, prep, load_cards, goto

st.set_page_config(page_title="RuLearn", layout="centered")

st.title("🇷🇺 Reps for Mastery - Russian")
# ---------------------------
# SESSION STATE INIT
# ---------------------------
if "mode" not in st.session_state:
    st.session_state.mode = "prepare"
if "shuffle" not in st.session_state:
    st.session_state.shuffle = True
if "cards" not in st.session_state:
    st.session_state.cards = []
if "flashcards" not in st.session_state:
    st.session_state.flashcards = {}
if "score" not in st.session_state:
    st.session_state.score = 0

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



def main():
    st.divider()

    mode = st.session_state.mode

    if mode == "train":
        train()
    elif mode == "prepare":
        prep()
    elif mode == "load":
        load_cards()
    else:
        st.session_state.mode = "prepare"
        st.rerun()

if __name__ == "__main__":
    main()
