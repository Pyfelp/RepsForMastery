from operator import truediv

import streamlit as st
from db import get_supabase




def _restore_session():
    if st.session_state.get("user"):
        return
    tokens = st.session_state.get("auth_tokens")
    #if not tokens:
        #return
    try:
        client = get_supabase()
        client.auth.set_session(tokens["access_token"], tokens["refresh_token"])
        user_resp = client.auth.get_user()
        if user_resp and user_resp.user:
            st.session_state.user = {
                "id": user_resp.user.id,
                "email": user_resp.user.email,
            }
    except Exception:
        st.session_state.pop("auth_tokens", None)


def sign_up(email: str, password: str):
    client = get_supabase()
    return client.auth.sign_up({"email": email, "password": password})


def sign_in(email: str, password: str):
    client = get_supabase()
    res = client.auth.sign_in_with_password({"email": email, "password": password})
    if res.session and res.user:
        st.session_state.auth_tokens = {
            "access_token": res.session.access_token,
            "refresh_token": res.session.refresh_token,
        }
        st.session_state.user = {"id": res.user.id, "email": res.user.email}

    return res


def sign_out():
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    for key in ("user", "auth_tokens"):
        st.session_state.pop(key, None)


def auth_gate() -> bool:
    """Render auth UI if the user isn't signed in. Returns True if authenticated."""
    _restore_session()
    if st.session_state.get("user"):
        return True

    st.title("🇷🇺 Reps for Mastery")
    tab_login, tab_signup = st.tabs(["Log in", "Sign up"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log in")
        if submitted:
            try:
                sign_in(email, password)
                st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")

    with tab_signup:
        with st.form("signup_form"):
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            submitted = st.form_submit_button("Sign up")
        if submitted:
            try:
                res = sign_up(email, password)
                if res.session and res.user:
                    st.session_state.auth_tokens = {
                        "access_token": res.session.access_token,
                        "refresh_token": res.session.refresh_token,
                    }
                    st.session_state.user = {"id": res.user.id, "email": res.user.email}
                    st.rerun()
                else:
                    st.success("Account created. Check your email to confirm, then log in.")
            except Exception as e:
                st.error(f"Sign-up failed: {e}")

    return False


def logout_button():
    user = st.session_state.get("user")
    if not user:
        return
    with st.sidebar:
        st.write(f"Signed in as **{user['email']}**")
        if st.button("Log out"):
            sign_out()
            st.rerun()


