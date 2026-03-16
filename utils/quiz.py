"""
Quiz logic – question management, scoring, analytics, and leaderboard.
"""
import os
import json
import logging
from utils.db import execute_query, fetch_one, fetch_all
from utils.gemini_ai import generate_quiz_questions

log = logging.getLogger("quiz_app.quiz")

# ─── Fallback JSON dataset ────────────────────────────────────────────────────
_fallback_data = None
_FALLBACK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "fallback_questions.json"
)


def load_fallback_questions(category_name: str = None, difficulty: str = None, count: int = 10) -> list[dict]:
    """Load questions from the local JSON fallback dataset.
    Used as the absolute last resort when DB + Gemini are both unavailable."""
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
        # Fuzzy category match
        if category_name and category_name.lower() not in block["category"].lower():
            continue
        if difficulty and block.get("difficulty", "").lower() != difficulty.lower():
            continue
        for q in block.get("questions", []):
            results.append({
                **q,
                "category_name": block["category"],
                "difficulty": block.get("difficulty", "Medium"),
                "question_id": hash(q["question_text"]) % 100000,  # synthetic ID
            })

    # If no exact match, try without filters
    if not results and (category_name or difficulty):
        if category_name and difficulty:
            results = load_fallback_questions(category_name, None, count)
        if not results:
            results = load_fallback_questions(None, None, count)

    import random
    random.shuffle(results)
    return results[:count]


# ─── Categories ───────────────────────────────────────────────────────────────
def get_categories() -> list[dict]:
    return fetch_all("SELECT * FROM categories ORDER BY category_name")


def get_category_by_id(category_id: int) -> dict | None:
    return fetch_one("SELECT * FROM categories WHERE category_id = %s", (category_id,))


def add_category(name: str, description: str = None, icon: str = "📚") -> int:
    return execute_query(
        "INSERT INTO categories (category_name, description, icon) VALUES (%s, %s, %s)",
        (name, description, icon)
    )


def update_category(category_id: int, name: str, description: str = None, icon: str = "📚"):
    execute_query(
        "UPDATE categories SET category_name=%s, description=%s, icon=%s WHERE category_id=%s",
        (name, description, icon, category_id)
    )


def delete_category(category_id: int):
    execute_query("DELETE FROM categories WHERE category_id = %s", (category_id,))


# ─── Questions ────────────────────────────────────────────────────────────────
def get_questions(category_id: int = None, difficulty: str = None, limit: int = None) -> list[dict]:
    query = "SELECT q.*, c.category_name FROM questions q JOIN categories c ON q.category_id = c.category_id WHERE 1=1"
    params = []
    if category_id:
        query += " AND q.category_id = %s"
        params.append(category_id)
    if difficulty:
        query += " AND q.difficulty = %s"
        params.append(difficulty)
    query += " ORDER BY RAND()"
    if limit:
        query += f" LIMIT {int(limit)}"
    return fetch_all(query, tuple(params) if params else None)


def get_question_by_id(question_id: int) -> dict | None:
    return fetch_one(
        "SELECT q.*, c.category_name FROM questions q JOIN categories c ON q.category_id = c.category_id WHERE q.question_id = %s",
        (question_id,)
    )


def add_question(category_id: int, question_text: str, option1: str, option2: str,
                 option3: str, option4: str, correct_answer: str, explanation: str,
                 difficulty: str = "Medium") -> int:
    return execute_query(
        """INSERT INTO questions 
           (category_id, question_text, option1, option2, option3, option4, correct_answer, explanation, difficulty)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (category_id, question_text, option1, option2, option3, option4, correct_answer, explanation, difficulty)
    )


def update_question(question_id: int, **kwargs):
    allowed = {"category_id", "question_text", "option1", "option2", "option3", "option4",
               "correct_answer", "explanation", "difficulty"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    params = list(fields.values()) + [question_id]
    execute_query(f"UPDATE questions SET {set_clause} WHERE question_id = %s", tuple(params))


def delete_question(question_id: int):
    execute_query("DELETE FROM questions WHERE question_id = %s", (question_id,))


def get_question_count(category_id: int = None, difficulty: str = None) -> int:
    query = "SELECT COUNT(*) as cnt FROM questions WHERE 1=1"
    params = []
    if category_id:
        query += " AND category_id = %s"
        params.append(category_id)
    if difficulty:
        query += " AND difficulty = %s"
        params.append(difficulty)
    row = fetch_one(query, tuple(params) if params else None)
    return row["cnt"] if row else 0


# ─── AI-powered question generation & storage ────────────────────────────────
def generate_and_store_questions(topic: str, category_id: int, difficulty: str, count: int) -> list[dict]:
    """Generate questions via Gemini and store them in the database.
    Returns empty list if quota is exhausted (graceful fallback)."""
    try:
        questions = generate_quiz_questions(topic, difficulty, count)
    except Exception as e:
        import logging
        logging.getLogger("quiz_app").warning(f"Gemini generation failed: {e}")
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
    Fetch questions from DB. If not enough exist, generate more with Gemini.
    
    Returns a dict:
        {
            "questions": list[dict],
            "status":    "ok" | "partial" | "empty",
            "message":   str  (human-readable status message)
        }
    
    Fallback chain:
        1. Exact match (category + difficulty) from DB
        2. Generate via Gemini AI → store in DB
        3. Same category, any difficulty from DB
        4. Any category, any difficulty from DB
    """
    import logging
    log = logging.getLogger("quiz_app.quiz")

    # ── Step 1: Check DB for exact cache match ────────────────────────────────
    questions = get_questions(category_id, difficulty, count)
    if len(questions) >= count:
        log.info(f"DB cache hit: {len(questions)} questions (cat={category_id}, diff={difficulty})")
        return {
            "questions": questions[:count],
            "status": "ok",
            "message": f"Loaded {count} questions from database."
        }

    # ── Step 2: Try generating via Gemini AI ──────────────────────────────────
    category = get_category_by_id(category_id)
    topic = category["category_name"] if category else "General Knowledge"
    needed = count - len(questions)
    log.info(f"DB has {len(questions)}/{count}. Generating {needed} more via Gemini for '{topic}'")

    new_questions = generate_and_store_questions(topic, category_id, difficulty, needed)

    if new_questions:
        all_questions = get_questions(category_id, difficulty, count)
        return {
            "questions": all_questions[:count],
            "status": "ok",
            "message": f"Generated {len(new_questions)} new questions via AI."
        }

    # ── Step 3: Gemini failed — broaden DB search (any difficulty) ─────────
    log.warning("Gemini unavailable. Falling back to broader DB search.")

    if questions:
        # We have some questions with exact difficulty, return them
        return {
            "questions": questions,
            "status": "partial",
            "message": (
                f"AI quota exceeded. Showing {len(questions)} available questions "
                f"(requested {count}). More will be available when API quota resets."
            )
        }

    # Try same category, any difficulty
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

    # ── Step 5: JSON fallback dataset (absolute last resort) ────────────────
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

    # ── Truly nothing (fallback JSON also doesn't have this category) ─────
    # Try fallback with no filters at all
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
    """
    Generate a large batch of questions for a category/difficulty.
    Splits into smaller API calls to avoid hitting rate limits.
    
    Returns:
        {"generated": int, "failed": int, "total_in_db": int, "batches": int}
    """
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
            remaining -= batch  # Don't retry the same batch
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
    query = """
        SELECT q.*, c.category_name 
        FROM questions q
        JOIN categories c ON q.category_id = c.category_id
        WHERE c.category_name IN (
            SELECT interest_name FROM user_interests WHERE user_id = %s
        )
        ORDER BY RAND()
        LIMIT %s
    """
    return fetch_all(query, (user_id, count))


# ─── Quiz sessions & scoring ─────────────────────────────────────────────────
def create_quiz_session(user_id: int, category_id: int, difficulty: str, total_questions: int) -> int:
    return execute_query(
        "INSERT INTO quiz_sessions (user_id, category_id, difficulty, total_questions) VALUES (%s, %s, %s, %s)",
        (user_id, category_id, difficulty, total_questions)
    )


def submit_quiz(session_id: int, answers: list[dict], time_taken: int = None) -> dict:
    """
    Process quiz answers. Each answer dict: {question_id, selected_answer}
    Returns {score, total, percentage}.
    """
    if session_id is None:
        raise ValueError("session_id is required for quiz submission")

    session_meta = fetch_one(
        "SELECT category_id, difficulty FROM quiz_sessions WHERE session_id = %s",
        (session_id,),
    )
    if not session_meta:
        raise ValueError(f"quiz session not found: session_id={session_id}")

    score = 0
    total = len(answers)
    inserted_answers = 0

    for ans in answers:
        question_id = ans.get("question_id")

        selected_answer = ans.get("selected_answer")
        if selected_answer is None:
            selected_answer = ""

        question = get_question_by_id(question_id) if question_id is not None else None

        # If this question only exists in fallback payload, persist it first so FK insert works.
        if not question and ans.get("question_text") and ans.get("correct_answer"):
            try:
                category_id = ans.get("category_id") or session_meta["category_id"]
                existing = fetch_one(
                    "SELECT question_id FROM questions WHERE category_id = %s AND question_text = %s LIMIT 1",
                    (category_id, ans["question_text"]),
                )
                if existing and existing.get("question_id"):
                    question_id = existing["question_id"]
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
                    "Persisted fallback question for scoring: old_question_id=%s new_question_id=%s session_id=%s",
                    ans.get("question_id"),
                    question_id,
                    session_id,
                )
            except Exception as e:
                log.warning(
                    "Failed to persist fallback question (session_id=%s question_id=%s): %s",
                    session_id,
                    ans.get("question_id"),
                    e,
                )

        correct_answer = ans.get("correct_answer") or (question["correct_answer"] if question else None)
        if correct_answer is None:
            log.warning(
                "Missing correct_answer; forcing incorrect (session_id=%s question_id=%s)",
                session_id,
                question_id,
            )

        is_correct = 1 if selected_answer == correct_answer else 0

        # Defensive default to guarantee DB-safe values.
        if is_correct is None:
            is_correct = 0

        if is_correct not in (0, 1):
            log.warning(
                "Invalid is_correct=%s for session_id=%s question_id=%s; forcing 0",
                is_correct,
                session_id,
                question_id,
            )
            is_correct = 0

        if is_correct:
            score += 1

        log.info(
            "Inserting quiz_answer: session_id=%s question_id=%s selected_answer=%r correct_answer=%r is_correct=%s",
            session_id,
            question_id,
            selected_answer,
            correct_answer,
            is_correct,
        )

        if question_id is None or not question:
            log.warning(
                "Skipping answer insert: unresolved question reference (session_id=%s question_id=%s)",
                session_id,
                question_id,
            )
            continue

        execute_query(
            "INSERT INTO quiz_answers (session_id, question_id, selected_answer, is_correct) VALUES (%s, %s, %s, %s)",
            (session_id, question_id, selected_answer, is_correct)
        )
        inserted_answers += 1

    # Canonical score comes from persisted answers whenever inserts succeeded.
    if inserted_answers:
        row = fetch_one(
            "SELECT COUNT(*) AS cnt FROM quiz_answers WHERE session_id = %s AND is_correct = 1",
            (session_id,),
        )
        score = int(row["cnt"]) if row and row.get("cnt") is not None else score

    execute_query(
        "UPDATE quiz_sessions SET score = %s, time_taken = %s WHERE session_id = %s",
        (score, time_taken, session_id)
    )

    return {"score": score, "total": total, "percentage": round((score / total) * 100, 1) if total else 0}


# ─── Results & Analytics ─────────────────────────────────────────────────────
def get_user_results(user_id: int, limit: int = 20) -> list[dict]:
    return fetch_all(
        """SELECT qs.*, c.category_name 
           FROM quiz_sessions qs 
           JOIN categories c ON qs.category_id = c.category_id 
           WHERE qs.user_id = %s 
           ORDER BY qs.date_taken DESC LIMIT %s""",
        (user_id, limit)
    )


def get_session_details(session_id: int) -> list[dict]:
    return fetch_all(
        """SELECT qa.*, q.question_text, q.option1, q.option2, q.option3, q.option4,
                  q.correct_answer, q.explanation
           FROM quiz_answers qa
           JOIN questions q ON qa.question_id = q.question_id
           WHERE qa.session_id = %s""",
        (session_id,)
    )


def get_user_stats(user_id: int) -> dict:
    stats = fetch_one(
        """SELECT 
               COUNT(*) as total_quizzes,
               COALESCE(SUM(score), 0) as total_correct,
               COALESCE(SUM(total_questions), 0) as total_attempted,
               COALESCE(AVG(score * 100.0 / NULLIF(total_questions, 0)), 0) as avg_percentage,
               MAX(score * 100.0 / NULLIF(total_questions, 0)) as best_percentage
           FROM quiz_sessions WHERE user_id = %s""",
        (user_id,)
    )
    return stats or {"total_quizzes": 0, "total_correct": 0, "total_attempted": 0,
                     "avg_percentage": 0, "best_percentage": 0}


def get_category_stats(user_id: int) -> list[dict]:
    return fetch_all(
        """SELECT c.category_name, COUNT(*) as attempts,
                  AVG(qs.score * 100.0 / NULLIF(qs.total_questions, 0)) as avg_score
           FROM quiz_sessions qs
           JOIN categories c ON qs.category_id = c.category_id
           WHERE qs.user_id = %s
           GROUP BY c.category_name
           ORDER BY avg_score DESC""",
        (user_id,)
    )


# ─── Leaderboard ─────────────────────────────────────────────────────────────
def get_leaderboard(category_id: int = None, limit: int = 20) -> list[dict]:
    query = """
        SELECT u.name, u.avatar_url,
               COUNT(qs.session_id) as quizzes_taken,
               COALESCE(SUM(qs.score), 0) as total_score,
               COALESCE(SUM(qs.total_questions), 0) as total_questions,
               ROUND(AVG(qs.score * 100.0 / NULLIF(qs.total_questions, 0)), 1) as avg_percentage
        FROM users u
        JOIN quiz_sessions qs ON u.user_id = qs.user_id
    """
    params = []
    if category_id:
        query += " WHERE qs.category_id = %s"
        params.append(category_id)
    query += " GROUP BY u.user_id ORDER BY total_score DESC, avg_percentage DESC LIMIT %s"
    params.append(limit)
    return fetch_all(query, tuple(params))


# ─── Admin Stats ──────────────────────────────────────────────────────────────
def get_all_users() -> list[dict]:
    return fetch_all(
        """SELECT u.*, 
                  (SELECT COUNT(*) FROM quiz_sessions WHERE user_id = u.user_id) as quizzes_taken
           FROM users u ORDER BY u.created_at DESC"""
    )


def get_platform_stats() -> dict:
    total_users = fetch_one("SELECT COUNT(*) as cnt FROM users")
    total_questions = fetch_one("SELECT COUNT(*) as cnt FROM questions")
    total_quizzes = fetch_one("SELECT COUNT(*) as cnt FROM quiz_sessions")
    avg_score = fetch_one(
        "SELECT COALESCE(AVG(score * 100.0 / NULLIF(total_questions, 0)), 0) as avg FROM quiz_sessions"
    )
    return {
        "total_users": total_users["cnt"] if total_users else 0,
        "total_questions": total_questions["cnt"] if total_questions else 0,
        "total_quizzes": total_quizzes["cnt"] if total_quizzes else 0,
        "avg_score": round(avg_score["avg"], 1) if avg_score and avg_score["avg"] else 0,
    }
