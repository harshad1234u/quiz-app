"""
🔐 Login & Registration Page
"""
import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Login – AI Quiz App", page_icon="🔐", layout="wide")

css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from utils.auth import (
    login_user, register_user, set_session_user, is_logged_in,
    logout, INTEREST_OPTIONS, google_oauth_upsert
)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("# 🧠 AI Quiz App")
    st.caption("Powered by Google Gemini")
    st.divider()
    if is_logged_in():
        user = st.session_state.get("user", {})
        st.markdown(f"👋 **{user.get('name', 'User')}**")
        if st.button("🚪 Logout", use_container_width=True):
            logout()
            st.rerun()

# ─── Already Logged In ───────────────────────────────────────────────────────
if is_logged_in():
    st.success(f"✅ You are logged in as **{st.session_state['user_name']}**")
    st.info("Use the sidebar to navigate to other pages.")
    st.stop()

# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align: center; padding: 1rem 0;">
    <h1 style="font-size: 2.2rem; font-weight: 800;
        background: linear-gradient(135deg, #6C63FF, #00D2FF);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        🔐 Welcome Back
    </h1>
    <p style="color: #A0A4B8;">Sign in to continue your learning journey</p>
</div>
""", unsafe_allow_html=True)

# ─── Auth Tabs ────────────────────────────────────────────────────────────────
tab_login, tab_register, tab_google = st.tabs(["🔑 Login", "📝 Register", "🌐 Google Sign-In"])

# ─── Login Tab ────────────────────────────────────────────────────────────────
with tab_login:
    st.markdown("")
    col_left, col_form, col_right = st.columns([1, 2, 1])
    with col_form:
        with st.form("login_form"):
            st.markdown("#### Sign In")
            email = st.text_input("📧 Email", placeholder="you@example.com")
            password = st.text_input("🔒 Password", type="password", placeholder="Enter password")
            submitted = st.form_submit_button("🚀 Login", use_container_width=True)

            if submitted:
                if not email or not password:
                    st.error("Please fill in all fields.")
                else:
                    result = login_user(email.strip(), password)
                    if result["success"]:
                        set_session_user(result["user"])
                        st.success(result["message"])
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(result["message"])

        st.markdown(
            "<div style='text-align: center; color: #A0A4B8; font-size: 0.85rem; margin-top: 1rem;'>"
            "Default admin: <b>admin@quizapp.com</b> / <b>admin123</b>"
            "</div>",
            unsafe_allow_html=True
        )

# ─── Register Tab ─────────────────────────────────────────────────────────────
with tab_register:
    st.markdown("")
    col_left, col_form, col_right = st.columns([1, 2, 1])
    with col_form:
        with st.form("register_form"):
            st.markdown("#### Create Account")
            reg_name = st.text_input("👤 Full Name", placeholder="John Doe")
            reg_email = st.text_input("📧 Email", placeholder="you@example.com", key="reg_email")
            reg_password = st.text_input("🔒 Password", type="password", placeholder="Min. 6 characters", key="reg_pass")
            reg_confirm = st.text_input("🔒 Confirm Password", type="password", placeholder="Re-enter password", key="reg_confirm")

            st.markdown("##### 🎯 Select Your Interests")
            st.caption("Choose topics you're interested in for personalized quizzes")

            # Interest checkboxes in two columns
            int_cols = st.columns(2)
            selected_interests = []
            for i, interest in enumerate(INTEREST_OPTIONS):
                with int_cols[i % 2]:
                    if st.checkbox(interest, key=f"int_{interest}"):
                        selected_interests.append(interest)

            custom_interest = st.text_input("➕ Custom Interest (optional)", placeholder="e.g., Cloud Computing")

            submitted = st.form_submit_button("✨ Create Account", use_container_width=True)

            if submitted:
                if not reg_name or not reg_email or not reg_password:
                    st.error("Please fill in all required fields.")
                elif len(reg_password) < 6:
                    st.error("Password must be at least 6 characters.")
                elif reg_password != reg_confirm:
                    st.error("Passwords do not match.")
                else:
                    interests = selected_interests[:]
                    if custom_interest.strip():
                        interests.append(custom_interest.strip())

                    result = register_user(reg_name.strip(), reg_email.strip(), reg_password, interests)
                    if result["success"]:
                        set_session_user(result["user"])
                        st.success("🎉 " + result["message"])
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(result["message"])

# ─── Google Sign-In Tab ───────────────────────────────────────────────────────
with tab_google:
    st.markdown("")
    col_left, col_form, col_right = st.columns([1, 2, 1])
    with col_form:
        google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")

        if not google_client_id or not google_client_secret:
            st.markdown("""
            <div style="background: linear-gradient(135deg, #1A1D29, #22263A); 
                        border: 1px solid rgba(108,99,255,0.15); border-radius: 16px; 
                        padding: 2rem; text-align: center;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">🌐</div>
                <h3 style="color: #FAFAFA;">Google Sign-In</h3>
                <p style="color: #A0A4B8;">
                    To enable Google Sign-In, add your Google OAuth credentials to the <code>.env</code> file:
                </p>
                <code style="color: #00D2FF;">
                    GOOGLE_CLIENT_ID=your_client_id<br>
                    GOOGLE_CLIENT_SECRET=your_client_secret
                </code>
                <p style="color: #A0A4B8; margin-top: 1rem; font-size: 0.85rem;">
                    Get credentials from 
                    <a href="https://console.cloud.google.com/apis/credentials" target="_blank" 
                       style="color: #6C63FF;">Google Cloud Console</a>
                </p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background: linear-gradient(135deg, #1A1D29, #22263A); 
                        border: 1px solid rgba(108,99,255,0.15); border-radius: 16px; 
                        padding: 2rem; text-align: center;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">🌐</div>
                <h3 style="color: #FAFAFA;">Sign in with Google</h3>
                <p style="color: #A0A4B8;">
                    Click below to authenticate with your Google account
                </p>
            </div>
            """, unsafe_allow_html=True)

            # Build Google OAuth URL
            from urllib.parse import urlencode
            redirect_uri = "http://localhost:8501"
            params = {
                "client_id": google_client_id,
                "redirect_uri": redirect_uri,
                "scope": "openid email profile",
                "response_type": "code",
                "access_type": "offline",
                "prompt": "consent"
            }
            auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
            st.link_button("🔗 Sign in with Google", auth_url, use_container_width=True)

            # Handle OAuth callback
            query_params = st.query_params
            auth_code = query_params.get("code")
            if auth_code:
                try:
                    import requests as req
                    token_resp = req.post("https://oauth2.googleapis.com/token", data={
                        "code": auth_code,
                        "client_id": google_client_id,
                        "client_secret": google_client_secret,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code"
                    })
                    tokens = token_resp.json()
                    if "access_token" in tokens:
                        user_resp = req.get(
                            "https://www.googleapis.com/oauth2/v2/userinfo",
                            headers={"Authorization": f"Bearer {tokens['access_token']}"}
                        )
                        guser = user_resp.json()
                        db_user = google_oauth_upsert(
                            google_id=guser.get("id"),
                            name=guser.get("name", "Google User"),
                            email=guser.get("email"),
                            avatar_url=guser.get("picture")
                        )
                        set_session_user(db_user)
                        st.query_params.clear()
                        st.success("✅ Signed in with Google!")
                        st.rerun()
                    else:
                        st.error("OAuth token exchange failed. Please try again.")
                except Exception as e:
                    st.error(f"Google Sign-In error: {e}")
