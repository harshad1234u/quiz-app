"""
Authentication module – email/password + Google OAuth helpers.
"""
import os
import bcrypt
import streamlit as st
from utils.db import execute_query, fetch_one, fetch_all

# ─── Available interest topics ───────────────────────────────────────────────
INTEREST_OPTIONS = [
    "Cybersecurity",
    "Programming",
    "AI & Machine Learning",
    "Databases",
    "Networking",
    "General Knowledge",
    "Technology",
    "Web Development",
]


# ─── Password helpers ────────────────────────────────────────────────────────
def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


# ─── Registration ─────────────────────────────────────────────────────────────
def register_user(name: str, email: str, password: str, interests: list[str] | None = None) -> dict:
    """Register a new user. Returns {'success': bool, 'message': str, 'user': dict|None}."""
    # Check if email exists
    existing = fetch_one("SELECT user_id FROM users WHERE email = %s", (email,))
    if existing:
        return {"success": False, "message": "An account with this email already exists.", "user": None}

    hashed = _hash_password(password)
    user_id = execute_query(
        "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, 'user')",
        (name, email, hashed)
    )

    # Save interests
    if interests:
        for interest in interests:
            execute_query(
                "INSERT IGNORE INTO user_interests (user_id, interest_name) VALUES (%s, %s)",
                (user_id, interest)
            )

    user = fetch_one("SELECT * FROM users WHERE user_id = %s", (user_id,))
    return {"success": True, "message": "Registration successful!", "user": user}


# ─── Email Login ──────────────────────────────────────────────────────────────
def login_user(email: str, password: str) -> dict:
    """Authenticate with email & password. Returns {'success': bool, 'message': str, 'user': dict|None}."""
    user = fetch_one("SELECT * FROM users WHERE email = %s", (email,))
    if not user:
        return {"success": False, "message": "No account found with this email.", "user": None}
    if user.get("password") is None:
        return {"success": False, "message": "This account uses Google Sign-In. Please log in with Google.", "user": None}
    if not _verify_password(password, user["password"]):
        return {"success": False, "message": "Incorrect password.", "user": None}
    return {"success": True, "message": "Login successful!", "user": user}


# ─── Google OAuth ─────────────────────────────────────────────────────────────
def google_oauth_upsert(google_id: str, name: str, email: str, avatar_url: str = None) -> dict:
    """Create or update user via Google profile info. Returns user dict."""
    user = fetch_one("SELECT * FROM users WHERE google_id = %s", (google_id,))
    if user:
        execute_query(
            "UPDATE users SET name=%s, email=%s, avatar_url=%s WHERE google_id=%s",
            (name, email, avatar_url, google_id)
        )
    else:
        # Check if email already exists (registered via email)
        existing = fetch_one("SELECT * FROM users WHERE email = %s", (email,))
        if existing:
            execute_query(
                "UPDATE users SET google_id=%s, avatar_url=%s WHERE user_id=%s",
                (google_id, avatar_url, existing["user_id"])
            )
        else:
            execute_query(
                "INSERT INTO users (name, email, google_id, avatar_url, role) VALUES (%s,%s,%s,%s,'user')",
                (name, email, google_id, avatar_url)
            )
    return fetch_one("SELECT * FROM users WHERE email = %s", (email,))


# ─── Interests ────────────────────────────────────────────────────────────────
def get_user_interests(user_id: int) -> list[str]:
    rows = fetch_all("SELECT interest_name FROM user_interests WHERE user_id = %s", (user_id,))
    return [r["interest_name"] for r in rows]


def update_user_interests(user_id: int, interests: list[str]):
    execute_query("DELETE FROM user_interests WHERE user_id = %s", (user_id,))
    for interest in interests:
        execute_query(
            "INSERT IGNORE INTO user_interests (user_id, interest_name) VALUES (%s, %s)",
            (user_id, interest)
        )


# ─── Session helpers ──────────────────────────────────────────────────────────
def set_session_user(user: dict):
    """Store user info in Streamlit session state."""
    st.session_state["user"] = user
    st.session_state["logged_in"] = True
    st.session_state["user_id"] = user["user_id"]
    st.session_state["user_name"] = user["name"]
    st.session_state["user_role"] = user["role"]


def get_session_user() -> dict | None:
    return st.session_state.get("user")


def is_logged_in() -> bool:
    return st.session_state.get("logged_in", False)


def is_admin() -> bool:
    return st.session_state.get("user_role") == "admin"


def logout():
    for key in ["user", "logged_in", "user_id", "user_name", "user_role"]:
        st.session_state.pop(key, None)


def require_login():
    """Show a warning and stop execution if user is not logged in."""
    if not is_logged_in():
        st.warning("🔒 Please log in to access this page.")
        st.stop()


def require_admin():
    """Show a warning and stop execution if user is not admin."""
    require_login()
    if not is_admin():
        st.error("⛔ Admin access required.")
        st.stop()
