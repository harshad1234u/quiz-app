"""
⚙️ Admin Dashboard Page
"""
import streamlit as st
import os
import pandas as pd

st.set_page_config(page_title="Admin – AI Quiz App", page_icon="⚙️", layout="wide")

css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from utils.auth import require_admin, logout
from utils.quiz import (
    get_categories, add_category, update_category, delete_category,
    get_questions, add_question, update_question, delete_question,
    generate_and_store_questions, get_all_users, get_platform_stats,
    get_leaderboard, get_question_count, bulk_generate_questions
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

require_admin()

# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div style="padding: 1rem 0;">
    <h1 style="font-size: 2rem; font-weight: 800;
        background: linear-gradient(135deg, #FF6584, #6C63FF);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        ⚙️ Admin Dashboard
    </h1>
    <p style="color: #A0A4B8;">Manage questions, categories, and users</p>
</div>
""", unsafe_allow_html=True)

# ─── Platform Overview ────────────────────────────────────────────────────────
platform = get_platform_stats()
m1, m2, m3, m4 = st.columns(4)
m1.metric("👥 Total Users", platform["total_users"])
m2.metric("❓ Total Questions", platform["total_questions"])
m3.metric("📝 Quizzes Completed", platform["total_quizzes"])
m4.metric("📈 Platform Avg.", f"{platform['avg_score']}%")

st.divider()

# ─── Admin Tabs ───────────────────────────────────────────────────────────────
tab_gen, tab_bulk, tab_questions, tab_categories, tab_users, tab_leader = st.tabs([
    "🤖 AI Generate", "📦 Bulk Pre-Generate", "❓ Questions", "📚 Categories", "👥 Users", "🏆 Leaderboard"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: AI QUESTION GENERATION
# ══════════════════════════════════════════════════════════════════════════════
with tab_gen:
    st.markdown("### 🤖 Generate Questions with Gemini AI")
    st.caption("Enter topic details and let AI create quiz questions automatically")

    categories = [c for c in get_categories() if c.get("category_id")]
    cat_map = {c["category_name"]: c["category_id"] for c in categories}

    if not cat_map:
        st.warning("No categories available. Add at least one category first.")
        gen_submit = False
        gen_topic = ""
    else:
        with st.form("gen_form"):
            gen_cols = st.columns(2)
            with gen_cols[0]:
                gen_category = st.selectbox("📚 Category", list(cat_map.keys()))
                gen_topic = st.text_input("🏷️ Topic / Sub-topic",
                                          placeholder="e.g., SQL Injection Prevention")

            with gen_cols[1]:
                gen_difficulty = st.selectbox("🎚️ Difficulty", ["Easy", "Medium", "Hard"], index=1)
                gen_count = st.slider("📝 Number of Questions", 3, 20, 5)

            gen_submit = st.form_submit_button("⚡ Generate Questions", use_container_width=True)

    if gen_submit:
        if not gen_topic:
            st.error("Please enter a topic.")
        else:
            with st.spinner(f"🤖 Gemini is generating {gen_count} {gen_difficulty} questions about '{gen_topic}'..."):
                try:
                    questions = generate_and_store_questions(
                        gen_topic, cat_map[gen_category], gen_difficulty, gen_count
                    )
                    st.success(f"✅ Successfully generated and stored {len(questions)} questions!")

                    for i, q in enumerate(questions, 1):
                        with st.expander(f"Q{i}: {q['question_text'][:60]}..."):
                            st.markdown(f"**Options:**")
                            options = [q['option1'], q['option2'], q['option3'], q['option4']]
                            for j, opt in enumerate(options, 1):
                                is_correct = opt == q['correct_answer']
                                st.markdown(f"{'✅' if is_correct else '⬜'} {j}. {opt}")
                            st.info(f"💡 {q.get('explanation', 'No explanation')}")
                except Exception as e:
                    st.error(f"❌ Generation failed: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: BULK PRE-GENERATION
# ══════════════════════════════════════════════════════════════════════════════
with tab_bulk:
    st.markdown("### 📦 Bulk Pre-Generate Questions")
    st.caption("Generate large batches to ensure quizzes always have cached questions")

    # ─── Question Inventory Matrix ────────────────────────────────────────────
    st.markdown("#### 📊 Question Inventory")
    categories = [c for c in get_categories() if c.get("category_id")]
    inventory_data = []
    for cat in categories:
        row = {"Category": f"{cat['icon']} {cat['category_name']}"}
        for diff in ["Easy", "Medium", "Hard"]:
            cnt = get_question_count(cat["category_id"], diff)
            row[diff] = cnt
        row["Total"] = sum(row[d] for d in ["Easy", "Medium", "Hard"])
        inventory_data.append(row)

    if inventory_data:
        inv_df = pd.DataFrame(inventory_data)
        st.dataframe(inv_df, use_container_width=True, hide_index=True)

        # Highlight gaps
        gaps = []
        for row in inventory_data:
            for diff in ["Easy", "Medium", "Hard"]:
                if row[diff] < 10:
                    gaps.append(f"{row['Category']} — {diff} ({row[diff]} questions)")
        if gaps:
            st.warning(f"⚠️ **{len(gaps)} combos have < 10 questions:**")
            for g in gaps[:8]:
                st.markdown(f"  - {g}")

    st.markdown("---")

    # ─── Bulk Generation Controls ─────────────────────────────────────────────
    st.markdown("#### ⚡ Generate Batch")
    if not categories:
        st.warning("No categories available for bulk generation.")
        bulk_submit = False
    else:
        with st.form("bulk_gen_form"):
            bg_cols = st.columns(3)
            with bg_cols[0]:
                cat_map_bulk = {c["category_name"]: c["category_id"] for c in categories}
                bulk_cat = st.selectbox("📚 Category", list(cat_map_bulk.keys()), key="bulk_cat")
            with bg_cols[1]:
                bulk_diff = st.selectbox("🎚️ Difficulty", ["Easy", "Medium", "Hard"], key="bulk_diff")
            with bg_cols[2]:
                bulk_count = st.slider("📝 Total Questions", 10, 50, 25, step=5, key="bulk_count")

            bulk_submit = st.form_submit_button("🚀 Generate Batch", use_container_width=True)

    if bulk_submit:
        cat_id = cat_map_bulk[bulk_cat]
        with st.spinner(f"Generating {bulk_count} {bulk_diff} questions for {bulk_cat}..."):
            result = bulk_generate_questions(cat_id, bulk_diff, bulk_count, batch_size=10)

        if result["generated"] > 0:
            st.success(
                f"✅ Generated **{result['generated']}** questions in {result['batches']} batches. "
                f"Total in DB: **{result['total_in_db']}**"
            )
        if result["failed"] > 0:
            st.warning(f"⚠️ {result['failed']} questions failed (API quota may be limited)")
        if result["generated"] == 0:
            st.error("❌ No questions generated. Gemini API quota may be exhausted.")

        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: MANAGE QUESTIONS
# ══════════════════════════════════════════════════════════════════════════════
with tab_questions:
    st.markdown("### ❓ Manage Questions")

    # ─── Filters ──────────────────────────────────────────────────────────────
    q_filter_cols = st.columns(3)
    with q_filter_cols[0]:
        categories = [c for c in get_categories() if c.get("category_id")]
        cat_filter_map = {"All": None}
        for c in categories:
            cat_filter_map[c["category_name"]] = c["category_id"]
        q_cat = st.selectbox("Category", list(cat_filter_map.keys()), key="q_filter_cat")
    with q_filter_cols[1]:
        q_diff = st.selectbox("Difficulty", ["All", "Easy", "Medium", "Hard"], key="q_filter_diff")
    with q_filter_cols[2]:
        q_count = get_question_count(
            cat_filter_map.get(q_cat),
            q_diff if q_diff != "All" else None
        )
        st.metric("Matching Questions", q_count)

    questions_list = get_questions(
        cat_filter_map.get(q_cat),
        q_diff if q_diff != "All" else None,
        limit=50
    )

    if questions_list:
        for q in questions_list:
            with st.expander(f"[{q['difficulty']}] {q['question_text'][:70]}... ({q.get('category_name', 'N/A')})"):
                cols = st.columns([3, 1])
                with cols[0]:
                    st.markdown(f"**Question:** {q['question_text']}")
                    st.markdown(f"1. {q['option1']}")
                    st.markdown(f"2. {q['option2']}")
                    st.markdown(f"3. {q['option3']}")
                    st.markdown(f"4. {q['option4']}")
                    st.markdown(f"**✅ Answer:** {q['correct_answer']}")
                    if q.get("explanation"):
                        st.caption(f"💡 {q['explanation']}")

                with cols[1]:
                    if st.button("🗑️ Delete", key=f"del_q_{q['question_id']}", use_container_width=True):
                        delete_question(q["question_id"])
                        st.success("Deleted!")
                        st.rerun()
    else:
        st.info("No questions found matching the filters.")

    # ─── Add Question Manually ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### ➕ Add Question Manually")
    if not categories:
        st.info("Create at least one category before adding questions.")
    else:
        with st.form("add_q_form"):
            aq_cols = st.columns(2)
            with aq_cols[0]:
                aq_cat = st.selectbox("Category", [c["category_name"] for c in categories], key="aq_cat")
                aq_text = st.text_area("Question Text", placeholder="Enter the question")
                aq_diff = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"], key="aq_diff")
            with aq_cols[1]:
                aq_o1 = st.text_input("Option 1")
                aq_o2 = st.text_input("Option 2")
                aq_o3 = st.text_input("Option 3")
                aq_o4 = st.text_input("Option 4")
            aq_ans = st.selectbox("Correct Answer", ["Option 1", "Option 2", "Option 3", "Option 4"])
            aq_exp = st.text_area("Explanation", placeholder="Why is this the correct answer?")

            if st.form_submit_button("➕ Add Question", use_container_width=True):
                options_vals = [aq_o1, aq_o2, aq_o3, aq_o4]
                ans_idx = ["Option 1", "Option 2", "Option 3", "Option 4"].index(aq_ans)
                cat_map = {c["category_name"]: c["category_id"] for c in categories}
                cat_id = cat_map.get(aq_cat)

                if not cat_id:
                    st.error("Please select a valid category.")
                elif not aq_text or not all(options_vals):
                    st.error("Please fill in all fields.")
                else:
                    add_question(cat_id, aq_text, aq_o1, aq_o2, aq_o3, aq_o4,
                                 options_vals[ans_idx], aq_exp, aq_diff)
                    st.success("✅ Question added!")
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: MANAGE CATEGORIES
# ══════════════════════════════════════════════════════════════════════════════
with tab_categories:
    st.markdown("### 📚 Manage Categories")

    categories = get_categories()
    for cat in categories:
        with st.expander(f"{cat['icon']} {cat['category_name']}"):
            cat_cols = st.columns([3, 1])
            with cat_cols[0]:
                st.markdown(f"**Description:** {cat.get('description', 'No description')}")
                q_count = get_question_count(cat["category_id"])
                st.caption(f"📊 {q_count} questions in this category")
            with cat_cols[1]:
                if st.button("🗑️ Delete", key=f"del_cat_{cat['category_id']}", use_container_width=True):
                    delete_category(cat["category_id"])
                    st.success("Deleted!")
                    st.rerun()

    st.markdown("---")
    st.markdown("#### ➕ Add New Category")
    with st.form("add_cat_form"):
        ac_cols = st.columns(3)
        with ac_cols[0]:
            ac_name = st.text_input("Category Name")
        with ac_cols[1]:
            ac_desc = st.text_input("Description")
        with ac_cols[2]:
            ac_icon = st.text_input("Icon (emoji)", value="📚")
        if st.form_submit_button("➕ Add Category", use_container_width=True):
            if ac_name:
                add_category(ac_name.strip(), ac_desc.strip(), ac_icon.strip())
                st.success(f"✅ Category '{ac_name}' added!")
                st.rerun()
            else:
                st.error("Please enter a category name.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: USER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════
with tab_users:
    st.markdown("### 👥 User Statistics")
    users = get_all_users()
    if users:
        user_data = []
        for u in users:
            user_data.append({
                "Name": u["name"],
                "Email": u["email"],
                "Role": u["role"].title(),
                "Quizzes": u.get("quizzes_taken", 0),
                "Joined": u["created_at"].strftime("%b %d, %Y") if u.get("created_at") else "N/A",
                "Auth": "Google" if u.get("google_id") else "Email"
            })
        df = pd.DataFrame(user_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"Total: {len(users)} users")
    else:
        st.info("No users registered yet.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5: LEADERBOARD VIEW
# ══════════════════════════════════════════════════════════════════════════════
with tab_leader:
    st.markdown("### 🏆 Leaderboard Overview")
    leaders = get_leaderboard(limit=20)
    if leaders:
        leader_data = []
        for i, l in enumerate(leaders, 1):
            leader_data.append({
                "Rank": i,
                "Name": l["name"],
                "Quizzes Taken": l["quizzes_taken"],
                "Total Score": l["total_score"],
                "Total Questions": l["total_questions"],
                "Avg %": l["avg_percentage"]
            })
        df = pd.DataFrame(leader_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No quiz results yet.")
