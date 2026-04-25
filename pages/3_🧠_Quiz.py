"""
Quiz gameplay page.
"""
import os
import time

import streamlit as st

from utils.auth import logout, require_login, require_topics
from utils.quiz import (
    create_quiz_session,
    get_categories,
    get_quiz_questions,
    get_recommended_questions,
    submit_quiz,
)


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
            if st.button("Logout", use_container_width=True, key="quiz_sidebar_logout"):
                logout()
                st.rerun()


def init_quiz_state() -> None:
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
        "quiz_time_per_q": 30,
        "setup_difficulty": "Medium",
        "setup_num_questions": 10,
        "setup_time_per_q": 30,
        "setup_use_interests": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _set_quiz_active(
    user_id: int,
    questions: list[dict],
    category_id: int,
    difficulty: str,
    time_per_q: int,
) -> None:
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
    st.session_state.pop("launch_personalized_quiz", None)


st.set_page_config(page_title="Quiz - AI Quiz App", page_icon="🧠", layout="wide")
_load_styles()
_render_sidebar()

require_login()
require_topics()

user_id = st.session_state["user_id"]
init_quiz_state()

# Quiz setup screen
if not st.session_state["quiz_active"] and not st.session_state["quiz_submitted"]:
    categories = get_categories()
    category_by_id = {cat["category_id"]: cat for cat in categories}
    category_ids = [cat["category_id"] for cat in categories]

    preselected_id = st.session_state.get("selected_category")
    if preselected_id in category_ids:
        st.session_state["setup_category_id"] = preselected_id
    elif "setup_category_id" not in st.session_state or st.session_state.get("setup_category_id") not in category_ids:
        st.session_state["setup_category_id"] = category_ids[0] if category_ids else None

    if st.session_state.pop("launch_personalized_quiz", False):
        st.session_state["setup_use_interests"] = True

    selected_category_id = st.session_state.get("setup_category_id")
    selected_category = category_by_id.get(selected_category_id)
    selected_category_name = selected_category["category_name"] if selected_category else "None"

    difficulty = st.session_state.get("setup_difficulty", "Medium")
    num_questions = st.session_state.get("setup_num_questions", 10)
    time_per_q = st.session_state.get("setup_time_per_q", 30)
    use_interests = st.session_state.get("setup_use_interests", False)

    st.markdown("<div class='page-shell'>", unsafe_allow_html=True)
    st.markdown(
        """
        <p class='section-kicker'>Quiz Setup</p>
        <h1 class='section-title'>Build Your Next Quiz</h1>
        <p class='section-sub'>Choose a category, tune difficulty, and start a focused session in seconds.</p>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.9, 1], gap="large")
    setup_notice = st.empty()

    with left:
        st.markdown("### 1) Select Category")
        if not categories:
            st.info("No categories are available. Ask an admin to generate questions.")
        else:
            card_cols = st.columns(2)
            for idx, cat in enumerate(categories):
                is_active = cat["category_id"] == selected_category_id
                active_class = "active" if is_active else ""
                description = cat.get("description") or "Balanced topic set for concept clarity and retention."

                with card_cols[idx % 2]:
                    st.markdown(
                        f"""
                        <div class='category-choice {active_class}'>
                            <div class='name'>{cat.get('icon', '📘')} {cat['category_name']}</div>
                            <div class='desc'>{description}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    label = "Selected" if is_active else f"Choose {cat['category_name']}"
                    if st.button(label, key=f"choose_cat_{cat['category_id']}", use_container_width=True):
                        st.session_state["setup_category_id"] = cat["category_id"]
                        st.session_state["selected_category"] = cat["category_id"]
                        st.session_state["selected_category_name"] = cat["category_name"]
                        st.rerun()

        st.markdown("<hr class='subtle-divider' />", unsafe_allow_html=True)
        st.markdown("### 2) Difficulty")

        d1, d2, d3 = st.columns(3)
        with d1:
            easy_active = difficulty == "Easy"
            st.markdown(
                f"<div class='diff-chip {'active' if easy_active else ''}'>Easy</div>",
                unsafe_allow_html=True,
            )
            if st.button("Set Easy", key="set_diff_easy", use_container_width=True):
                st.session_state["setup_difficulty"] = "Easy"
                st.rerun()

        with d2:
            medium_active = difficulty == "Medium"
            st.markdown(
                f"<div class='diff-chip {'active' if medium_active else ''}'>Medium</div>",
                unsafe_allow_html=True,
            )
            if st.button("Set Medium", key="set_diff_medium", use_container_width=True):
                st.session_state["setup_difficulty"] = "Medium"
                st.rerun()

        with d3:
            hard_active = difficulty == "Hard"
            st.markdown(
                f"<div class='diff-chip {'active' if hard_active else ''}'>Hard</div>",
                unsafe_allow_html=True,
            )
            if st.button("Set Hard", key="set_diff_hard", use_container_width=True):
                st.session_state["setup_difficulty"] = "Hard"
                st.rerun()

        st.markdown("<hr class='subtle-divider' />", unsafe_allow_html=True)
        st.markdown("### 3) Customize")

        st.slider(
            "Number of Questions",
            min_value=5,
            max_value=25,
            value=num_questions,
            step=5,
            key="setup_num_questions",
        )
        st.slider(
            "Seconds per Question",
            min_value=15,
            max_value=120,
            value=time_per_q,
            step=15,
            key="setup_time_per_q",
        )

        st.toggle(
            "Use my interests for personalized quiz",
            key="setup_use_interests",
            help="When enabled, the app will pull questions mapped to your selected interests first.",
        )

        if st.session_state.get("setup_use_interests"):
            st.markdown(
                """
                <div class='personalized-box'>
                    <strong>Personalized Quiz</strong>
                    <span class='personalized-badge'>AI Personalized</span>
                    <div class='topic-desc' style='margin-top:0.35rem;'>
                        We will prioritize questions from your saved interests and adapt your practice session.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with right:
        st.markdown("<div class='summary-card'>", unsafe_allow_html=True)
        st.markdown("### Quiz Summary")
        st.markdown(
            f"""
            <div class='summary-item'><span class='summary-key'>Category</span><span class='summary-val'>{selected_category_name}</span></div>
            <div class='summary-item'><span class='summary-key'>Difficulty</span><span class='summary-val'>{st.session_state['setup_difficulty']}</span></div>
            <div class='summary-item'><span class='summary-key'>Questions</span><span class='summary-val'>{st.session_state['setup_num_questions']}</span></div>
            <div class='summary-item'><span class='summary-key'>Time / Question</span><span class='summary-val'>{st.session_state['setup_time_per_q']}s</span></div>
            """,
            unsafe_allow_html=True,
        )

        start_click = st.button("Start Quiz", use_container_width=True, key="start_quiz_summary")

        if start_click:
            if not selected_category_id and not st.session_state.get("setup_use_interests"):
                setup_notice.error("Choose a category before starting the quiz.")
                st.stop()

            if st.session_state.get("setup_use_interests"):
                with st.spinner("Preparing personalized questions..."):
                    rec_questions = get_recommended_questions(user_id, st.session_state["setup_num_questions"])

                if rec_questions:
                    rec_cat = rec_questions[0].get("category_id") or selected_category_id
                    _set_quiz_active(
                        user_id=user_id,
                        questions=rec_questions,
                        category_id=rec_cat,
                        difficulty=st.session_state["setup_difficulty"],
                        time_per_q=st.session_state["setup_time_per_q"],
                    )
                    st.rerun()
                else:
                    setup_notice.warning(
                        "No questions matched your interests yet. Starting a category-based quiz instead."
                    )

            if selected_category_id:
                with st.spinner("Preparing your quiz..."):
                    result = get_quiz_questions(
                        selected_category_id,
                        st.session_state["setup_difficulty"],
                        st.session_state["setup_num_questions"],
                    )

                questions = result["questions"]
                status = result["status"]
                message = result["message"]

                if status == "empty":
                    setup_notice.error(message)
                elif status == "partial":
                    setup_notice.warning(message)
                    if questions:
                        _set_quiz_active(
                            user_id=user_id,
                            questions=questions,
                            category_id=selected_category_id,
                            difficulty=st.session_state["setup_difficulty"],
                            time_per_q=st.session_state["setup_time_per_q"],
                        )
                        st.rerun()
                else:
                    _set_quiz_active(
                        user_id=user_id,
                        questions=questions,
                        category_id=selected_category_id,
                        difficulty=st.session_state["setup_difficulty"],
                        time_per_q=st.session_state["setup_time_per_q"],
                    )
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# Quiz gameplay
elif st.session_state["quiz_active"]:
    questions = st.session_state["quiz_questions"]
    current = st.session_state["quiz_current"]
    total = len(questions)
    q = questions[current]

    col_prog, col_timer = st.columns([3, 1])

    with col_prog:
        st.progress((current + 1) / total, text=f"Question {current + 1} of {total}")

    with col_timer:
        elapsed = int(time.time() - st.session_state["quiz_start_time"])
        total_time = total * st.session_state.get("quiz_time_per_q", 30)
        remaining = max(0, total_time - elapsed)
        mins, secs = divmod(remaining, 60)
        timer_color = "#ff6b6b" if remaining < 60 else "#ffb64d" if remaining < 180 else "#1dd58f"
        timer_class = "timer-urgent" if remaining < 60 else ""
        st.markdown(
            f"""
            <div class='card-panel {timer_class}' style='padding:0.6rem; text-align:center;'>
                <div style='font-size:0.75rem; color:#93a6cf; text-transform:uppercase; letter-spacing:0.06em;'>Time Left</div>
                <div style='font-size:1.4rem; font-weight:800; color:{timer_color};'>{mins:02d}:{secs:02d}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<hr class='subtle-divider' />", unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class='card-panel' style='padding:1.4rem;'>
            <div style='color:#93a6cf; font-size:0.82rem; margin-bottom:0.4rem;'>
                {q.get('category_name', 'Quiz')} · {q.get('difficulty', 'Medium')}
            </div>
            <h2 style='margin:0; font-size:1.35rem;'>Q{current + 1}. {q['question_text']}</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    options = [q["option1"], q["option2"], q["option3"], q["option4"]]
    prev_answer = st.session_state["quiz_answers"].get(q["question_id"])
    default_idx = options.index(prev_answer) if prev_answer and prev_answer in options else None

    selected = st.radio(
        "Select your answer",
        options,
        index=default_idx,
        key=f"radio_{current}_{q['question_id']}",
        label_visibility="collapsed",
    )

    if selected:
        st.session_state["quiz_answers"][q["question_id"]] = selected

    st.markdown("")
    nav_cols = st.columns([1, 1, 1, 2])

    with nav_cols[0]:
        if current > 0 and st.button("Previous", use_container_width=True):
            st.session_state["quiz_current"] = current - 1
            st.rerun()

    with nav_cols[1]:
        if current < total - 1 and st.button("Next", use_container_width=True):
            st.session_state["quiz_current"] = current + 1
            st.rerun()

    with nav_cols[3]:
        answered = len(st.session_state["quiz_answers"])
        if st.button(
            f"Submit Quiz ({answered}/{total} answered)",
            use_container_width=True,
            type="primary",
        ):
            if answered < total:
                st.warning(f"You have not answered {total - answered} question(s). Submit anyway?")
                if not st.button("Yes, submit now", key="confirm_submit"):
                    st.stop()

            elapsed_time = int(time.time() - st.session_state["quiz_start_time"])
            answer_list = []
            for question in questions:
                answer_list.append(
                    {
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
                    }
                )

            result = submit_quiz(st.session_state["quiz_session_id"], answer_list, elapsed_time)
            st.session_state["quiz_result"] = result
            st.session_state["quiz_active"] = False
            st.session_state["quiz_submitted"] = True
            st.rerun()

    st.markdown("")
    st.markdown("#### Question Navigator")
    dot_cols = st.columns(min(total, 10))
    for i in range(min(total, 10)):
        q_id = questions[i]["question_id"]
        is_answered = q_id in st.session_state["quiz_answers"]
        is_current = i == current
        with dot_cols[i]:
            label = f"{'Done' if is_answered else 'Open'} {i + 1}"
            if is_current:
                label = f"Now {i + 1}"
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
                label = f"{'Done' if is_answered else 'Open'} {i + 1}"
                if is_current:
                    label = f"Now {i + 1}"
                if st.button(label, key=f"nav_{i}", use_container_width=True):
                    st.session_state["quiz_current"] = i
                    st.rerun()

# Quiz results
elif st.session_state["quiz_submitted"]:
    result = st.session_state.get("quiz_result", {})
    score = result.get("score", 0)
    total = result.get("total", 0)
    pct = result.get("percentage", 0)

    if pct >= 80:
        grade, color = "Excellent", "#1dd58f"
    elif pct >= 60:
        grade, color = "Good Progress", "#ffb64d"
    elif pct >= 40:
        grade, color = "Keep Practicing", "#ff9c48"
    else:
        grade, color = "Needs Improvement", "#ff6b6b"

    st.markdown(
        f"""
        <div class='card-panel' style='text-align:center; padding:1.6rem; margin-bottom:1.3rem;'>
            <h1 style='margin:0; color:{color};'>{grade}</h1>
            <p style='font-size:2rem; font-weight:800; color:{color}; margin:0.5rem 0 0;'>
                {score}/{total} ({pct}%)
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    import plotly.graph_objects as go

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=pct,
            title={"text": "Score", "font": {"color": "#c2d0ee"}},
            number={"suffix": "%", "font": {"color": "#eaf1ff", "size": 40}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#93a6cf"},
                "bar": {"color": color},
                "bgcolor": "#16233d",
                "steps": [
                    {"range": [0, 40], "color": "rgba(255,107,107,0.23)"},
                    {"range": [40, 70], "color": "rgba(255,182,77,0.23)"},
                    {"range": [70, 100], "color": "rgba(29,213,143,0.24)"},
                ],
            },
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        height=250,
        margin=dict(t=50, b=0, l=30, r=30),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Question Review")
    questions = st.session_state.get("quiz_questions", [])
    answers = st.session_state.get("quiz_answers", {})

    for i, q in enumerate(questions):
        user_ans = answers.get(q["question_id"], "Not answered")
        correct = q["correct_answer"]
        is_correct = user_ans == correct
        icon = "Correct" if is_correct else "Incorrect"

        with st.expander(f"{icon} · Q{i + 1}: {q['question_text'][:80]}..."):
            st.markdown(f"**Your Answer:** {user_ans}")
            st.markdown(f"**Correct Answer:** {correct}")
            if not is_correct:
                st.error("Your answer was incorrect.")

            if q.get("explanation"):
                st.info(f"Explanation: {q['explanation']}")
            else:
                if st.button("Get AI Explanation", key=f"explain_{q['question_id']}"):
                    from utils.gemini_ai import generate_explanation

                    with st.spinner("Generating explanation..."):
                        explanation = generate_explanation(q["question_text"], correct, user_ans)
                    st.info(f"AI Explanation: {explanation}")

    st.markdown("")
    action_cols = st.columns(3)
    with action_cols[0]:
        if st.button("Take Another Quiz", use_container_width=True):
            for key in [
                "quiz_active",
                "quiz_questions",
                "quiz_current",
                "quiz_answers",
                "quiz_session_id",
                "quiz_start_time",
                "quiz_submitted",
                "quiz_result",
            ]:
                st.session_state.pop(key, None)
            st.rerun()
    with action_cols[1]:
        if st.button("View Dashboard", use_container_width=True):
            for key in [
                "quiz_active",
                "quiz_questions",
                "quiz_current",
                "quiz_answers",
                "quiz_session_id",
                "quiz_start_time",
                "quiz_submitted",
                "quiz_result",
            ]:
                st.session_state.pop(key, None)
            st.switch_page("pages/2_📊_Dashboard.py")
    with action_cols[2]:
        if st.button("Leaderboard", use_container_width=True):
            st.switch_page("pages/5_🏆_Leaderboard.py")
