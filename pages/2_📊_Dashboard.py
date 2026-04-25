"""
User dashboard page.
"""
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.auth import (
    INTEREST_OPTIONS,
    get_user_interests,
    logout,
    require_login,
    require_topics,
    update_user_interests,
    force_refresh_interests,
)
from utils.gemini_ai import suggest_topics
from utils.quiz import get_categories, get_category_stats, get_user_results, get_user_stats


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
        if st.session_state.get("logged_in"):
            user = st.session_state.get("user", {})
            st.markdown(f"**{user.get('name', 'User')}**")
            st.caption(f"Role: {user.get('role', 'user').title()}")
            if st.button("Logout", use_container_width=True, key="dash_sidebar_logout"):
                logout()
                st.rerun()


def _stat_card(title: str, value: str, hint: str, icon: str) -> str:
    return f"""
    <div class='card-panel'>
        <div class='stat-top'>
            <span>{title}</span>
            <span>{icon}</span>
        </div>
        <div class='stat-value'>{value}</div>
        <div class='stat-hint'>{hint}</div>
    </div>
    """


def _topic_card(name: str, description: str) -> str:
    return f"""
    <div class='topic-card'>
        <div class='topic-name'>{name}</div>
        <div class='topic-desc'>{description}</div>
    </div>
    """


def _build_performance_chart(category_stats: list[dict]):
    if not category_stats:
        return None

    df = pd.DataFrame(category_stats).sort_values(by="avg_score", ascending=True)
    colors = [
        "#ff7a7a" if val < 50 else "#ffbf66" if val < 70 else "#42d39f"
        for val in df["avg_score"]
    ]

    fig = go.Figure(
        go.Bar(
            x=df["avg_score"],
            y=df["category_name"],
            orientation="h",
            text=[f"{v:.0f}%" for v in df["avg_score"]],
            textposition="outside",
            marker=dict(color=colors, line=dict(color="rgba(190,210,255,0.35)", width=1)),
            hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
        )
    )

    fig.update_layout(
        height=320,
        margin=dict(l=20, r=10, t=15, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c8d7f6", size=13),
        xaxis=dict(
            title="Average Score (%)",
            range=[0, 100],
            showgrid=True,
            gridcolor="rgba(140,170,230,0.16)",
            zeroline=False,
        ),
        yaxis=dict(title="", showgrid=False),
    )
    return fig


st.set_page_config(page_title="Dashboard - AI Quiz App", page_icon="📊", layout="wide")
_load_styles()
_render_sidebar()

require_login()
require_topics()

user_id = st.session_state["user_id"]
user_name = st.session_state["user_name"]
user_data = st.session_state.get("user", {})

stats = get_user_stats(user_id)
categories = get_categories()
category_stats = get_category_stats(user_id)
current_interests = get_user_interests(user_id)
recent_results = get_user_results(user_id, limit=6)

try:
    ai_suggestions = suggest_topics(current_interests) if current_interests else []
except Exception:
    ai_suggestions = []

category_map = {c["category_name"]: c["category_id"] for c in categories}

st.markdown("<div class='page-shell'>", unsafe_allow_html=True)
st.markdown(
    f"""
    <p class='section-kicker'>Overview</p>
    <h1 class='section-title'>Welcome back, {user_name}</h1>
    <p class='section-sub'>Your progress, recommended topics, and next best actions in one place.</p>
    """,
    unsafe_allow_html=True,
)

st.markdown("<div class='stats-grid'>", unsafe_allow_html=True)
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(_stat_card("Quizzes Taken", str(stats["total_quizzes"]), "Total completed attempts", "🧠"), unsafe_allow_html=True)
with col2:
    st.markdown(_stat_card("Correct Answers", str(stats["total_correct"]), "Across all sessions", "✅"), unsafe_allow_html=True)
with col3:
    st.markdown(_stat_card("Average Score", f"{stats['avg_percentage']:.0f}%", "Overall consistency", "📈"), unsafe_allow_html=True)
with col4:
    best = f"{stats['best_percentage']:.0f}%" if stats["best_percentage"] else "N/A"
    st.markdown(_stat_card("Best Score", best, "Your top attempt", "🏆"), unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<hr class='subtle-divider' />", unsafe_allow_html=True)

left, right = st.columns([1.85, 1], gap="large")

with left:
    st.markdown("### Quick Actions")
    qa1, qa2 = st.columns(2)

    with qa1:
        st.markdown("<div class='quick-action-wrap'>", unsafe_allow_html=True)
        if st.button("Start Quiz", use_container_width=True, key="dash_start_quiz"):
            st.switch_page("pages/3_🧠_Quiz.py")
        st.markdown("</div>", unsafe_allow_html=True)

    with qa2:
        st.markdown("<div class='quick-action-wrap'>", unsafe_allow_html=True)
        if st.button("Personalized Quiz", use_container_width=True, key="dash_personal_quiz"):
            st.session_state["launch_personalized_quiz"] = True
            st.switch_page("pages/3_🧠_Quiz.py")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr class='subtle-divider' />", unsafe_allow_html=True)
    st.markdown("### Recommended Topics")
    if categories:
        topic_cols = st.columns(2)
        for idx, cat in enumerate(categories[:8]):
            desc = cat.get("description") or "Practice this category to improve your retention and accuracy."
            with topic_cols[idx % 2]:
                st.markdown(_topic_card(cat["category_name"], desc), unsafe_allow_html=True)
                if st.button(
                    f"Practice {cat['category_name']}",
                    key=f"practice_cat_{cat['category_id']}",
                    use_container_width=True,
                ):
                    st.session_state["selected_category"] = cat["category_id"]
                    st.session_state["selected_category_name"] = cat["category_name"]
                    st.switch_page("pages/3_🧠_Quiz.py")
    else:
        st.info("No categories are available yet.")

    if ai_suggestions:
        st.markdown("#### AI Suggestions")
        st.markdown("<div class='tag-list'>", unsafe_allow_html=True)
        st.markdown(
            " ".join([f"<span class='tag-pill'>{topic}</span>" for topic in ai_suggestions[:8]]),
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr class='subtle-divider' />", unsafe_allow_html=True)
    st.markdown("### Category Performance")
    performance_fig = _build_performance_chart(category_stats)
    if performance_fig:
        st.plotly_chart(performance_fig, use_container_width=True)
    else:
        st.caption("Complete a quiz to populate your category performance chart.")

    with st.expander("Recent Quiz Activity"):
        if not recent_results:
            st.caption("No quiz activity yet.")
        for row in recent_results:
            pct = round((row["score"] / row["total_questions"] * 100), 1) if row["total_questions"] else 0
            st.markdown(
                f"""
                <div class='topic-card'>
                    <div class='topic-name'>{row['category_name']} · {row['difficulty']}</div>
                    <div class='topic-desc'>
                        Score: {row['score']}/{row['total_questions']} ({pct}%) · {row['date_taken'].strftime('%b %d, %Y')}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

with right:
    first_letter = (user_data.get("name", "U")[:1] or "U").upper()
    st.markdown("<div class='card-panel'>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class='profile-stack'>
            <div class='profile-avatar'>{first_letter}</div>
            <div>
                <p class='profile-name'>{user_data.get('name', 'User')}</p>
                <p class='profile-mail'>{user_data.get('email', '')}</p>
                <span class='role-chip'>{user_data.get('role', 'user').upper()}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("#### Interests")
    if current_interests:
        st.markdown(
            " ".join([f"<span class='tag-pill'>{tag}</span>" for tag in current_interests]),
            unsafe_allow_html=True,
        )
    else:
        st.caption("No interests selected yet.")

    with st.form("interests_form"):
        selected = st.multiselect(
            "Update interests",
            options=INTEREST_OPTIONS,
            default=[tag for tag in current_interests if tag in INTEREST_OPTIONS],
            placeholder="Select interests",
        )
        custom = st.text_input("Custom interest", placeholder="e.g., Cloud Computing")
        if st.form_submit_button("Update Interests", use_container_width=True):
            merged = selected[:]
            if custom.strip():
                merged.append(custom.strip())
            update_user_interests(user_id, merged)
            force_refresh_interests()  # Clear stale state so Quiz page reads fresh DB
            st.success("Interests updated.")
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)
    st.markdown("<div class='card-panel'>", unsafe_allow_html=True)
    st.markdown("### Weak Areas")

    weak_areas = [row for row in category_stats if row["avg_score"] < 65]
    weak_areas = sorted(weak_areas, key=lambda item: item["avg_score"])[:3]

    if not weak_areas:
        st.success("No weak areas detected. Keep the momentum going.")
    else:
        for idx, weak in enumerate(weak_areas):
            st.markdown(
                f"""
                <div class='weak-alert'>
                    <div class='weak-title'>{weak['category_name']}</div>
                    <div class='weak-sub'>Accuracy: {weak['avg_score']:.0f}%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                f"Practice {weak['category_name']}",
                key=f"weak_practice_{idx}",
                use_container_width=True,
            ):
                category_id = category_map.get(weak["category_name"])
                if category_id:
                    st.session_state["selected_category"] = category_id
                    st.session_state["selected_category_name"] = weak["category_name"]
                st.switch_page("pages/3_🧠_Quiz.py")

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
