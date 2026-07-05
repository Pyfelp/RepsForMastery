import streamlit as st
from modes import study_view, goto

if st.session_state.get("training_started"):
    st.session_state.training_started = False

has_selection = bool(st.session_state.get("selected_deck_ids")) or bool(st.session_state.get("flashcards"))
if not has_selection:
    st.info("Pick decks from **Decks** first.")
    if st.button("Go to decks"):
        goto("decks")
    st.stop()

study_view()
