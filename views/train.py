import streamlit as st
from modes import train

if not st.session_state.get("cards"):
    st.info("No deck loaded. Pick or create one first.")
    if st.button("Go to menu"):
        st.switch_page("views/prepare.py")
    st.stop()

train()
