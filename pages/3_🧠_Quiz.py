"""
🧠 Quiz Gameplay Page
"""
import streamlit as st
import os
import time
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Quiz – AI Quiz App", page_icon="🧠", layout="wide")

css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from utils.auth import require_login, logout
from utils.quiz import (
    get_categories, get_quiz_questions, create_quiz_session,
    submit_quiz, get_recommended_questions
)

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


# ─── Helper: initialise quiz state ───────────────────────────────────────────
def init_quiz_state():
    defaults = {
        "quiz_active": False,
        "quiz_questions": [],
        "quiz_current": 0,
        "quiz_answers": {},
        "quiz_session_id": None,
        "quiz_start_time": None,
        "quiz_submitted": False,
        "quiz_category_id": None,
        "quiz_difficulty": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_quiz_state()

# ─── QUIZ SETUP (if not active) ──────────────────────────────────────────────
if not st.session_state["quiz_active"] and not st.session_state["quiz_submitted"]:
    st.markdown("""
    <div style="padding: 1rem 0;">
        <h1 style="font-size: 2rem; font-weight: 800;
            background: linear-gradient(135deg, #6C63FF, #00D2FF);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            🧠 Start a Quiz
        </h1>
        <p style="color: #A0A4B8;">Choose your category, difficulty, and number of questions</p>
    </div>
    """, unsafe_allow_html=True)

    col_setup, col_preview = st.columns([2, 1])

    with col_setup:
        categories = get_categories()
        cat_names = {c["category_name"]: c["category_id"] for c in categories}

        # Pre-select if coming from dashboard
        pre_selected = st.session_state.get("selected_category_name", None)
        cat_list = list(cat_names.keys())
        default_idx = cat_list.index(pre_selected) if pre_selected and pre_selected in cat_list else 0

        selected_cat = st.selectbox("📚 Category", cat_list, index=default_idx)
        difficulty = st.selectbox("🎚️ Difficulty", ["Easy", "Medium", "Hard"], index=1)
        num_questions = st.slider("📝 Number of Questions", min_value=5, max_value=25, value=10, step=5)
        time_per_q = st.slider("⏱️ Seconds per Question", min_value=15, max_value=120, value=30, step=15)

        st.markdown("")
        if st.button("🚀 Start Quiz", use_container_width=True, type="primary"):
            category_id = cat_names[selected_cat]
            with st.spinner("Preparing your quiz... (AI may generate new questions)"):
                result = get_quiz_questions(category_id, difficulty, num_questions)

            questions = result["questions"]
            status = result["status"]
            message = result["message"]

            if status == "empty":
                # No questions at all — show specific error
                st.error("😔 " + message)
                st.info(
                    "**What you can do:**\n"
                    "- Wait a few minutes for the Gemini API quota to reset\n"
                    "- Ask an admin to generate questions from the Admin Dashboard\n"
                    "- Try a different category that may have cached questions"
                )
            elif status == "partial":
                # Some questions available — let user proceed with warning
                st.warning("⚠️ " + message)
                if questions:
                    session_id = create_quiz_session(user_id, category_id, difficulty, len(questions))
                    st.session_state["quiz_active"] = True
                    st.session_state["quiz_questions"] = questions
                    st.session_state["quiz_current"] = 0
                    st.session_state["quiz_answers"] = {}
                    st.session_state["quiz_session_id"] = session_id
                    st.session_state["quiz_start_time"] = time.time()
                    st.session_state["quiz_submitted"] = False
                    st.session_state["quiz_category_id"] = category_id
                    st.session_state["quiz_difficulty"] = difficulty
                    st.session_state["quiz_time_per_q"] = time_per_q
                    st.session_state.pop("selected_category", None)
                    st.session_state.pop("selected_category_name", None)
                    st.rerun()
            else:
                # Full success
                session_id = create_quiz_session(user_id, category_id, difficulty, len(questions))
                st.session_state["quiz_active"] = True
                st.session_state["quiz_questions"] = questions
                st.session_state["quiz_current"] = 0
                st.session_state["quiz_answers"] = {}
                st.session_state["quiz_session_id"] = session_id
                st.session_state["quiz_start_time"] = time.time()
                st.session_state["quiz_submitted"] = False
                st.session_state["quiz_category_id"] = category_id
                st.session_state["quiz_difficulty"] = difficulty
                st.session_state["quiz_time_per_q"] = time_per_q
                # Clear dashboard pre-selection
                st.session_state.pop("selected_category", None)
                st.session_state.pop("selected_category_name", None)
                st.rerun()

    with col_preview:
        st.markdown("""
        <div style="background: #1A1D29; border: 1px solid rgba(108,99,255,0.15); 
                    border-radius: 16px; padding: 1.5rem;">
            <h3 style="color: #FAFAFA; margin-bottom: 1rem;">📋 Quiz Rules</h3>
            <ul style="color: #A0A4B8; font-size: 0.9rem; line-height: 1.8;">
                <li>Answer all questions within the time limit</li>
                <li>Each question has exactly one correct answer</li>
                <li>You can navigate between questions</li>
                <li>Unanswered questions count as incorrect</li>
                <li>AI explanations are provided after submission</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

        # Recommended quiz option
        st.markdown("")
        if st.button("🎯 Personalized Quiz (Based on Interests)", use_container_width=True):
            with st.spinner("Finding questions matching your interests..."):
                questions = get_recommended_questions(user_id, 10)
            if not questions:
                st.warning("No questions match your interests yet. Try a category quiz instead!")
            else:
                cat_id = questions[0]["category_id"]
                session_id = create_quiz_session(user_id, cat_id, "Medium", len(questions))
                st.session_state["quiz_active"] = True
                st.session_state["quiz_questions"] = questions
                st.session_state["quiz_current"] = 0
                st.session_state["quiz_answers"] = {}
                st.session_state["quiz_session_id"] = session_id
                st.session_state["quiz_start_time"] = time.time()
                st.session_state["quiz_submitted"] = False
                st.session_state["quiz_time_per_q"] = 30
                st.rerun()

# ─── QUIZ GAMEPLAY ────────────────────────────────────────────────────────────
elif st.session_state["quiz_active"]:
    questions = st.session_state["quiz_questions"]
    current = st.session_state["quiz_current"]
    total = len(questions)
    q = questions[current]

    # ─── Header: Progress & Timer ─────────────────────────────────────────────
    col_prog, col_timer = st.columns([3, 1])

    with col_prog:
        st.progress((current + 1) / total, text=f"Question {current + 1} of {total}")

    with col_timer:
        elapsed = int(time.time() - st.session_state["quiz_start_time"])
        total_time = total * st.session_state.get("quiz_time_per_q", 30)
        remaining = max(0, total_time - elapsed)
        mins, secs = divmod(remaining, 60)
        timer_color = "#FF5252" if remaining < 60 else "#FFB300" if remaining < 180 else "#00C853"
        st.markdown(f"""
        <div style="text-align: center; background: #1A1D29; border-radius: 12px; padding: 0.5rem;">
            <div style="font-size: 0.75rem; color: #A0A4B8;">⏱ Time Left</div>
            <div style="font-size: 1.5rem; font-weight: 700; color: {timer_color};">{mins:02d}:{secs:02d}</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # ─── Question Card ────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1A1D29, #22263A);
                border: 1px solid rgba(108,99,255,0.15); border-radius: 16px;
                padding: 2rem; margin-bottom: 1rem;">
        <div style="color: #A0A4B8; font-size: 0.85rem; margin-bottom: 0.5rem;">
            {q.get('category_name', 'Quiz')} · {q.get('difficulty', 'Medium')}
        </div>
        <h2 style="color: #FAFAFA; font-size: 1.3rem; line-height: 1.5;">
            Q{current + 1}. {q['question_text']}
        </h2>
    </div>
    """, unsafe_allow_html=True)

    # ─── Answer Options ───────────────────────────────────────────────────────
    options = [q["option1"], q["option2"], q["option3"], q["option4"]]
    q_key = f"q_{q['question_id']}"
    prev_answer = st.session_state["quiz_answers"].get(q["question_id"])
    default_idx = options.index(prev_answer) if prev_answer and prev_answer in options else None

    selected = st.radio(
        "Select your answer:",
        options,
        index=default_idx,
        key=f"radio_{current}_{q['question_id']}",
        label_visibility="collapsed"
    )

    # Save answer
    if selected:
        st.session_state["quiz_answers"][q["question_id"]] = selected

    # ─── Navigation ───────────────────────────────────────────────────────────
    st.markdown("")
    nav_cols = st.columns([1, 1, 1, 2])

    with nav_cols[0]:
        if current > 0:
            if st.button("◀ Previous", use_container_width=True):
                st.session_state["quiz_current"] = current - 1
                st.rerun()

    with nav_cols[1]:
        if current < total - 1:
            if st.button("Next ▶", use_container_width=True):
                st.session_state["quiz_current"] = current + 1
                st.rerun()

    with nav_cols[3]:
        answered = len(st.session_state["quiz_answers"])
        if st.button(f"✅ Submit Quiz ({answered}/{total} answered)", use_container_width=True, type="primary"):
            if answered < total:
                st.warning(f"You haven't answered {total - answered} question(s). Submit anyway?")
                if st.button("Yes, submit now", key="confirm_submit"):
                    pass  # Fall through to submit
                else:
                    st.stop()

            # Process submission
            elapsed_time = int(time.time() - st.session_state["quiz_start_time"])
            answer_list = []
            for question in questions:
                answer_list.append({
                    "question_id": question["question_id"],
                    "selected_answer": st.session_state["quiz_answers"].get(question["question_id"], ""),
                    "correct_answer": question.get("correct_answer"),
                    "question_text": question.get("question_text"),
                    "option1": question.get("option1"),
                    "option2": question.get("option2"),
                    "option3": question.get("option3"),
                    "option4": question.get("option4"),
                    "explanation": question.get("explanation", ""),
                    "difficulty": question.get("difficulty"),
                    "category_id": question.get("category_id"),
                })

            result = submit_quiz(st.session_state["quiz_session_id"], answer_list, elapsed_time)
            st.session_state["quiz_result"] = result
            st.session_state["quiz_active"] = False
            st.session_state["quiz_submitted"] = True
            st.rerun()

    # ─── Question Navigator Dots ──────────────────────────────────────────────
    st.markdown("")
    st.markdown("#### Question Navigator")
    dot_cols = st.columns(min(total, 10))
    for i in range(min(total, 10)):
        q_id = questions[i]["question_id"]
        is_answered = q_id in st.session_state["quiz_answers"]
        is_current = i == current
        with dot_cols[i]:
            label = f"{'✅' if is_answered else '⬜'} {i + 1}"
            if is_current:
                label = f"👉 {i + 1}"
            if st.button(label, key=f"nav_{i}", use_container_width=True):
                st.session_state["quiz_current"] = i
                st.rerun()

    if total > 10:
        dot_cols2 = st.columns(min(total - 10, 10))
        for i in range(10, min(total, 20)):
            q_id = questions[i]["question_id"]
            is_answered = q_id in st.session_state["quiz_answers"]
            is_current = i == current
            with dot_cols2[i - 10]:
                label = f"{'✅' if is_answered else '⬜'} {i + 1}"
                if is_current:
                    label = f"👉 {i + 1}"
                if st.button(label, key=f"nav_{i}", use_container_width=True):
                    st.session_state["quiz_current"] = i
                    st.rerun()

# ─── QUIZ RESULTS (after submit) ─────────────────────────────────────────────
elif st.session_state["quiz_submitted"]:
    result = st.session_state.get("quiz_result", {})
    score = result.get("score", 0)
    total = result.get("total", 0)
    pct = result.get("percentage", 0)

    # Result header
    if pct >= 80:
        emoji, grade, color = "🏆", "Excellent!", "#00C853"
    elif pct >= 60:
        emoji, grade, color = "👏", "Good Job!", "#FFB300"
    elif pct >= 40:
        emoji, grade, color = "💪", "Keep Trying!", "#FF9800"
    else:
        emoji, grade, color = "📚", "Study More!", "#FF5252"

    st.markdown(f"""
    <div style="text-align: center; padding: 2rem; background: linear-gradient(135deg, #1A1D29, #22263A);
                border: 1px solid rgba(108,99,255,0.15); border-radius: 16px; margin-bottom: 2rem;">
        <div style="font-size: 4rem;">{emoji}</div>
        <h1 style="color: {color}; font-size: 2.5rem; margin: 0.5rem 0;">{grade}</h1>
        <p style="font-size: 2rem; font-weight: 800; color: {color};">{score}/{total} ({pct}%)</p>
    </div>
    """, unsafe_allow_html=True)

    # Score gauge
    import plotly.graph_objects as go
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        title={"text": "Score", "font": {"color": "#A0A4B8"}},
        number={"suffix": "%", "font": {"color": "#FAFAFA", "size": 40}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#A0A4B8"},
            "bar": {"color": color},
            "bgcolor": "#1A1D29",
            "steps": [
                {"range": [0, 40], "color": "rgba(255,82,82,0.2)"},
                {"range": [40, 70], "color": "rgba(255,179,0,0.2)"},
                {"range": [70, 100], "color": "rgba(0,200,83,0.2)"},
            ],
        }
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        height=250,
        margin=dict(t=50, b=0, l=30, r=30)
    )
    st.plotly_chart(fig, use_container_width=True)

    # ─── Review answers ───────────────────────────────────────────────────────
    st.markdown("### 📝 Question Review")
    questions = st.session_state.get("quiz_questions", [])
    answers = st.session_state.get("quiz_answers", {})

    for i, q in enumerate(questions):
        user_ans = answers.get(q["question_id"], "Not answered")
        correct = q["correct_answer"]
        is_correct = user_ans == correct

        icon = "✅" if is_correct else "❌"
        border_color = "rgba(0,200,83,0.3)" if is_correct else "rgba(255,82,82,0.3)"

        with st.expander(f"{icon} Q{i + 1}: {q['question_text'][:80]}..."):
            st.markdown(f"**Your Answer:** {user_ans}")
            st.markdown(f"**Correct Answer:** {correct}")

            if not is_correct:
                st.error(f"Your answer was incorrect.")

            if q.get("explanation"):
                st.info(f"💡 **Explanation:** {q['explanation']}")
            else:
                # Generate AI explanation on demand
                if st.button(f"🤖 Get AI Explanation", key=f"explain_{q['question_id']}"):
                    from utils.gemini_ai import generate_explanation
                    with st.spinner("Generating explanation..."):
                        explanation = generate_explanation(q["question_text"], correct, user_ans)
                    st.info(f"💡 **AI Explanation:** {explanation}")

    # ─── Actions ──────────────────────────────────────────────────────────────
    st.markdown("")
    action_cols = st.columns(3)
    with action_cols[0]:
        if st.button("🔄 Take Another Quiz", use_container_width=True):
            for key in ["quiz_active", "quiz_questions", "quiz_current", "quiz_answers",
                        "quiz_session_id", "quiz_start_time", "quiz_submitted", "quiz_result"]:
                st.session_state.pop(key, None)
            st.rerun()
    with action_cols[1]:
        if st.button("📊 View Dashboard", use_container_width=True):
            for key in ["quiz_active", "quiz_questions", "quiz_current", "quiz_answers",
                        "quiz_session_id", "quiz_start_time", "quiz_submitted", "quiz_result"]:
                st.session_state.pop(key, None)
            st.switch_page("pages/2_📊_Dashboard.py")
    with action_cols[2]:
        if st.button("🏆 Leaderboard", use_container_width=True):
            st.switch_page("pages/5_🏆_Leaderboard.py")
