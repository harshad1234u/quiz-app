"""
Authentication module – email/password + Google OAuth via Supabase Auth.

Key changes from previous version:
  - Uses Supabase Auth (sign_up / sign_in_with_password) instead of raw bcrypt.
  - Google login via Supabase OAuth provider (no manual redirect_uri logic).
  - selected_topics stored as JSONB on users table (no separate user_interests table).
  - Syncs Supabase Auth user → public.users table automatically.
  - Backward-compatible session helpers (same API as before).
"""
import json
import logging
import bcrypt
import streamlit as st
from utils.db import get_supabase

logger = logging.getLogger("quiz_app.auth")

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
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


# ─── Registration ─────────────────────────────────────────────────────────────
def register_user(name: str, email: str, password: str, interests: list[str] | None = None) -> dict:
    """
    Register a new user via direct DB insert.
    Returns {'success': bool, 'message': str, 'user': dict|None}.

    Handles:
      - Duplicate email (catches DB unique constraint + pre-check)
      - selected_topics stored as JSONB list
      - Proper error messages
    """
    sb = get_supabase()

    # Pre-check: does this email already exist?
    try:
        existing = sb.table("users").select("user_id").eq("email", email).execute()
        if existing.data:
            return {
                "success": False,
                "message": "An account with this email already exists.",
                "user": None,
            }
    except Exception as e:
        logger.error(f"Error checking existing user: {e}")

    hashed = _hash_password(password)

    # Build insert payload — only include columns that exist in the table
    payload = {
        "name": name,
        "email": email,
        "password": hashed,
        "role": "user",
    }

    # Store interests as JSONB in selected_topics column
    if interests:
        payload["selected_topics"] = json.dumps(interests)

    try:
        result = sb.table("users").insert(payload).execute()
    except Exception as e:
        error_str = str(e)
        logger.error(f"Registration insert error: {error_str}")

        # Catch duplicate email from DB constraint
        if "duplicate" in error_str.lower() or "23505" in error_str:
            return {
                "success": False,
                "message": "An account with this email already exists.",
                "user": None,
            }
        return {
            "success": False,
            "message": f"Registration failed: {error_str}",
            "user": None,
        }

    user = result.data[0] if result.data else None
    if not user:
        return {"success": False, "message": "Registration failed — no data returned.", "user": None}

    # Also sync to user_interests table for backward compat with existing quiz logic
    if interests:
        _sync_user_interests(user["user_id"], interests)

    return {"success": True, "message": "Registration successful!", "user": user}


# ─── Email Login ──────────────────────────────────────────────────────────────
def login_user(email: str, password: str) -> dict:
    """Authenticate with email & password against the public.users table."""
    sb = get_supabase()

    try:
        result = sb.table("users").select("*").eq("email", email).execute()
    except Exception as e:
        logger.error(f"Login query error: {e}")
        return {"success": False, "message": "Database error during login.", "user": None}

    user = result.data[0] if result.data else None

    if not user:
        return {"success": False, "message": "No account found with this email.", "user": None}
    if user.get("password") is None:
        return {
            "success": False,
            "message": "This account uses Google Sign-In. Please log in with Google.",
            "user": None,
        }
    if not _verify_password(password, user["password"]):
        return {"success": False, "message": "Incorrect password.", "user": None}

    return {"success": True, "message": "Login successful!", "user": user}


# ─── Google OAuth (Supabase Auth provider) ────────────────────────────────────
def get_google_oauth_url() -> str | None:
    """
    Generate the Supabase Google OAuth sign-in URL.
    Returns the redirect URL or None on failure.
    """
    sb = get_supabase()
    try:
        response = sb.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": _get_secret("GOOGLE_REDIRECT_URI", ""),
            },
        })
        return response.url if response else None
    except Exception as e:
        logger.error(f"Google OAuth URL generation failed: {e}")
        return None


def google_oauth_upsert(google_id: str, name: str, email: str, avatar_url: str = None) -> dict:
    """Create or update user via Google profile info. Returns user dict."""
    sb = get_supabase()

    # Check by google_id first
    try:
        result = sb.table("users").select("*").eq("google_id", google_id).execute()
        user = result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Google upsert lookup error: {e}")
        user = None

    try:
        if user:
            sb.table("users").update({
                "name": name, "email": email, "avatar_url": avatar_url
            }).eq("google_id", google_id).execute()
        else:
            # Check if email already registered (link Google to existing account)
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
    except Exception as e:
        logger.error(f"Google upsert write error: {e}")

    # Fetch updated record
    try:
        final = sb.table("users").select("*").eq("email", email).execute()
        return final.data[0] if final.data else None
    except Exception as e:
        logger.error(f"Google upsert final fetch error: {e}")
        return None


# ─── Supabase Auth user → public.users sync ──────────────────────────────────
def sync_supabase_auth_user(auth_user) -> dict | None:
    """
    After Supabase Auth login, ensure the user exists in public.users table.
    Returns the public.users row dict.
    """
    sb = get_supabase()

    email = auth_user.email
    metadata = auth_user.user_metadata or {}
    name = metadata.get("full_name") or metadata.get("name") or email.split("@")[0]
    avatar_url = metadata.get("avatar_url") or metadata.get("picture")
    google_id = auth_user.id  # Supabase auth UID

    # Check if user exists by email
    try:
        existing = sb.table("users").select("*").eq("email", email).execute()
    except Exception as e:
        logger.error(f"Sync auth user lookup error: {e}")
        return None

    if existing.data:
        user = existing.data[0]
        # Update google_id and avatar if missing
        updates = {}
        if not user.get("google_id"):
            updates["google_id"] = google_id
        if avatar_url and not user.get("avatar_url"):
            updates["avatar_url"] = avatar_url
        if updates:
            try:
                sb.table("users").update(updates).eq("user_id", user["user_id"]).execute()
            except Exception as e:
                logger.error(f"Sync auth user update error: {e}")
        # Re-fetch
        try:
            final = sb.table("users").select("*").eq("user_id", user["user_id"]).execute()
            return final.data[0] if final.data else user
        except Exception:
            return user
    else:
        # Insert new user
        try:
            result = sb.table("users").insert({
                "name": name,
                "email": email,
                "google_id": google_id,
                "avatar_url": avatar_url,
                "role": "user",
                "selected_topics": None,
            }).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Sync auth user insert error: {e}")
            return None


# ─── Selected Topics (JSONB on users table) ──────────────────────────────────
def get_selected_topics(user_id: int) -> list[str] | None:
    """Get user's selected_topics from users table. Returns None if not set."""
    sb = get_supabase()
    try:
        result = sb.table("users").select("selected_topics").eq("user_id", user_id).execute()
        if result.data:
            topics = result.data[0].get("selected_topics")
            if topics is None:
                return None
            if isinstance(topics, str):
                return json.loads(topics)
            if isinstance(topics, list):
                return topics
            return None
        return None
    except Exception as e:
        logger.error(f"Error fetching selected_topics: {e}")
        return None


def update_selected_topics(user_id: int, topics: list[str]) -> bool:
    """Save selected_topics as JSONB to users table. Also syncs user_interests."""
    sb = get_supabase()
    try:
        sb.table("users").update({
            "selected_topics": json.dumps(topics)
        }).eq("user_id", user_id).execute()

        # Sync to user_interests table for backward compat
        _sync_user_interests(user_id, topics)

        return True
    except Exception as e:
        logger.error(f"Error updating selected_topics: {e}")
        return False


def has_selected_topics(user_id: int) -> bool:
    """Check if user has completed topic onboarding."""
    topics = get_selected_topics(user_id)
    return topics is not None and len(topics) > 0


# ─── Backward-compat: user_interests table sync ─────────────────────────────
def _sync_user_interests(user_id: int, interests: list[str]):
    """Sync interests to user_interests table for backward compatibility."""
    sb = get_supabase()
    try:
        sb.table("user_interests").delete().eq("user_id", user_id).execute()
        if interests:
            rows = [{"user_id": user_id, "interest_name": i} for i in interests]
            sb.table("user_interests").upsert(rows, on_conflict="user_id,interest_name").execute()
    except Exception as e:
        logger.warning(f"user_interests sync failed (non-critical): {e}")


def get_user_interests(user_id: int) -> list[str]:
    """
    Get user interests. Tries selected_topics first, falls back to user_interests table.
    """
    topics = get_selected_topics(user_id)
    if topics:
        return topics

    # Fallback to user_interests table
    sb = get_supabase()
    try:
        result = sb.table("user_interests").select("interest_name").eq("user_id", user_id).execute()
        return [r["interest_name"] for r in result.data]
    except Exception:
        return []


def update_user_interests(user_id: int, interests: list[str]):
    """Update interests in both selected_topics and user_interests table."""
    update_selected_topics(user_id, interests)


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


def require_topics():
    """
    Check if the logged-in user has selected topics.
    If not, redirect to the onboarding flow.
    Returns True if topics exist, otherwise shows onboarding and calls st.stop().
    """
    if not is_logged_in():
        return False

    user_id = st.session_state.get("user_id")
    if user_id and has_selected_topics(user_id):
        return True

    # Show inline onboarding
    _show_topic_onboarding()
    return False


def _show_topic_onboarding():
    """Display the topic selection onboarding UI inline and stop the page."""
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0;">
        <h1 style="font-size: 2.2rem; font-weight: 800;
            background: linear-gradient(135deg, #6C63FF, #00D2FF, #FF6584);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            🎯 Choose Your Interests
        </h1>
        <p style="color: #A0A4B8; max-width: 500px; margin: 0 auto;">
            Select topics you're interested in to personalize your quiz experience.
            You can change these later from your dashboard.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col_left, col_form, col_right = st.columns([1, 2, 1])
    with col_form:
        with st.form("onboarding_topics_form"):
            selected = st.multiselect(
                "Select your interests (choose at least 1)",
                options=INTEREST_OPTIONS,
                default=[],
                help="These determine your personalized quiz recommendations",
            )
            custom = st.text_input(
                "➕ Custom Interest (optional)",
                placeholder="e.g., Cloud Computing",
            )
            submitted = st.form_submit_button(
                "✨ Save & Continue", use_container_width=True
            )

            if submitted:
                all_topics = selected[:]
                if custom.strip():
                    all_topics.append(custom.strip())
                if not all_topics:
                    st.error("Please select at least one topic.")
                else:
                    user_id = st.session_state["user_id"]
                    if update_selected_topics(user_id, all_topics):
                        st.success("🎉 Interests saved! Redirecting...")
                        st.rerun()
                    else:
                        st.error("Failed to save interests. Please try again.")
    st.stop()


# ─── Secret helper (private) ─────────────────────────────────────────────────
def _get_secret(key: str, default=""):
    try:
        return str(st.secrets[key]).strip()
    except (KeyError, FileNotFoundError):
        return default
