import streamlit as st
import random
from audio import rec_audio, play_target
from utills import parse_flashcards, similarity
from db import submit_ai_key, get_user_data, save_new_deck, remove_decks, remove_cards, \
    get_cards_of_decks, get_cards_for_decks, get_cards_by_ids, \
    save_ai_explanation, add_attempt, add_streak_to_card, update_user_vocabulary, \
    prepare_random_deck, get_deck_cards_ordered, \
    upload_deck_audio, get_deck_audio_bytes, deck_audio_exists, \
    get_user_preferences, save_user_preferences, rename_deck, merge_decks
from ai import explain_phrase
from audio import build_deck_audio, join_deck_audios
from languages import LANGUAGES, language_name

PAGE_PATHS = {
    "decks": "views/decks.py",
    "train": "views/train.py",
    "study": "views/study.py",
    "listen": "views/listen.py",
    "load": "views/load_cards.py",
    "get_ai": "views/get_ai.py",
    "preferences": "views/preferences.py",
}


def goto(mode: str):
    st.switch_page(PAGE_PATHS[mode])


def unload_flashcards():
    st.session_state.flashcards = {}
    st.session_state.cards = []
    st.session_state.training_started = False


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
    if st.session_state.index < len(st.session_state.cards) - 1:
        st.session_state.index += 1
        if st.session_state.ui_answer:
            st.session_state.ui_answer = ""
    else:
        st.session_state.training_started = False
        goto("decks")


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
        raw_text = st.text_area("Paste JSON or text here", height=200)
        if raw_text:
            try:
                flashcards = parse_flashcards(raw_text)
            except Exception as e:
                st.error(f"Invalid input: {e}")
    else:
        uploaded = st.file_uploader("Upload file", type=["json", "txt"])
        if uploaded:
            try:
                content = uploaded.read().decode("utf-8")
                flashcards = parse_flashcards(content)
            except Exception as e:
                st.error(f"Invalid file: {e}")

    if st.button("Cancel"):
        unload_flashcards()
        goto("decks")

    if flashcards:
        st.session_state.flashcards = flashcards
        if st.button("Save deck"):
            if deck_name:
                if save_new_deck(deck_name):
                    st.session_state.deck = deck_name
                    unload_flashcards()
                    goto("decks")
            else:
                st.warning("Please provide a deck name.")


def get_ai():
    st.markdown("""
    ## AI Functionality
    Enabling AI features will allow you to:
    * **Explain complex sentences** instantly.
    * **Translate** words or sentences from your native language.
    * **Generate personalized decks** based on weaknesses in your training sessions.
    """)

    st.markdown("""
    > :warning: **Requirements:** To use these features, you need an OpenAI account with an active credit balance (a minimum of $5–$10 will last for a very long time).
    """)

    ai_key = st.text_input(
        label="OpenAI API Key",
        type="password",
        help="You can find or create your API key in your OpenAI developer dashboard."
    )
    if ai_key:
        submit_ai_key(ai_key)

    if st.button("Back"):
        goto("decks")


def _render_multi_deck_audio_panel(deck_names: list, deck_ids: list):
    st.subheader(f"🔊 Deck audio — {len(deck_ids)} decks")

    name_by_id = dict(zip(deck_ids, deck_names))
    missing = [did for did in deck_ids if not deck_audio_exists(did)]

    if missing:
        st.caption(
            f"{len(deck_ids) - len(missing)} of {len(deck_ids)} decks have audio. "
            f"Missing: {', '.join(name_by_id[d] for d in missing)}."
        )
        if st.button(f"Generate audio for {len(missing)} missing deck(s)"):
            progress = st.progress(0.0)
            for i, did in enumerate(missing, start=1):
                with st.spinner(f"Rendering {name_by_id[did]}…"):
                    cards = get_deck_cards_ordered(did)
                    if not cards:
                        st.warning(f"{name_by_id[did]} has no cards — skipped.")
                    else:
                        audio_bytes = build_deck_audio(cards)
                        if not upload_deck_audio(did, audio_bytes):
                            st.error(f"Failed to upload {name_by_id[did]}.")
                            return
                progress.progress(i / len(missing))
            st.success("All missing decks generated.")
            st.rerun()
        return

    cache_key = f"joined_audio_{'_'.join(str(d) for d in sorted(deck_ids))}"
    joined = st.session_state.get(cache_key)
    if joined is None:
        with st.spinner("Stitching decks together…"):
            blobs = [get_deck_audio_bytes(did) for did in deck_ids]
            blobs = [b for b in blobs if b]
            joined = join_deck_audios(blobs)
            st.session_state[cache_key] = joined

    if not joined:
        st.warning("Could not load audio for the selected decks.")
        return

    loop = st.toggle("🔁 Loop", value=False, key=f"loop_multi_{'_'.join(str(d) for d in sorted(deck_ids))}")
    st.audio(joined, format="audio/mpeg", loop=loop)
    st.caption(f"Playing: {' → '.join(deck_names)}")


def _render_deck_audio_panel(deck_name: str, deck_id: int):
    st.subheader(f"🔊 Deck audio — {deck_name}")
    exists = deck_audio_exists(deck_id)

    if exists:
        audio_bytes = get_deck_audio_bytes(deck_id)
        if audio_bytes:
            loop = st.toggle("🔁 Loop", value=False, key=f"loop_{deck_id}")
            st.audio(audio_bytes, format="audio/mpeg", loop=loop)
        regenerate = st.button("Regenerate audio")
    else:
        st.caption("No audio yet for this deck.")
        regenerate = st.button("Generate audio")

    if regenerate:
        cards = get_deck_cards_ordered(deck_id)
        if not cards:
            st.warning("Deck has no cards.")
            return
        with st.spinner(f"Rendering audio for {len(cards)} cards…"):
            audio_bytes = build_deck_audio(cards)
        with st.spinner("Uploading…"):
            if upload_deck_audio(deck_id, audio_bytes):
                for k in list(st.session_state.keys()):
                    if k.startswith("joined_audio_"):
                        st.session_state.pop(k, None)
                st.success("Audio saved.")
                st.rerun()


def preferences_view():
    st.header("🌐 Language settings")

    current_native = st.session_state.get("native_lang")
    current_target = st.session_state.get("lang")
    has_prefs = bool(current_native and current_target)

    codes = list(LANGUAGES.keys())

    def _index(code, fallback):
        return codes.index(code) if code in codes else codes.index(fallback)

    native = st.selectbox(
        "Your native language",
        codes,
        format_func=lambda c: LANGUAGES[c],
        index=_index(current_native, "en"),
    )
    target = st.selectbox(
        "Language you want to learn",
        codes,
        format_func=lambda c: LANGUAGES[c],
        index=_index(current_target, "ru" if native != "ru" else "en"),
    )

    if native == target:
        st.warning("Native and target language must differ.")
        return

    if st.button("Save", type="primary"):
        if save_user_preferences(native, target):
            st.session_state.native_lang = native
            st.session_state.lang = target
            st.session_state.decks = {}
            unload_flashcards()
            st.success("Languages saved.")
            st.rerun()

    if has_prefs:
        if st.button("Back to decks"):
            goto("decks")


def decks_view():
    st.header("🗂 Decks")
    get_user_data()
    decks_dict = st.session_state.get("decks") or {}

    if not decks_dict:
        st.info("You have no decks yet. Create one from **New deck**.")
        if st.button("✨ Create training set from your weak cards"):
            prepare_random_deck()
            st.session_state.selected_deck_ids = []
            st.session_state.selected_deck_names = []
            st.session_state.selected_card_ids = []
            st.session_state.training_started = False
            goto("train")
        return

    selected_names = st.multiselect("Decks", list(decks_dict.keys()))
    selected_deck_ids = [decks_dict[name] for name in selected_names]

    cards_options = {}
    selected_card_ids = []
    if selected_deck_ids:
        cards_options = get_cards_of_decks(selected_deck_ids)
        if cards_options:
            card_selected_keys = st.multiselect(
                "Cards (optional — leave empty to use all cards in the deck)",
                list(cards_options.keys()),
            )
            selected_card_ids = [cards_options[k] for k in card_selected_keys]

    st.session_state.selected_deck_ids = selected_deck_ids
    st.session_state.selected_deck_names = selected_names
    st.session_state.selected_card_ids = selected_card_ids

    tab_train, tab_edit = st.tabs(["🎯 Train", "✏️ Edit decks"])

    with tab_train:
        if selected_deck_ids:
            cols = st.columns(3)
            if cols[0].button("🧪 Test", use_container_width=True):
                st.session_state.training_started = False
                goto("train")
            if cols[1].button("📖 Study", use_container_width=True):
                st.session_state.study_started = False
                goto("study")
            if cols[2].button("🔊 Listen", use_container_width=True):
                goto("listen")
        else:
            st.caption("Select one or more decks above to start training.")

        st.divider()
        if st.button("✨ Create training set from your weak cards"):
            prepare_random_deck()
            st.session_state.selected_deck_ids = []
            st.session_state.selected_deck_names = []
            st.session_state.selected_card_ids = []
            st.session_state.training_started = False
            goto("train")

    with tab_edit:
        if not selected_deck_ids:
            st.caption("Select one or more decks above to edit them.")
        else:
            mgmt_cols = st.columns(2)
            if selected_card_ids:
                if mgmt_cols[0].button("Remove cards", use_container_width=True):
                    if remove_cards(selected_card_ids):
                        st.success(f"Removed {len(selected_card_ids)} card(s).")
                        st.rerun()
            if mgmt_cols[1].button("🗑 Delete decks", use_container_width=True):
                if remove_decks(selected_deck_ids):
                    st.success(f"Deleted {len(selected_deck_ids)} deck(s).")
                    unload_flashcards()
                    st.rerun()

            st.divider()

            if len(selected_deck_ids) == 1:
                with st.expander("✏️ Rename deck"):
                    current_name = selected_names[0]
                    new_name = st.text_input("New name", value=current_name, key="rename_input")
                    if st.button("Save name", key="rename_save"):
                        if new_name.strip() and new_name.strip() != current_name:
                            if rename_deck(selected_deck_ids[0], new_name):
                                st.success("Deck renamed.")
                                st.rerun()
                        else:
                            st.warning("Pick a different, non-empty name.")
            else:
                with st.expander(f"🔗 Merge {len(selected_deck_ids)} decks"):
                    merged_name = st.text_input(
                        "Name for the merged deck",
                        value=selected_names[0],
                        key="merge_input",
                    )
                    st.caption(
                        "All cards will be combined into a single deck. "
                        "Existing deck audio for the merged decks will be cleared."
                    )
                    if st.button("Merge", key="merge_save"):
                        target_id = merge_decks(selected_deck_ids, merged_name)
                        if target_id:
                            st.success(f"Merged into '{merged_name.strip()}'.")
                            unload_flashcards()
                            st.session_state.selected_deck_ids = []
                            st.session_state.selected_deck_names = []
                            st.session_state.selected_card_ids = []
                            st.rerun()


def listen_view():
    st.header("🔊 Listen")
    deck_ids = st.session_state.get("selected_deck_ids") or []
    deck_names = st.session_state.get("selected_deck_names") or []

    if not deck_ids:
        st.info("Pick decks from the **Decks** view first.")
        if st.button("Back to decks"):
            goto("decks")
        return

    if len(deck_ids) == 1:
        _render_deck_audio_panel(deck_names[0], deck_ids[0])
    else:
        _render_multi_deck_audio_panel(deck_names, deck_ids)

    if st.button("Back to decks"):
        goto("decks")


def study_view():
    st.header("📖 Study")
    deck_ids = st.session_state.get("selected_deck_ids") or []
    deck_names = st.session_state.get("selected_deck_names") or []

    if not deck_ids and not st.session_state.get("flashcards"):
        st.info("Pick decks from the **Decks** view first.")
        if st.button("Back to decks"):
            goto("decks")
        return

    if not st.session_state.get("study_started"):
        if deck_names:
            st.caption(f"Decks: {', '.join(deck_names)}")
        st.session_state.shuffle = st.checkbox("Shuffle cards", value=st.session_state.get("shuffle", True))
        col1, col2 = st.columns(2)
        if col1.button("Start", type="primary"):
            _load_training_flashcards()
            if not st.session_state.flashcards:
                st.warning("No cards to study.")
                return
            prep_cards()
            st.session_state.study_started = True
            st.rerun()
        if col2.button("Back to decks"):
            goto("decks")
        return

    cards = st.session_state.cards
    index = st.session_state.index
    deck_size = len(cards)
    front, back_data = cards[index]

    st.write(f"**Card: {index + 1} / {deck_size}**")
    st.markdown(
        f"<div style='font-size:24px; font-weight:600'>{front}</div>",
        unsafe_allow_html=True,
    )
    st.markdown("")
    st.markdown(
        f"<div style='font-size:24px; font-weight:600; color:#4CAF50'>Solution: {back_data[0]}</div>",
        unsafe_allow_html=True,
    )

    st.write("🔊 Listen to pronunciation:")
    if st.session_state.get("tts_for_index") != index or index == 0:
        st.session_state.tts_audio = play_target(back_data[0])
    st.session_state.tts_for_index = index
    if st.session_state.tts_audio:
        st.audio(st.session_state.tts_audio)

    st.divider()

    col1, col2 = st.columns(2)
    if col1.button("Back to decks"):
        st.session_state.study_started = False
        goto("decks")
    if index + 1 < deck_size:
        if col2.button("Next ➡"):
            st.session_state.index += 1
            st.rerun()
    else:
        st.success("You've reviewed all cards!")
        if col2.button("Start over"):
            prep_cards()
            st.rerun()


def _load_training_flashcards():
    card_ids = st.session_state.get("selected_card_ids") or []
    deck_ids = st.session_state.get("selected_deck_ids") or []
    if card_ids:
        st.session_state.flashcards = get_cards_by_ids(card_ids)
    elif deck_ids:
        st.session_state.flashcards = get_cards_for_decks(deck_ids)
    # else: already set (e.g. weakness deck via prepare_random_deck)


def _train_setup():
    deck_names = st.session_state.get("selected_deck_names") or []
    card_ids = st.session_state.get("selected_card_ids") or []
    deck_ids = st.session_state.get("selected_deck_ids") or []
    has_preloaded = bool(st.session_state.get("flashcards")) and not deck_ids and not card_ids

    st.header("🧪 Set up test")
    if deck_names:
        st.caption(f"Decks: {', '.join(deck_names)}")
    if card_ids:
        st.caption(f"Testing on {len(card_ids)} selected card(s).")
    elif has_preloaded:
        st.caption(f"Testing on {len(st.session_state.flashcards)} weak card(s).")
    elif deck_ids:
        st.caption("Testing on all cards from the selected deck(s).")
    else:
        st.info("Pick decks from the **Decks** view first.")
        if st.button("Back to decks"):
            goto("decks")
        return

    mode = st.radio(
        "Test mode",
        ["✍️ Writing", "🎤 Speaking"],
        horizontal=True,
    )
    st.session_state.shuffle = st.checkbox("Shuffle cards", value=st.session_state.get("shuffle", True))

    col1, col2 = st.columns(2)
    if col1.button("Start", type="primary"):
        if not has_preloaded:
            _load_training_flashcards()
        if not st.session_state.flashcards:
            st.warning("No cards to train on.")
            return
        st.session_state.routine = mode
        clear_memory()
        prep_cards()
        st.session_state.training_started = True
        st.rerun()
    if col2.button("Back to decks"):
        goto("decks")


def train():
    if not st.session_state.get("training_started"):
        _train_setup()
        return

    st.header("🧪 Test yourself!")
    st.write(st.session_state.routine)
    current_index = st.session_state.index
    english, russian = st.session_state.cards[current_index]
    deck_size = len(st.session_state.flashcards)

    st.write(f"**Card: {current_index + 1} / {deck_size}**")

    st.markdown(
        f"<div style='font-size:24px; font-weight:600'>{english}</div>",
        unsafe_allow_html=True
    )
    st.markdown('''


    ''')

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
                add_attempt(russian[2], russian[0], user_input, score, "writing")
                add_streak_to_card(russian[2], score > 0.8)
                if st.session_state.get("user"):
                    update_user_vocabulary(russian[0], user_input, st.session_state.lang, st.session_state.user["id"])
                st.session_state.attempt_added = True

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
                add_streak_to_card(russian[2], score > 0.8)
                if st.session_state.get("user"):
                    update_user_vocabulary(russian[0], user_input, st.session_state.lang, st.session_state.user["id"])
                st.session_state.attempt_added = True

    if st.session_state.submitted == True:
        st.write("🔊 Listen to pronunciation:")

        if st.session_state.tts_for_index != current_index or current_index == 0:
            st.session_state.tts_audio = play_target(russian[0])
        st.session_state.tts_for_index = current_index
        if st.session_state.tts_audio:
            st.audio(st.session_state.tts_audio)

        st.divider()

        ai_explanation = ""
        if st.button("Ask AI for explanation"):
            ai_explanation = explain_phrase(
                russian[0],
                st.session_state.ai_api,
                target_language=language_name(st.session_state.get("lang")),
                native_language=language_name(st.session_state.get("native_lang")),
            )
            if save_ai_explanation(russian[2], ai_explanation):
                st.success("The explanation has been saved")
                russian[1] = ai_explanation
            else:
                st.error("Error saving the explanation")
        else:
            ai_explanation = russian[1]

        if not ai_explanation:
            pass
        elif len(ai_explanation) < 30:
            st.markdown(ai_explanation)
        else:
            ai_explanation = ai_explanation.replace("-", "\n-")
            with st.expander("💡 View Explanation & Grammar Notes"):
                if "**Grammar Notes:**" in ai_explanation:
                    gloser, grammatikk = ai_explanation.split("**Grammar Notes:**")
                    st.markdown("### 🔤 Word-by-Word Breakdown")
                    st.markdown(gloser.strip())
                    st.info(grammatikk.strip(), icon="📝")
                else:
                    st.markdown(ai_explanation)

    col1, col2 = st.columns(2)

    if col1.button("Back to decks"):
        st.session_state.training_started = False
        goto("decks")
    if current_index + 1 < deck_size:
        col2.button("Next ➡", key="but_next", on_click=next_card)

    if st.session_state.stats and st.session_state.routine != "Practice":
        st.divider()
        st.header("📊 Progress")
        if len(st.session_state.stats) > 0:
            avg_score = sum(st.session_state.stats.values()) / len(st.session_state.stats)
            st.metric("Average score", f"{avg_score:.2f}")
