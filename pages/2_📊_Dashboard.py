"""
📊 User Dashboard Page
"""
import streamlit as st
import os

st.set_page_config(page_title="Dashboard – AI Quiz App", page_icon="📊", layout="wide")

css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from utils.auth import require_login, get_user_interests, update_user_interests, INTEREST_OPTIONS, is_admin, logout
from utils.quiz import get_categories, get_user_stats, get_category_stats, get_user_results, get_recommended_questions
from utils.gemini_ai import suggest_topics

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

user_id = st.session_state["user_id"]
user_name = st.session_state["user_name"]

# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="padding: 1rem 0;">
    <h1 style="font-size: 2rem; font-weight: 800;
        background: linear-gradient(135deg, #6C63FF, #00D2FF);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        📊 Welcome back, {user_name}!
    </h1>
</div>
""", unsafe_allow_html=True)

# ─── Quick Stats ──────────────────────────────────────────────────────────────
stats = get_user_stats(user_id)
c1, c2, c3, c4 = st.columns(4)
c1.metric("🎯 Quizzes Taken", stats["total_quizzes"])
c2.metric("✅ Correct Answers", stats["total_correct"])
c3.metric("📈 Avg. Score", f"{stats['avg_percentage']:.0f}%")
c4.metric("🏆 Best Score", f"{stats['best_percentage']:.0f}%" if stats["best_percentage"] else "N/A")

st.divider()

# ─── Main Columns ─────────────────────────────────────────────────────────────
col_left, col_right = st.columns([2, 1])

# ─── Left: Quick Start & History ──────────────────────────────────────────────
with col_left:
    st.markdown("### 🚀 Quick Start a Quiz")

    categories = [c for c in get_categories() if c.get("category_id")]
    if categories:
        cat_cols = st.columns(min(len(categories), 4))
        for i, cat in enumerate(categories):
            with cat_cols[i % 4]:
                if st.button(
                    f"{cat['icon']} {cat['category_name']}",
                    key=f"quick_{cat['category_id']}",
                    use_container_width=True
                ):
                    st.session_state["selected_category"] = cat["category_id"]
                    st.session_state["selected_category_name"] = cat["category_name"]
                    st.switch_page("pages/3_🧠_Quiz.py")
    else:
        st.info("No categories available yet. Ask an admin to generate questions!")

    # ─── AI-Suggested Topics ──────────────────────────────────────────────────
    st.markdown("")
    st.markdown("### 🤖 AI-Suggested Topics For You")
    interests = get_user_interests(user_id)
    if interests:
        try:
            with st.spinner("Generating suggestions..."):
                suggestions = suggest_topics(interests)
            for s in suggestions:
                st.markdown(f"• 💡 **{s}**")
        except Exception:
            st.caption("Could not generate suggestions. Check your Gemini API key.")
    else:
        st.info("Select your interests below to get personalized suggestions!")

    # ─── Recent Quiz History ──────────────────────────────────────────────────
    st.markdown("")
    st.markdown("### 📜 Recent Quiz History")
    results = get_user_results(user_id, limit=5)
    if results:
        for r in results:
            pct = round(r["score"] / r["total_questions"] * 100, 1) if r["total_questions"] else 0
            color = "#00C853" if pct >= 70 else "#FFB300" if pct >= 40 else "#FF5252"
            st.markdown(f"""
            <div style="background: #1A1D29; border: 1px solid rgba(108,99,255,0.1); 
                        border-radius: 12px; padding: 1rem; margin-bottom: 0.5rem;
                        display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong style="color: #FAFAFA;">{r['category_name']}</strong>
                    <span style="color: #A0A4B8; font-size: 0.85rem;"> · {r['difficulty']} · {r['date_taken'].strftime('%b %d, %Y')}</span>
                </div>
                <div style="font-size: 1.2rem; font-weight: 700; color: {color};">
                    {r['score']}/{r['total_questions']} ({pct}%)
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("No quizzes taken yet. Start one above! 🎮")

    # ─── Category Performance ─────────────────────────────────────────────────
    cat_stats = get_category_stats(user_id)
    if cat_stats:
        st.markdown("")
        st.markdown("### 📊 Category Performance")
        import plotly.express as px
        import pandas as pd

        df = pd.DataFrame(cat_stats)
        fig = px.bar(
            df, x="category_name", y="avg_score",
            color="avg_score",
            color_continuous_scale=["#FF5252", "#FFB300", "#00C853"],
            labels={"category_name": "Category", "avg_score": "Avg Score (%)"},
            text="attempts"
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#A0A4B8",
            showlegend=False,
            coloraxis_showscale=False,
            xaxis_title="",
            yaxis_title="Average Score %"
        )
        fig.update_traces(texttemplate='%{text} quiz(es)', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

# ─── Right: Profile & Interests ──────────────────────────────────────────────
with col_right:
    st.markdown("### 👤 Your Profile")
    user_data = st.session_state.get("user", {})
    st.markdown(f"""
    <div style="background: #1A1D29; border: 1px solid rgba(108,99,255,0.15); 
                border-radius: 16px; padding: 1.5rem; text-align: center;">
        <div style="font-size: 3rem; margin-bottom: 0.5rem;">👤</div>
        <h3 style="color: #FAFAFA; margin-bottom: 0.25rem;">{user_data.get('name', 'User')}</h3>
        <p style="color: #A0A4B8; font-size: 0.85rem;">{user_data.get('email', '')}</p>
        <span style="background: linear-gradient(135deg, #6C63FF, #4A42D4); 
                     padding: 0.25rem 0.75rem; border-radius: 20px; font-size: 0.8rem; color: white;">
            {user_data.get('role', 'user').upper()}
        </span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")
    st.markdown("### 🎯 Your Interests")

    current_interests = get_user_interests(user_id)

    with st.form("interests_form"):
        new_interests = st.multiselect(
            "Select your interests",
            options=INTEREST_OPTIONS,
            default=[i for i in current_interests if i in INTEREST_OPTIONS],
            help="These determine your personalized quiz recommendations"
        )
        custom = st.text_input("Add custom interest", placeholder="e.g., Cloud Computing")
        if st.form_submit_button("💾 Update Interests", use_container_width=True):
            all_interests = new_interests[:]
            if custom.strip():
                all_interests.append(custom.strip())
            update_user_interests(user_id, all_interests)
            st.success("Interests updated!")
            st.rerun()

    if current_interests:
        for interest in current_interests:
            st.markdown(f"• {interest}")
