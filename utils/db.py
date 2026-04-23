"""
Database utility module – Supabase client singleton.

Reads SUPABASE_URL and SUPABASE_KEY from Streamlit secrets.
All modules import `supabase` from here to ensure a single client instance.
"""
import streamlit as st
from supabase import create_client, Client

_client: Client | None = None


def _get_secret(key: str, default=None):
    """Read a config value from Streamlit secrets, with a fallback default."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return default


def get_supabase() -> Client:
    """Return the Supabase client singleton (lazy-initialised)."""
    global _client
    if _client is None:
        url = _get_secret("SUPABASE_URL", "")
        key = _get_secret("SUPABASE_KEY", "")
        if not url or not key:
            raise EnvironmentError(
                "SUPABASE_URL and SUPABASE_KEY must be set in "
                ".streamlit/secrets.toml or Streamlit Cloud secrets."
            )
        _client = create_client(url, key)
    return _client
