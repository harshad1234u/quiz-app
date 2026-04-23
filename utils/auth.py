"""
Authentication module – email/password + Google OAuth helpers.
Uses Supabase (PostgREST) for all database operations.
"""
import bcrypt
import streamlit as st
from postgrest.exceptions import APIError
from utils.db import get_supabase

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


def _api_error_message(exc: APIError) -> str:
    """Extract a readable message from a PostgREST exception."""
    try:
        payload = exc.json() if callable(getattr(exc, "json", None)) else {}
    except Exception:
        payload = {}

    if isinstance(payload, dict):
        return str(payload.get("message") or payload.get("details") or payload.get("hint") or "")
    return ""


# ─── Registration ─────────────────────────────────────────────────────────────
def register_user(name: str, email: str, password: str, interests: list[str] | None = None) -> dict:
    """Register a new user. Returns {'success': bool, 'message': str, 'user': dict|None}."""
    sb = get_supabase()
    email = email.strip().lower()

    try:
        # Check if email exists (case-insensitive)
        existing = sb.table("users").select("user_id").ilike("email", email).limit(1).execute()
        if existing.data:
            return {"success": False, "message": "An account with this email already exists.", "user": None}
    except APIError:
        # Fallback for environments where ilike may not be available through API permissions.
        existing = sb.table("users").select("user_id").eq("email", email).limit(1).execute()
        if existing.data:
            return {"success": False, "message": "An account with this email already exists.", "user": None}

    hashed = _hash_password(password)

    # Try a couple payload shapes to tolerate role-column drift across deployments.
    insert_payloads = [
        {"name": name, "email": email, "password": hashed, "role": "user"},
        {"name": name, "email": email, "password": hashed},
    ]

    result = None
    last_error: APIError | None = None
    for payload in insert_payloads:
        try:
            result = sb.table("users").insert(payload).execute()
            break
        except APIError as exc:
            last_error = exc

    if result is None:
        details = _api_error_message(last_error) if last_error else ""
        if "duplicate" in details.lower() or "unique" in details.lower():
            return {"success": False, "message": "An account with this email already exists.", "user": None}
        if details:
            return {"success": False, "message": f"Registration failed: {details}", "user": None}
        return {"success": False, "message": "Registration failed. Please verify your Supabase users table schema.", "user": None}

    user = result.data[0] if result.data else None
    if not user:
        try:
            refreshed = sb.table("users").select("*").ilike("email", email).limit(1).execute()
            user = refreshed.data[0] if refreshed.data else None
        except APIError:
            refreshed = sb.table("users").select("*").eq("email", email).limit(1).execute()
            user = refreshed.data[0] if refreshed.data else None

    if not user:
        return {"success": False, "message": "Registration failed.", "user": None}

    user_id = user["user_id"]

    # Save interests
    if interests:
        rows = [{"user_id": user_id, "interest_name": i} for i in interests]
        try:
            sb.table("user_interests").upsert(rows, on_conflict="user_id,interest_name").execute()
        except APIError:
            # Keep auth flow working even if interests table/policy differs.
            pass

    return {"success": True, "message": "Registration successful!", "user": user}


# ─── Email Login ──────────────────────────────────────────────────────────────
def login_user(email: str, password: str) -> dict:
    """Authenticate with email & password."""
    sb = get_supabase()
    result = sb.table("users").select("*").eq("email", email).execute()
    user = result.data[0] if result.data else None

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
    sb = get_supabase()

    # Check by google_id first
    result = sb.table("users").select("*").eq("google_id", google_id).execute()
    user = result.data[0] if result.data else None

    if user:
        sb.table("users").update({
            "name": name, "email": email, "avatar_url": avatar_url
        }).eq("google_id", google_id).execute()
    else:
        # Check if email already registered
        existing = sb.table("users").select("*").eq("email", email).execute()
        if existing.data:
            sb.table("users").update({
                "google_id": google_id, "avatar_url": avatar_url
            }).eq("user_id", existing.data[0]["user_id"]).execute()
        else:
            sb.table("users").insert({
                "name": name, "email": email, "google_id": google_id,
                "avatar_url": avatar_url, "role": "user"
            }).execute()

    # Fetch updated record
    final = sb.table("users").select("*").eq("email", email).execute()
    return final.data[0] if final.data else None


# ─── Interests ────────────────────────────────────────────────────────────────
def get_user_interests(user_id: int) -> list[str]:
    sb = get_supabase()
    result = sb.table("user_interests").select("interest_name").eq("user_id", user_id).execute()
    return [r["interest_name"] for r in result.data]


def update_user_interests(user_id: int, interests: list[str]):
    sb = get_supabase()
    sb.table("user_interests").delete().eq("user_id", user_id).execute()
    if interests:
        rows = [{"user_id": user_id, "interest_name": i} for i in interests]
        sb.table("user_interests").upsert(rows, on_conflict="user_id,interest_name").execute()


# ─── Session helpers ──────────────────────────────────────────────────────────
def set_session_user(user: dict):
    """Store user info in Streamlit session state."""
    st.session_state["user"] = user
    st.session_state["logged_in"] = True
    st.session_state["user_id"] = user["user_id"]
    st.session_state["user_name"] = user.get("name") or user.get("email", "User")
    st.session_state["user_role"] = user.get("role", "user")


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
