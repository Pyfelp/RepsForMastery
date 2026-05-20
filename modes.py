import streamlit as st
import random
from audio import rec_audio, play_russian
from utills import parse_flashcards, similarity
from db import submit_ai_key, get_user_data, get_deck, save_new_deck, remove_decks, remove_cards, get_cards_of_decks, \
    save_ai_explanation, add_attempt, prepare_random_deck
from ai import explain_phrase
def goto(mode:str):
    st.session_state.mode = mode
    st.rerun()
def unload_flashcards():
    st.session_state.flashcards = {}

def clear_memory():
    st.session_state.submitted = False
    st.session_state.user_input = ""
    st.session_state.attempt_added = False
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

def load_cards():
    st.header("📥 Create a new deck")

    deck_name = st.text_input("Name of the deck")
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

          Hello::Привет
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
    if st.button("Cancel"):
        unload_flashcards()
        goto("prepare")

    if flashcards:
        st.session_state.flashcards = flashcards
        if st.button("Save deck"):
            if deck_name:
                if save_new_deck(deck_name):
                    st.session_state.deck = deck_name
                    goto("prepare")
            else:
                st.warning("Please provide a deck name.")
    # ---------------------------
    # 2️⃣ PREPARE SESSION CARDS
    # ---------------------------

def get_ai():
    st.markdown("""
    ## AI Functionality
    Enabling AI features will allow you to:
    * **Explain complex sentences** instantly.
    * **Translate** words or sentences from your native language.
    * **Generate personalized decks** based on weaknesses in your training sessions.
    """)

    # Viktig informasjon om oppsett og kostnader
    st.markdown("""
    > :warning: **Requirements:** To use these features, you need an OpenAI account with an active credit balance (a minimum of $5–$10 will last for a very long time).
    """)

    # Inntastingsfelt for API-nøkkel med hjelpetekst
    ai_key = st.text_input(
        label="OpenAI API Key",
        type="password",
        help="You can find or create your API key in your OpenAI developer dashboard."
    )
    if ai_key:
        submit_ai_key(ai_key)

    if st.button("Back"):
        goto("prepare")
def manage_decks():
    st.header("🗂 Manage decks")
    get_user_data()
    decks_dict = st.session_state.get("decks") or []
    if not decks_dict:
        st.info("You have no decks yet.")
        if st.button("Back"):
            goto("prepare")
        return


    selected_names = st.multiselect("Decks", decks_dict.keys())
    selected_deck_ids = [decks_dict[name] for name in selected_names]

    if selected_deck_ids:
        col1, col2 = st.columns(2)
        if col1.button("Edit decks"):
            st.session_state.editing_decks = selected_deck_ids
        if col2.button("Delete decks"):
            if remove_decks(selected_deck_ids):
                st.session_state.pop("editing_decks", None)
                st.success(f"Deleted {len(selected_deck_ids)} deck(s).")
                unload_flashcards()
                st.rerun()

    editing = st.session_state.get("editing_decks")
    if editing:
        cards_options = get_cards_of_decks(editing)
        if not cards_options:
            st.info("No cards in the selected decks.")
        else:
            card_selected_keys = st.multiselect("Cards", list(cards_options.keys()))
            card_ids = [cards_options[k] for k in card_selected_keys]
            if card_ids and st.button("Remove cards"):
                if remove_cards(card_ids):
                    st.success(f"Removed {len(card_ids)} card(s).")
                    unload_flashcards()
                    st.rerun()

    if st.button("Back to menu"):
        st.session_state.pop("editing_decks", None)

        if st.session_state.prev_mode ==     st.session_state.mode:
            goto("prepare")
        elif st.session_state.prev_mode != "prepare":
            get_user_data()
            goto(st.session_state.prev_mode)
        else:
            goto("prepare")
def prep():
    flashcards = st.session_state.flashcards
    get_user_data()



    if st.session_state.decks:
        decks = st.session_state.get("decks")
        option_list = decks.keys()
        selected_deck = st.selectbox("Which deck will you train on?", option_list)
        selected_index = decks[selected_deck]


        if st.button("Load deck"):
            st.session_state.flashcards = get_deck(selected_index)
            st.session_state.deck = selected_deck
            st.session_state.load_from_start = True
            goto("prepare")
    else:
        st.markdown("""
        ### You have no decks to train on.
        """)
    if st.button("Create new deck"):
        st.session_state.load_from_start = True
        goto("load")
    if st.button("Create random deck based on your historic attempts"):
        prepare_random_deck()
        st.session_state.load_from_start = True
        st.rerun()

    if len(flashcards) != 0:
        st.success(f"Loaded {len(flashcards)} cards")

        col1, col2, col3 = st.columns(3)
        but1 = col1.button("Practice")

        but2 = col2.button("Challenge")

        challenge_mode = col3.radio(
            "Training mode",
            ["✍️ Writing", "🎤 Speaking"],
            horizontal=True
        )
        st.session_state.shuffle = col3.checkbox("Shuffle cards", value=True)
        if but1:
            st.session_state.routine = "Practice"
            clear_memory()
            prep_cards()
            goto("train")
        if but2:
            st.session_state.routine = challenge_mode
            clear_memory()
            prep_cards()
            goto("train")




def train():
    st.header("🧠 Put in some reps!")
    st.write(st.session_state.routine)
    current_index = st.session_state.index
    english, russian = st.session_state.cards[current_index]
    deck_size = len(st.session_state.flashcards)

    st.write(f"**Card: {current_index + 1}**")

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
                st.session_state.score = similarity(user_input, russian[0])
                st.session_state.user_input = user_input
                st.session_state.submitted = True
                st.rerun()

            if st.button("Submit and see solution"):
                score = 0
                st.session_state.submitted = True
                st.session_state.stats[english] = score
                st.rerun()

        elif st.session_state.submitted == True:
            user_input = st.text_input("Your answer", value=st.session_state.user_input)
            st.markdown('''


            ''')
            st.markdown('**Solution:**')
            st.markdown(
                f"<div style='font-size:24px; font-weight:600'>{russian[0]}</div>",
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
            if st.session_state.attempt_added == False:
                add_attempt(russian[2], russian[0], user_input, score, "speaking")
                st.session_state.attempt_added == True



    elif st.session_state.routine == "Practice":
        st.markdown(
            f"<div style='font-size:24px; font-weight:600'>Solution: {russian[0]}</div>",
            unsafe_allow_html=True
        )
    # -----------------------
    # 🎤 SPEAKING MODE (STUB)
    # -----------------------
    elif st.session_state.routine == "🎤 Speaking":
        if st.session_state.submitted == False:

            user_input = rec_audio()
            if user_input:
                st.session_state.score = similarity(user_input, russian[0])
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
            st.write(f"Correct: **{russian[0]}**")
            st.write(f"Score: **{score:.2f}**")

            if score > 0.8:
                st.success("✅ Good pronunciation!")
            elif score > 0.6:
                st.warning("🟡 Almost")
            elif score > 0:
                st.error("❌ Not correct")
            if st.session_state.attempt_added == False:
                add_attempt(russian[2], russian[0], user_input, score, "speaking")
                st.session_state.attempt_added == True
    # -----------------------
    # 🔊 PRONUNCIATION
    # -----------------------
    if st.session_state.routine == "Practice" or st.session_state.submitted == True:
        st.write("🔊 Listen to pronunciation:")

        if st.session_state.tts_for_index != current_index or current_index == 0:
            st.session_state.tts_audio = play_russian(russian[0])
        st.session_state.tts_for_index = current_index
        if st.session_state.tts_audio:
            st.audio(st.session_state.tts_audio)     # format="audio/aac"
        # ---------------------------
        # ⃣ AI
        # ---------------------------
        st.divider()

        ai_explanation = ""
        if st.button("Ask AI for explanation"):
            ai_explanation = explain_phrase(russian[0], st.session_state.ai_api)
            if save_ai_explanation(russian[2], ai_explanation):
                st.success("The explanation has been saved")
                russian[1] = ai_explanation
            else:
                st.error("Error saving the explanation")
        else:
            ai_explanation = russian[1]

        if len(ai_explanation) < 30:
            st.markdown(ai_explanation)
        else:
            ai_explanation = ai_explanation.replace("-", "\n-")
            with st.expander("💡 View Explanation & Grammar Notes"):
                # Vi splitter teksten ved '**Grammar Notes:**' for å gi dem ulike visuelle bokser
                if "**Grammar Notes:**" in ai_explanation:
                    gloser, grammatikk = ai_explanation.split("**Grammar Notes:**")

                    st.markdown("### 🔤 Word-by-Word Breakdown")
                    st.markdown(gloser.strip())

                    # Vi legger grammatikken i en egen infoboks for visuell kontrast
                    st.info(grammatikk.strip(), icon="📝")
                else:
                    # Fallback hvis AI-en formaterte teksten litt annerledes en gang
                    st.markdown(ai_explanation)




    col1, col2 = st.columns(2)

    if col1.button("Back to menu"):
        goto("prepare")
    if current_index + 1 < deck_size:
        col2.button(
            "Next ➡",
            key="but_next",
            on_click=next_card
        )


    # ---------------------------
    # 4️⃣ PROGRESS TRACKING
    # ---------------------------
    if st.session_state.stats and st.session_state.routine != "Practice":
        st.divider()
        st.header("📊 Progress")
        if len(st.session_state.stats) > 0:
            avg_score = sum(st.session_state.stats.values()) / len(st.session_state.stats)
            st.metric("Average score", f"{avg_score:.2f}")

        weak = [k for k, v in st.session_state.stats.items() if v < 0.7]

