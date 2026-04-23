"""
📈 Results & Analytics Page
"""
import streamlit as st
import os
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(page_title="Results – AI Quiz App", page_icon="📈", layout="wide")

css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from utils.auth import require_login, logout
from utils.quiz import get_user_results, get_user_stats, get_category_stats, get_session_details

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

# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div style="padding: 1rem 0;">
    <h1 style="font-size: 2rem; font-weight: 800;
        background: linear-gradient(135deg, #6C63FF, #00D2FF);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        📈 Results & Analytics
    </h1>
    <p style="color: #A0A4B8;">Track your learning progress and performance</p>
</div>
""", unsafe_allow_html=True)

# ─── Overall Stats ───────────────────────────────────────────────────────────
stats = get_user_stats(user_id)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("🎯 Total Quizzes", stats["total_quizzes"])
c2.metric("✅ Correct Answers", stats["total_correct"])
c3.metric("📝 Total Attempted", stats["total_attempted"])
c4.metric("📈 Avg. Score", f"{stats['avg_percentage']:.1f}%")
c5.metric("🏆 Best Score", f"{stats['best_percentage']:.1f}%" if stats["best_percentage"] else "N/A")

st.divider()

# ─── Charts Row ───────────────────────────────────────────────────────────────
results = get_user_results(user_id, limit=50)

if results:
    chart_col1, chart_col2 = st.columns(2)

    # ─── Score Over Time ──────────────────────────────────────────────────────
    with chart_col1:
        st.markdown("### 📉 Score Trend Over Time")
        df = pd.DataFrame(results)
        df["percentage"] = (df["score"] / df["total_questions"] * 100).round(1)
        df["date_taken"] = pd.to_datetime(df["date_taken"])
        df = df.sort_values("date_taken")

        fig = px.line(
            df, x="date_taken", y="percentage",
            color="category_name",
            markers=True,
            labels={"date_taken": "Date", "percentage": "Score (%)", "category_name": "Category"}
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#A0A4B8",
            yaxis_range=[0, 105],
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=350
        )
        # Add passing line
        fig.add_hline(y=70, line_dash="dash", line_color="rgba(0,200,83,0.5)",
                      annotation_text="Passing (70%)")
        st.plotly_chart(fig, use_container_width=True)

    # ─── Category Performance Radar ───────────────────────────────────────────
    with chart_col2:
        st.markdown("### 🛡️ Category Strengths")
        cat_stats = get_category_stats(user_id)
        if cat_stats:
            cat_df = pd.DataFrame(cat_stats)
            fig = go.Figure(data=go.Scatterpolar(
                r=[c["avg_score"] for c in cat_stats],
                theta=[c["category_name"] for c in cat_stats],
                fill='toself',
                fillcolor='rgba(108,99,255,0.2)',
                line=dict(color='#6C63FF', width=2),
                marker=dict(size=8, color='#00D2FF')
            ))
            fig.update_layout(
                polar=dict(
                    bgcolor="rgba(0,0,0,0)",
                    radialaxis=dict(visible=True, range=[0, 100], gridcolor="rgba(160,164,184,0.2)"),
                    angularaxis=dict(gridcolor="rgba(160,164,184,0.2)")
                ),
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="#A0A4B8",
                height=350
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Take quizzes in different categories to see your radar chart!")

    # ─── Difficulty Distribution ──────────────────────────────────────────────
    st.markdown("### 📊 Performance by Difficulty")
    df_diff = pd.DataFrame(results)
    df_diff["percentage"] = (df_diff["score"] / df_diff["total_questions"] * 100).round(1)

    fig_diff = px.box(
        df_diff, x="difficulty", y="percentage",
        color="difficulty",
        color_discrete_map={"Easy": "#00C853", "Medium": "#FFB300", "Hard": "#FF5252"},
        labels={"difficulty": "Difficulty", "percentage": "Score (%)"}
    )
    fig_diff.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#A0A4B8",
        showlegend=False,
        height=300
    )
    st.plotly_chart(fig_diff, use_container_width=True)

    # ─── Previous Attempts Table ──────────────────────────────────────────────
    st.markdown("### 📜 All Previous Attempts")

    for r in results:
        pct = round(r["score"] / r["total_questions"] * 100, 1) if r["total_questions"] else 0
        color = "#00C853" if pct >= 70 else "#FFB300" if pct >= 40 else "#FF5252"

        with st.expander(
            f"{'✅' if pct >= 70 else '⚠️' if pct >= 40 else '❌'} "
            f"{r['category_name']} · {r['difficulty']} · "
            f"{r['score']}/{r['total_questions']} ({pct}%) · "
            f"{r['date_taken'].strftime('%b %d, %Y %I:%M %p')}"
        ):
            details = get_session_details(r["session_id"])
            if details:
                for j, d in enumerate(details):
                    icon = "✅" if d["is_correct"] else "❌"
                    st.markdown(f"""
                    **{icon} Q{j + 1}:** {d['question_text']}  
                    - Your answer: `{d['selected_answer'] or 'Not answered'}`  
                    - Correct: `{d['correct_answer']}`
                    """)
                    if d.get("explanation"):
                        st.caption(f"💡 {d['explanation']}")
                    st.markdown("---")
            else:
                st.caption("No detailed records for this session.")

else:
    st.markdown("")
    st.info("📭 You haven't taken any quizzes yet. Head to the **Quiz** page to get started!", icon="🧠")
