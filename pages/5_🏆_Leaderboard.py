"""
🏆 Leaderboard Page
"""
import streamlit as st
import os

st.set_page_config(page_title="Leaderboard – AI Quiz App", page_icon="🏆", layout="wide")

css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from utils.auth import require_login, is_logged_in, logout
from utils.quiz import get_leaderboard, get_categories

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("# 🧠 AI Quiz App")
    st.caption("Powered by Google Gemini")
    st.divider()
    if st.session_state.get("logged_in"):
        user = st.session_state.get("user", {})
        st.markdown(f"👋 **{user.get('name', 'User')}**")
        st.caption(f"Role: {user.get('role', 'user').title()}")
        if st.button("🚪 Logout", use_container_width=True):
            logout()
            st.rerun()

require_login()

# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div style="padding: 1rem 0;">
    <h1 style="font-size: 2rem; font-weight: 800;
        background: linear-gradient(135deg, #FFD700, #FF6584, #6C63FF);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        🏆 Leaderboard
    </h1>
    <p style="color: #A0A4B8;">See how you rank against other quiz takers</p>
</div>
""", unsafe_allow_html=True)

# ─── Filters ──────────────────────────────────────────────────────────────────
filter_cols = st.columns([2, 1])
with filter_cols[0]:
    categories = get_categories()
    cat_options = {"All Categories": None}
    for c in categories:
        cat_options[f"{c['icon']} {c['category_name']}"] = c["category_id"]
    selected_filter = st.selectbox("Filter by Category", list(cat_options.keys()))
    category_filter = cat_options[selected_filter]

with filter_cols[1]:
    top_n = st.selectbox("Show Top", [10, 20, 50], index=1)

# ─── Fetch Leaderboard ───────────────────────────────────────────────────────
leaders = get_leaderboard(category_id=category_filter, limit=top_n)

if leaders:
    # ─── Top 3 Podium ─────────────────────────────────────────────────────────
    if len(leaders) >= 3:
        st.markdown("")
        podium = st.columns([1, 1.2, 1])

        # Silver (2nd place)
        with podium[0]:
            l = leaders[1]
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1A1D29, #22263A);
                        border: 1px solid rgba(192,192,192,0.3); border-radius: 16px;
                        padding: 1.5rem; text-align: center; margin-top: 2rem;">
                <div style="font-size: 2.5rem;">🥈</div>
                <h3 style="color: #C0C0C0; margin: 0.5rem 0 0.25rem;">{l['name']}</h3>
                <p style="font-size: 1.5rem; font-weight: 800; color: #FAFAFA;">{l['total_score']} pts</p>
                <p style="color: #A0A4B8; font-size: 0.85rem;">{l['quizzes_taken']} quizzes · {l['avg_percentage']}% avg</p>
            </div>
            """, unsafe_allow_html=True)

        # Gold (1st place)
        with podium[1]:
            l = leaders[0]
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, rgba(42,36,32,0.9), rgba(51,43,26,0.9));
                        border: 2px solid rgba(255,215,0,0.45); border-radius: 18px;
                        padding: 2rem; text-align: center;
                        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
                        box-shadow: 0 0 40px rgba(255,215,0,0.12), 0 20px 50px rgba(0,0,0,0.3);">
                <div style="font-size: 3rem;">👑</div>
                <h2 style="color: #FFD700; margin: 0.5rem 0 0.25rem;">{l['name']}</h2>
                <p style="font-size: 2rem; font-weight: 800; color: #FAFAFA;">{l['total_score']} pts</p>
                <p style="color: #93a6cf; font-size: 0.9rem;">{l['quizzes_taken']} quizzes · {l['avg_percentage']}% avg</p>
            </div>
            """, unsafe_allow_html=True)

        # Bronze (3rd place)
        with podium[2]:
            l = leaders[2]
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1A1D29, #22263A);
                        border: 1px solid rgba(205,127,50,0.3); border-radius: 16px;
                        padding: 1.5rem; text-align: center; margin-top: 2rem;">
                <div style="font-size: 2.5rem;">🥉</div>
                <h3 style="color: #CD7F32; margin: 0.5rem 0 0.25rem;">{l['name']}</h3>
                <p style="font-size: 1.5rem; font-weight: 800; color: #FAFAFA;">{l['total_score']} pts</p>
                <p style="color: #A0A4B8; font-size: 0.85rem;">{l['quizzes_taken']} quizzes · {l['avg_percentage']}% avg</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("")
    st.divider()

    # ─── Full Leaderboard Table ───────────────────────────────────────────────
    st.markdown("### 📋 Full Rankings")

    current_user = st.session_state.get("user_name", "")

    for rank, l in enumerate(leaders, 1):
        if rank == 1:
            rank_icon = "🥇"
        elif rank == 2:
            rank_icon = "🥈"
        elif rank == 3:
            rank_icon = "🥉"
        else:
            rank_icon = f"#{rank}"

        is_current = l["name"] == current_user
        highlight = "border: 1px solid rgba(108,99,255,0.5); background: rgba(108,99,255,0.08);" if is_current else "border: 1px solid rgba(108,99,255,0.12);"

        st.markdown(f"""
        <div class='leader-row' style="{highlight} border-radius: 14px; padding: 0.85rem 1.1rem; margin-bottom: 0.5rem;
                    display: flex; align-items: center; justify-content: space-between;
                    backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
                    background: linear-gradient(160deg, rgba(16,27,47,0.7), rgba(12,20,35,0.6));">
            <div style="display: flex; align-items: center; gap: 1rem;">
                <span style="font-size: 1.3rem; min-width: 40px;">{rank_icon}</span>
                <div>
                    <strong style="color: #FAFAFA;">{l['name']}</strong>
                    {"<span style='color: #6C63FF; font-size: 0.75rem; margin-left: 8px;'>⭐ YOU</span>" if is_current else ""}
                </div>
            </div>
            <div style="display: flex; gap: 2rem; align-items: center;">
                <div style="text-align: center;">
                    <div style="color: #93a6cf; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em;">Quizzes</div>
                    <div style="color: #FAFAFA; font-weight: 600;">{l['quizzes_taken']}</div>
                </div>
                <div style="text-align: center;">
                    <div style="color: #93a6cf; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em;">Avg</div>
                    <div style="color: #33c3ff; font-weight: 600;">{l['avg_percentage']}%</div>
                </div>
                <div style="text-align: center;">
                    <div style="color: #93a6cf; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em;">Score</div>
                    <div style="color: #FFD700; font-weight: 700; font-size: 1.1rem;">{l['total_score']}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

else:
    st.info("🏆 No leaderboard data yet. Be the first to take a quiz!", icon="🎮")
