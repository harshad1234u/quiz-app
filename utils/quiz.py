"""
Quiz logic – question management, scoring, analytics, and leaderboard.
Uses Supabase (PostgREST) for all database operations.

SCHEMA NOTE:
  The 'questions' table now uses a JSONB `options` column instead of
  option1..option4.  Format: ["Option A", "Option B", "Option C", "Option D"]
  For backward compatibility with page code that reads option1..option4,
  every row returned from helper functions is enriched with those keys.
"""
import os
import json
import random
import logging
from utils.db import get_supabase
from utils.gemini_ai import generate_quiz_questions

log = logging.getLogger("quiz_app.quiz")

# ─── Fallback JSON dataset ────────────────────────────────────────────────────
_fallback_data = None
_FALLBACK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "fallback_questions.json"
)


def load_fallback_questions(category_name: str = None, difficulty: str = None, count: int = 10) -> list[dict]:
    """Load questions from the local JSON fallback dataset."""
    global _fallback_data
    if _fallback_data is None:
        try:
            with open(_FALLBACK_PATH, "r", encoding="utf-8") as f:
                _fallback_data = json.load(f)
            log.info(f"Loaded fallback dataset from {_FALLBACK_PATH}")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            log.error(f"Failed to load fallback dataset: {e}")
            return []

    results = []
    for block in _fallback_data:
        if category_name and category_name.lower() not in block["category"].lower():
            continue
        if difficulty and block.get("difficulty", "").lower() != difficulty.lower():
            continue
        for q in block.get("questions", []):
            results.append({
                **q,
                "category_name": block["category"],
                "difficulty": block.get("difficulty", "Medium"),
                "question_id": hash(q["question_text"]) % 100000,
            })

    if not results and (category_name or difficulty):
        if category_name and difficulty:
            results = load_fallback_questions(category_name, None, count)
        if not results:
            results = load_fallback_questions(None, None, count)

    random.shuffle(results)
    return results[:count]


# ─── Row enrichment (JSONB options → option1..4 keys) ────────────────────────
def _enrich_question(row: dict) -> dict:
    """Add option1..option4 keys from the JSONB `options` column for backward compat."""
    opts = row.get("options") or []
    # If options is a string (shouldn't be, but defensive), parse it
    if isinstance(opts, str):
        try:
            opts = json.loads(opts)
        except json.JSONDecodeError:
            opts = []
    for i in range(4):
        row[f"option{i+1}"] = opts[i] if i < len(opts) else ""
    return row


# ─── Categories ───────────────────────────────────────────────────────────────
def get_categories() -> list[dict]:
    sb = get_supabase()
    result = sb.table("categories").select("*").order("category_name").execute()
    return result.data


def get_category_by_id(category_id: int) -> dict | None:
    sb = get_supabase()
    result = sb.table("categories").select("*").eq("category_id", category_id).execute()
    return result.data[0] if result.data else None


def add_category(name: str, description: str = None, icon: str = "📚") -> int:
    sb = get_supabase()
    result = sb.table("categories").insert({
        "category_name": name, "description": description, "icon": icon
    }).execute()
    return result.data[0]["category_id"] if result.data else None


def update_category(category_id: int, name: str, description: str = None, icon: str = "📚"):
    sb = get_supabase()
    sb.table("categories").update({
        "category_name": name, "description": description, "icon": icon
    }).eq("category_id", category_id).execute()


def delete_category(category_id: int):
    sb = get_supabase()
    sb.table("categories").delete().eq("category_id", category_id).execute()


# ─── Questions ────────────────────────────────────────────────────────────────
def get_questions(category_id: int = None, difficulty: str = None, limit: int = None) -> list[dict]:
    sb = get_supabase()
    query = sb.table("questions").select("*, categories(category_name)")
    if category_id:
        query = query.eq("category_id", category_id)
    if difficulty:
        query = query.eq("difficulty", difficulty)
    if limit:
        query = query.limit(limit)
    result = query.execute()
    rows = result.data or []
    # Flatten the joined category_name and shuffle (replaces ORDER BY RAND())
    for r in rows:
        cat = r.pop("categories", None)
        r["category_name"] = cat["category_name"] if cat else ""
        _enrich_question(r)
    random.shuffle(rows)
    return rows


def get_question_by_id(question_id: int) -> dict | None:
    sb = get_supabase()
    result = sb.table("questions").select("*, categories(category_name)").eq("question_id", question_id).execute()
    if not result.data:
        return None
    row = result.data[0]
    cat = row.pop("categories", None)
    row["category_name"] = cat["category_name"] if cat else ""
    return _enrich_question(row)


def add_question(category_id: int, question_text: str, option1: str, option2: str,
                 option3: str, option4: str, correct_answer: str, explanation: str,
                 difficulty: str = "Medium") -> int:
    """Insert a question. Converts option1..4 → JSONB options array."""
    sb = get_supabase()
    result = sb.table("questions").insert({
        "category_id": category_id,
        "question_text": question_text,
        "options": [option1, option2, option3, option4],
        "correct_answer": correct_answer,
        "explanation": explanation,
        "difficulty": difficulty,
    }).execute()
    return result.data[0]["question_id"] if result.data else None


def update_question(question_id: int, **kwargs):
    allowed = {"category_id", "question_text", "correct_answer", "explanation", "difficulty"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    # Handle option1..4 → options JSONB conversion
    opt_keys = {"option1", "option2", "option3", "option4"}
    if opt_keys & kwargs.keys():
        # Fetch current options to merge partial updates
        current = get_question_by_id(question_id)
        current_opts = [current.get(f"option{i+1}", "") for i in range(4)] if current else ["", "", "", ""]
        for i, k in enumerate(["option1", "option2", "option3", "option4"]):
            if k in kwargs:
                current_opts[i] = kwargs[k]
        fields["options"] = current_opts
    if not fields:
        return
    sb = get_supabase()
    sb.table("questions").update(fields).eq("question_id", question_id).execute()


def delete_question(question_id: int):
    sb = get_supabase()
    sb.table("questions").delete().eq("question_id", question_id).execute()


def get_question_count(category_id: int = None, difficulty: str = None) -> int:
    sb = get_supabase()
    query = sb.table("questions").select("question_id", count="exact")
    if category_id:
        query = query.eq("category_id", category_id)
    if difficulty:
        query = query.eq("difficulty", difficulty)
    result = query.execute()
    return result.count if result.count is not None else len(result.data)


# ─── AI-powered question generation & storage ────────────────────────────────
def generate_and_store_questions(topic: str, category_id: int, difficulty: str, count: int) -> list[dict]:
    """Generate questions via AI and store them in the database."""
    try:
        questions = generate_quiz_questions(topic, difficulty, count)
    except Exception as e:
        log.warning(f"AI generation failed: {e}")
        return []

    if not questions:
        return []

    for q in questions:
        q["question_id"] = add_question(
            category_id=category_id,
            question_text=q["question_text"],
            option1=q["option1"],
            option2=q["option2"],
            option3=q["option3"],
            option4=q["option4"],
            correct_answer=q["correct_answer"],
            explanation=q.get("explanation", ""),
            difficulty=difficulty
        )
    return questions


# ─── Quiz fetch with AI fallback ─────────────────────────────────────────────
def get_quiz_questions(category_id: int, difficulty: str, count: int = 10) -> dict:
    """
    Fetch questions from DB. If not enough exist, generate more with AI.

    Returns a dict:
        {"questions": list[dict], "status": "ok"|"partial"|"empty", "message": str}

    Fallback chain:
        1. Exact match (category + difficulty) from DB
        2. Generate via AI → store in DB
        3. Same category, any difficulty from DB
        4. Any category, any difficulty from DB
        5. Local JSON fallback
    """
    # ── Step 1: Check DB for exact match ──────────────────────────────────────
    questions = get_questions(category_id, difficulty, count)
    if len(questions) >= count:
        log.info(f"DB cache hit: {len(questions)} questions (cat={category_id}, diff={difficulty})")
        return {
            "questions": questions[:count],
            "status": "ok",
            "message": f"Loaded {count} questions from database."
        }

    # ── Step 2: Try generating via AI ─────────────────────────────────────────
    category = get_category_by_id(category_id)
    topic = category["category_name"] if category else "General Knowledge"
    needed = count - len(questions)
    log.info(f"DB has {len(questions)}/{count}. Generating {needed} more via AI for '{topic}'")

    new_questions = generate_and_store_questions(topic, category_id, difficulty, needed)

    if new_questions:
        all_questions = get_questions(category_id, difficulty, count)
        return {
            "questions": all_questions[:count],
            "status": "ok",
            "message": f"Generated {len(new_questions)} new questions via AI."
        }

    # ── Step 3: AI failed — broaden DB search ─────────────────────────────────
    log.warning("AI unavailable. Falling back to broader DB search.")

    if questions:
        return {
            "questions": questions,
            "status": "partial",
            "message": (
                f"AI quota exceeded. Showing {len(questions)} available questions "
                f"(requested {count}). More will be available when API quota resets."
            )
        }

    any_diff_questions = get_questions(category_id, None, count)
    if any_diff_questions:
        log.info(f"Fallback: found {len(any_diff_questions)} questions across all difficulties")
        return {
            "questions": any_diff_questions[:count],
            "status": "partial",
            "message": (
                f"AI quota exceeded. Showing {len(any_diff_questions[:count])} questions "
                f"from mixed difficulty levels."
            )
        }

    # ── Step 4: Last resort — any category at all ─────────────────────────────
    any_questions = get_questions(None, None, count)
    if any_questions:
        log.info(f"Fallback: using {len(any_questions)} questions from other categories")
        return {
            "questions": any_questions[:count],
            "status": "partial",
            "message": (
                f"AI quota exceeded and no questions found for '{topic}'. "
                f"Showing {len(any_questions[:count])} questions from other categories."
            )
        }

    # ── Step 5: JSON fallback dataset ─────────────────────────────────────────
    category = get_category_by_id(category_id)
    cat_name = category["category_name"] if category else None
    fallback = load_fallback_questions(cat_name, difficulty, count)
    if fallback:
        log.info(f"Using JSON fallback: {len(fallback)} questions for '{cat_name}' ({difficulty})")
        return {
            "questions": fallback,
            "status": "partial",
            "message": (
                f"Using offline question bank ({len(fallback)} questions). "
                f"AI-generated questions will be available when API quota resets."
            )
        }

    any_fallback = load_fallback_questions(None, None, count)
    if any_fallback:
        return {
            "questions": any_fallback,
            "status": "partial",
            "message": (
                f"Using general offline questions ({len(any_fallback)} questions). "
                f"Category-specific questions will be available when API quota resets."
            )
        }

    return {
        "questions": [],
        "status": "empty",
        "message": (
            "No questions available. The AI quota is exceeded, the database is empty, "
            "and the fallback dataset could not be loaded. Please contact an administrator."
        )
    }


# ─── Admin bulk pre-generation ───────────────────────────────────────────────
def bulk_generate_questions(
    category_id: int, difficulty: str, total: int = 50, batch_size: int = 10
) -> dict:
    """Generate a large batch of questions for a category/difficulty."""
    category = get_category_by_id(category_id)
    topic = category["category_name"] if category else "General Knowledge"

    generated = 0
    failed = 0
    batches = 0
    remaining = total

    while remaining > 0:
        batch = min(remaining, batch_size)
        batches += 1
        log.info(f"Bulk generation batch {batches}: {batch} questions for '{topic}' ({difficulty})")

        result = generate_and_store_questions(topic, category_id, difficulty, batch)
        if result:
            generated += len(result)
            remaining -= len(result)
        else:
            failed += batch
            remaining -= batch
            log.warning(f"Batch {batches} failed. Moving on.")

    total_in_db = get_question_count(category_id, difficulty)
    log.info(f"Bulk generation complete: {generated} generated, {failed} failed, {total_in_db} total in DB")

    return {
        "generated": generated,
        "failed": failed,
        "total_in_db": total_in_db,
        "batches": batches
    }


# ─── Personalized quizzes ────────────────────────────────────────────────────
def get_recommended_questions(user_id: int, count: int = 10) -> list[dict]:
    """Fetch questions matching user interests."""
    sb = get_supabase()

    interests_result = sb.table("user_interests").select("interest_name").eq("user_id", user_id).execute()
    interest_names = [r["interest_name"] for r in interests_result.data]

    if not interest_names:
        return []

    # Get category IDs matching interests
    cat_result = sb.table("categories").select("category_id").in_("category_name", interest_names).execute()
    cat_ids = [r["category_id"] for r in cat_result.data]
    if not cat_ids:
        return []

    # Fetch questions in those categories
    q_result = sb.table("questions").select("*, categories(category_name)").in_("category_id", cat_ids).limit(count * 3).execute()
    rows = q_result.data or []
    for r in rows:
        cat = r.pop("categories", None)
        r["category_name"] = cat["category_name"] if cat else ""
        _enrich_question(r)
    random.shuffle(rows)
    return rows[:count]


# ─── Quiz sessions & scoring ─────────────────────────────────────────────────
def create_quiz_session(user_id: int, category_id: int, difficulty: str, total_questions: int) -> int:
    sb = get_supabase()
    result = sb.table("quiz_sessions").insert({
        "user_id": user_id,
        "category_id": category_id,
        "difficulty": difficulty,
        "total_questions": total_questions
    }).execute()
    return result.data[0]["session_id"] if result.data else None


def submit_quiz(session_id: int, answers: list[dict], time_taken: int = None) -> dict:
    """
    Process quiz answers. Each answer dict: {question_id, selected_answer}
    Returns {score, total, percentage}.
    """
    if session_id is None:
        raise ValueError("session_id is required for quiz submission")

    sb = get_supabase()

    session_result = sb.table("quiz_sessions").select("category_id, difficulty").eq("session_id", session_id).execute()
    if not session_result.data:
        raise ValueError(f"quiz session not found: session_id={session_id}")
    session_meta = session_result.data[0]

    score = 0
    total = len(answers)
    inserted_answers = 0

    for ans in answers:
        question_id = ans.get("question_id")
        selected_answer = ans.get("selected_answer") or ""

        question = get_question_by_id(question_id) if question_id is not None else None

        # If question only exists in fallback payload, persist it first
        if not question and ans.get("question_text") and ans.get("correct_answer"):
            try:
                category_id = ans.get("category_id") or session_meta["category_id"]

                # Check if question already exists by text
                existing = sb.table("questions").select("question_id").eq(
                    "category_id", category_id
                ).eq("question_text", ans["question_text"]).limit(1).execute()

                if existing.data:
                    question_id = existing.data[0]["question_id"]
                    question = get_question_by_id(question_id)

                if not question:
                    question_id = add_question(
                        category_id=category_id,
                        question_text=ans["question_text"],
                        option1=ans.get("option1", ""),
                        option2=ans.get("option2", ""),
                        option3=ans.get("option3", ""),
                        option4=ans.get("option4", ""),
                        correct_answer=ans["correct_answer"],
                        explanation=ans.get("explanation", ""),
                        difficulty=ans.get("difficulty") or session_meta.get("difficulty") or "Medium",
                    )
                    question = get_question_by_id(question_id)

                log.info(
                    "Persisted fallback question: old_id=%s new_id=%s session=%s",
                    ans.get("question_id"), question_id, session_id,
                )
            except Exception as e:
                log.warning("Failed to persist fallback question (session=%s): %s", session_id, e)

        correct_answer = ans.get("correct_answer") or (question["correct_answer"] if question else None)
        if correct_answer is None:
            log.warning("Missing correct_answer; forcing incorrect (session=%s question=%s)", session_id, question_id)

        is_correct = selected_answer == correct_answer

        if is_correct:
            score += 1

        if question_id is None or not question:
            log.warning("Skipping answer insert: unresolved question (session=%s question=%s)", session_id, question_id)
            continue

        sb.table("quiz_answers").insert({
            "session_id": session_id,
            "question_id": question_id,
            "selected_answer": selected_answer,
            "is_correct": is_correct,
        }).execute()
        inserted_answers += 1

    # Canonical score from persisted answers
    if inserted_answers:
        count_result = sb.table("quiz_answers").select("answer_id", count="exact").eq(
            "session_id", session_id
        ).eq("is_correct", True).execute()
        score = count_result.count if count_result.count is not None else score

    sb.table("quiz_sessions").update({
        "score": score, "time_taken": time_taken
    }).eq("session_id", session_id).execute()

    return {"score": score, "total": total, "percentage": round((score / total) * 100, 1) if total else 0}


# ─── Results & Analytics ─────────────────────────────────────────────────────
def get_user_results(user_id: int, limit: int = 20) -> list[dict]:
    sb = get_supabase()
    result = sb.table("quiz_sessions").select(
        "*, categories(category_name)"
    ).eq("user_id", user_id).order("date_taken", desc=True).limit(limit).execute()
    rows = result.data or []
    for r in rows:
        cat = r.pop("categories", None)
        r["category_name"] = cat["category_name"] if cat else ""
    return rows


def get_session_details(session_id: int) -> list[dict]:
    sb = get_supabase()
    result = sb.table("quiz_answers").select(
        "*, questions(question_text, options, correct_answer, explanation)"
    ).eq("session_id", session_id).execute()
    rows = result.data or []
    for r in rows:
        q = r.pop("questions", None) or {}
        r["question_text"] = q.get("question_text", "")
        r["correct_answer"] = q.get("correct_answer", "")
        r["explanation"] = q.get("explanation", "")
        opts = q.get("options") or []
        if isinstance(opts, str):
            try:
                opts = json.loads(opts)
            except json.JSONDecodeError:
                opts = []
        for i in range(4):
            r[f"option{i+1}"] = opts[i] if i < len(opts) else ""
    return rows


def get_user_stats(user_id: int) -> dict:
    sb = get_supabase()
    result = sb.table("quiz_sessions").select("score, total_questions").eq("user_id", user_id).execute()
    rows = result.data or []
    if not rows:
        return {"total_quizzes": 0, "total_correct": 0, "total_attempted": 0,
                "avg_percentage": 0, "best_percentage": 0}

    total_quizzes = len(rows)
    total_correct = sum(r["score"] for r in rows)
    total_attempted = sum(r["total_questions"] for r in rows)
    percentages = [
        (r["score"] * 100.0 / r["total_questions"]) if r["total_questions"] else 0
        for r in rows
    ]
    avg_percentage = sum(percentages) / len(percentages) if percentages else 0
    best_percentage = max(percentages) if percentages else 0

    return {
        "total_quizzes": total_quizzes,
        "total_correct": total_correct,
        "total_attempted": total_attempted,
        "avg_percentage": avg_percentage,
        "best_percentage": best_percentage,
    }


def get_category_stats(user_id: int) -> list[dict]:
    sb = get_supabase()
    result = sb.table("quiz_sessions").select(
        "score, total_questions, categories(category_name)"
    ).eq("user_id", user_id).execute()
    rows = result.data or []

    from collections import defaultdict
    agg = defaultdict(list)
    for r in rows:
        cat = r.get("categories") or {}
        cat_name = cat.get("category_name", "Unknown")
        pct = (r["score"] * 100.0 / r["total_questions"]) if r["total_questions"] else 0
        agg[cat_name].append(pct)

    stats = []
    for cat_name, scores in sorted(agg.items(), key=lambda x: -(sum(x[1]) / len(x[1]))):
        stats.append({
            "category_name": cat_name,
            "attempts": len(scores),
            "avg_score": sum(scores) / len(scores) if scores else 0,
        })
    return stats


# ─── Leaderboard ─────────────────────────────────────────────────────────────
def get_leaderboard(category_id: int = None, limit: int = 20) -> list[dict]:
    sb = get_supabase()
    query = sb.table("quiz_sessions").select(
        "user_id, score, total_questions, users(name, avatar_url)"
    )
    if category_id:
        query = query.eq("category_id", category_id)
    result = query.execute()
    rows = result.data or []

    from collections import defaultdict
    agg = defaultdict(lambda: {"name": "", "avatar_url": None, "scores": [], "totals": []})
    for r in rows:
        uid = r["user_id"]
        user_info = r.get("users") or {}
        agg[uid]["name"] = user_info.get("name", "")
        agg[uid]["avatar_url"] = user_info.get("avatar_url")
        agg[uid]["scores"].append(r["score"])
        agg[uid]["totals"].append(r["total_questions"])

    leaders = []
    for uid, data in agg.items():
        total_score = sum(data["scores"])
        total_questions = sum(data["totals"])
        quizzes_taken = len(data["scores"])
        pcts = [
            (s * 100.0 / t) if t else 0
            for s, t in zip(data["scores"], data["totals"])
        ]
        avg_pct = sum(pcts) / len(pcts) if pcts else 0
        leaders.append({
            "name": data["name"],
            "avatar_url": data["avatar_url"],
            "quizzes_taken": quizzes_taken,
            "total_score": total_score,
            "total_questions": total_questions,
            "avg_percentage": round(avg_pct, 1),
        })

    leaders.sort(key=lambda x: (-x["total_score"], -x["avg_percentage"]))
    return leaders[:limit]


# ─── Admin Stats ──────────────────────────────────────────────────────────────
def get_all_users() -> list[dict]:
    sb = get_supabase()
    users_result = sb.table("users").select("*").order("created_at", desc=True).execute()
    users = users_result.data or []

    # Get quiz counts per user
    sessions = sb.table("quiz_sessions").select("user_id").execute()
    from collections import Counter
    counts = Counter(r["user_id"] for r in (sessions.data or []))

    for u in users:
        u["quizzes_taken"] = counts.get(u["user_id"], 0)
    return users


def get_platform_stats() -> dict:
    sb = get_supabase()
    users = sb.table("users").select("user_id", count="exact").execute()
    questions = sb.table("questions").select("question_id", count="exact").execute()
    sessions = sb.table("quiz_sessions").select("score, total_questions").execute()

    total_users = users.count if users.count is not None else 0
    total_questions = questions.count if questions.count is not None else 0

    session_rows = sessions.data or []
    total_quizzes = len(session_rows)
    if session_rows:
        pcts = [
            (r["score"] * 100.0 / r["total_questions"]) if r["total_questions"] else 0
            for r in session_rows
        ]
        avg_score = sum(pcts) / len(pcts)
    else:
        avg_score = 0

    return {
        "total_users": total_users,
        "total_questions": total_questions,
        "total_quizzes": total_quizzes,
        "avg_score": round(avg_score, 1),
    }
