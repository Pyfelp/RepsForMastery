import streamlit as st
import random
from audio import rec_audio, play_russian
from utills import parse_flashcards, similarity
def goto(mode:str):
    st.session_state.mode = mode
    st.rerun()

def clear_memory():
    st.session_state.submitted = False
    st.session_state.user_input = ""
    st.session_state.score = 0
def prep_cards():
    cards = list(st.session_state.flashcards.items())
    if st.session_state.shuffle:
        random.shuffle(cards)

    st.session_state.cards = cards
    st.session_state.index = 0
    st.session_state.stats = {}

def next_card():
    clear_memory()
    if st.session_state.index < len(st.session_state.cards)-1:
        st.session_state.index += 1
        if st.session_state.ui_answer:
            st.session_state.ui_answer=""
    else:
        goto("prepare")
def input_change():
    st.session_state.submitted = True

def load_cards(from_start_train = False):
    st.header("📥 Load your training data")
    st.markdown("""


    Your training data must be in **JSON** format or **TXT** format.   

    **JSON example:**
    ```json
    {
      "Hello": "Привет",
      "How are you?": "Как дела?"
    }
    """)
    st.markdown("""
        In text format use `::` as seperator between excercise/question and solution/answer

        **TXT example:**
        ```txt

          Hello::"Привет
          How are you? :: Как дела?

        """)

    input_method = st.radio(
        "How do you want to load your training data?",
        ["Paste/write", "Upload File"]
    )

    flashcards = None

    if input_method == "Paste/write":
        raw_text = st.text_area(
            "Paste JSON or text here",
            height=200
        )

        if raw_text:
            try:
                flashcards = parse_flashcards(raw_text)
            except Exception as e:
                st.error(f"Invalid input: {e}")

    else:
        uploaded = st.file_uploader(
            "Upload file",
            type=["json", "txt"]
        )

        if uploaded:
            try:
                content = uploaded.read().decode("utf-8")
                flashcards = parse_flashcards(content)
            except Exception as e:
                st.error(f"Invalid file: {e}")

    if flashcards:
        st.session_state.flashcards = flashcards
        goto("prepare")
    # ---------------------------
    # 2️⃣ PREPARE SESSION CARDS
    # ---------------------------
def prep():
    st.session_state.load_from_start = False
    flashcards = st.session_state.flashcards

    if len(flashcards) != 0:
        st.success(f"Loaded {len(flashcards)} cards")

        st.session_state.shuffle = st.checkbox("Shuffle cards", value=True)
        st.session_state.routine = st.radio(
            "Training mode",
            ["✍️ Writing", "🎤 Speaking", "See cards without test"],
            horizontal=True
        )


        col1, col2, col3 = st.columns(3)
        if col1.button("Start training"):
            clear_memory()
            prep_cards()
            goto("train")
        if col2.button("Load new data"):
            goto("load")
    else:
        if st.button("Start training"):
            st.session_state.load_from_start = True
            goto("load")

def train():
    st.header("🧠 Put in some reps!")
    current_index = st.session_state.index
    english, russian = st.session_state.cards[current_index]

    st.write(f"**Excercise: {current_index + 1}**")

    st.markdown(
        f"<div style='font-size:24px; font-weight:600'>{english}</div>",
        unsafe_allow_html=True
    )
    st.markdown('''


    ''')

    # -----------------------
    # ✍️ WRITING MODE
    # -----------------------
    if st.session_state.routine == "✍️ Writing":

        if st.session_state.submitted == False:
            user_input = st.text_input("Your answer", key="ui_answer", autocomplete='off')
            if user_input:
                st.session_state.score = similarity(user_input, russian)
                st.session_state.user_input = user_input
                st.session_state.submitted = True
                st.rerun()

            if st.button("Submit and see solution"):
                score = 0
                st.session_state.submitted = True
                st.session_state.stats[english] = score
                st.rerun()

        elif st.session_state.submitted == True:
            st.text_input("Your answer", value=st.session_state.user_input)
            st.markdown('''


            ''')
            st.markdown('**Solution:**')
            st.markdown(
                f"<div style='font-size:24px; font-weight:600'>{russian}</div>",
                unsafe_allow_html=True
            )
            st.markdown('''


            ''')

            score = st.session_state.score

            if score > 0.8:
                st.success("✅ Correct")
            elif score > 0.6:
                st.warning("🟡 Almost")
            elif score == 0:
                st.write("**No score**")
            else:
                st.error("❌ Incorrect")
            st.session_state.stats[english] = score



    elif st.session_state.routine == "See cards without test":
        st.markdown(
            f"<div style='font-size:24px; font-weight:600'>Solution: {russian}</div>",
            unsafe_allow_html=True
        )
    # -----------------------
    # 🎤 SPEAKING MODE (STUB)
    # -----------------------
    else:
        if st.session_state.submitted == False:

            user_input = rec_audio()
            if user_input:
                st.session_state.score = similarity(user_input, russian)
                st.session_state.user_input = user_input
                st.session_state.submitted = True
                st.rerun()

            if st.button("See and listen to solution"):
                score = 0
                st.session_state.submitted = True
                st.session_state.stats[english] = score
                st.rerun()

        elif st.session_state.submitted == True:
            score = st.session_state.score
            user_input = st.session_state.user_input
            st.write(f"You said: **{user_input}**")
            st.write(f"Correct: **{russian}**")
            st.write(f"Score: **{score:.2f}**")

            if score > 0.8:
                st.success("✅ Good pronunciation!")
            elif score > 0.6:
                st.warning("🟡 Almost")
            elif score > 0:
                st.error("❌ Not correct")
    # -----------------------
    # 🔊 PRONUNCIATION
    # -----------------------
    if st.session_state.routine == "See cards without test" or st.session_state.submitted == True:
        st.write("🔊 Listen to pronunciation:")

        if st.session_state.tts_for_index != current_index or current_index == 0:
            st.session_state.tts_audio = play_russian(russian)
        st.session_state.tts_for_index = current_index
        if st.session_state.tts_audio:
            st.audio(st.session_state.tts_audio, format="audio/mp3")

    col1, col2 = st.columns(2)

    if col1.button("Cancel session"):
        goto("prepare")

    col2.button(
        "Next ➡",
        key="but_next",
        on_click=next_card
    )

    # ---------------------------
    # 4️⃣ PROGRESS TRACKING
    # ---------------------------
    if st.session_state.stats and   st.session_state.routine != "See cards without test":
        st.divider()
        st.header("📊 Progress")
        if len(st.session_state.stats) > 0:
            avg_score = sum(st.session_state.stats.values()) / len(st.session_state.stats)
            st.metric("Average score", f"{avg_score:.2f}")

        weak = [k for k, v in st.session_state.stats.items() if v < 0.7]
        if weak:
            st.write("⚠️ Cards to review:")
            st.write(weak)
