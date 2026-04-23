"""
Login and registration page.
"""
import os
from urllib.parse import urlencode

import streamlit as st

from utils.auth import (
    INTEREST_OPTIONS,
    google_oauth_upsert,
    is_logged_in,
    login_user,
    logout,
    register_user,
    set_session_user,
)


def _get_secret(key: str, default: str = "") -> str:
    try:
        return str(st.secrets[key]).strip()
    except (KeyError, FileNotFoundError):
        return default


def _load_styles() -> None:
    css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("# AI Quiz App")
        st.caption("Powered by Google Gemini")
        st.divider()
        if is_logged_in():
            user = st.session_state.get("user", {})
            st.markdown(f"**{user.get('name', 'User')}**")
            if st.button("Logout", use_container_width=True, key="auth_sidebar_logout"):
                logout()
                st.rerun()


def _render_google_section() -> None:
    st.markdown("<div class='auth-divider'>OR continue with Google</div>", unsafe_allow_html=True)

    google_client_id = _get_secret("GOOGLE_CLIENT_ID")
    google_client_secret = _get_secret("GOOGLE_CLIENT_SECRET")

    if not google_client_id or not google_client_secret:
        st.info(
            "Google sign-in is not configured yet. Add GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET in `.streamlit/secrets.toml`."
        )
        return

    redirect_uri = _get_secret("GOOGLE_REDIRECT_URI", "https://quiz-app-rhs.streamlit.app/Login")
    params = {
        "client_id": google_client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid email profile",
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    st.link_button("Continue with Google", auth_url, use_container_width=True)

    query_params = st.query_params
    auth_code = query_params.get("code")
    if isinstance(auth_code, list):
        auth_code = auth_code[0] if auth_code else None

    if not auth_code:
        return

    try:
        import requests as req

        token_resp = req.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": auth_code,
                "client_id": google_client_id,
                "client_secret": google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=25,
        )
        tokens = token_resp.json()

        if "access_token" not in tokens:
            st.error("OAuth token exchange failed. Please try again.")
            return

        user_resp = req.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            timeout=25,
        )
        guser = user_resp.json()

        db_user = google_oauth_upsert(
            google_id=guser.get("id"),
            name=guser.get("name", "Google User"),
            email=guser.get("email"),
            avatar_url=guser.get("picture"),
        )

        if not db_user:
            st.error("Failed to create your account. Please try again.")
            return

        set_session_user(db_user)
        st.query_params.clear()
        st.success("Signed in with Google.")
        st.rerun()
    except Exception as exc:
        st.error(f"Google sign-in error: {exc}")


def _render_login_form(status_slot) -> None:
    with st.form("login_form", clear_on_submit=False):
        st.markdown("### Welcome Back")
        email = st.text_input("Email", placeholder="you@example.com")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        login_click = st.form_submit_button("Login", use_container_width=True)

    if login_click:
        if not email or not password:
            status_slot.error("Please fill in email and password.")
            return

        result = login_user(email.strip(), password)
        if result["success"]:
            set_session_user(result["user"])
            status_slot.success("Login successful. Redirecting...")
            st.rerun()
        else:
            status_slot.error(result["message"])

    st.markdown(
        "<p class='soft-note'>Default admin login: <b>admin@quizapp.com</b> / <b>admin123</b></p>",
        unsafe_allow_html=True,
    )


def _render_register_form(status_slot) -> None:
    with st.form("register_form", clear_on_submit=False):
        st.markdown("### Create Your Account")
        reg_name = st.text_input("Full Name", placeholder="John Doe")
        reg_email = st.text_input("Email", placeholder="you@example.com")
        reg_password = st.text_input("Password", type="password", placeholder="Minimum 6 characters")
        reg_confirm = st.text_input("Confirm Password", type="password", placeholder="Re-enter password")

        st.caption("Select interests for personalized quizzes")
        selected_interests = st.multiselect(
            "Interests",
            options=INTEREST_OPTIONS,
            default=[],
            placeholder="Choose one or more topics",
        )
        custom_interest = st.text_input("Custom Interest (optional)", placeholder="e.g., Cloud Computing")

        register_click = st.form_submit_button("Create Account", use_container_width=True)

    if register_click:
        if not reg_name or not reg_email or not reg_password:
            status_slot.error("Please complete all required fields.")
            return
        if len(reg_password) < 6:
            status_slot.error("Password must be at least 6 characters.")
            return
        if reg_password != reg_confirm:
            status_slot.error("Passwords do not match.")
            return

        interests = selected_interests[:]
        if custom_interest.strip():
            interests.append(custom_interest.strip())

        result = register_user(reg_name.strip(), reg_email.strip(), reg_password, interests)
        if result["success"]:
            set_session_user(result["user"])
            status_slot.success("Account created successfully. Redirecting...")
            st.rerun()
        else:
            status_slot.error(result["message"])


def _render_footer_switch(mode: str) -> None:
    if mode == "Login":
        left, right = st.columns([2, 1])
        with left:
            st.markdown("<p class='soft-note' style='text-align:left;'>New here?</p>", unsafe_allow_html=True)
        with right:
            if st.button("Register", use_container_width=True, key="switch_to_register"):
                st.session_state["auth_mode"] = "Register"
                st.rerun()
    else:
        left, right = st.columns([2, 1])
        with left:
            st.markdown("<p class='soft-note' style='text-align:left;'>Already have an account?</p>", unsafe_allow_html=True)
        with right:
            if st.button("Login", use_container_width=True, key="switch_to_login"):
                st.session_state["auth_mode"] = "Login"
                st.rerun()


st.set_page_config(page_title="Login - AI Quiz App", page_icon="🔐", layout="wide")
_load_styles()
_render_sidebar()

if is_logged_in():
    st.success(f"You are already logged in as {st.session_state['user_name']}.")
    st.info("Use the sidebar to open Dashboard or Quiz.")
    st.stop()

if "auth_mode" not in st.session_state:
    st.session_state["auth_mode"] = "Login"

st.markdown("<div class='page-shell'>", unsafe_allow_html=True)
st.markdown("<div class='auth-shell'>", unsafe_allow_html=True)
st.markdown(
    """
    <div class='auth-head'>
        <p class='section-kicker'>Secure Access</p>
        <h1 class='auth-title'>AI Quiz App</h1>
        <p class='auth-sub'>A focused sign-in flow designed for quick access and clear feedback.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

mode = st.radio(
    "Auth Mode",
    ["Login", "Register"],
    key="auth_mode",
    horizontal=True,
    label_visibility="collapsed",
)

st.markdown("<div class='auth-card'>", unsafe_allow_html=True)
status_slot = st.empty()
status_slot.markdown("<div class='auth-status-slot'></div>", unsafe_allow_html=True)

if mode == "Login":
    _render_login_form(status_slot)
else:
    _render_register_form(status_slot)

_render_google_section()
st.markdown("<hr class='subtle-divider' />", unsafe_allow_html=True)
_render_footer_switch(mode)

st.markdown("</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)
