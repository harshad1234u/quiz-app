"""
NVIDIA NIM AI integration – quiz question generation and explanations.

Uses NVIDIA's OpenAI-compatible API endpoint (api.nvidia.com/v1).
Supports any model available in NVIDIA NIM (default: meta/llama-3.1-8b-instruct).

Features:
  - Retry with exponential backoff on 429 / rate-limit
  - In-memory request cache to avoid duplicate API calls
  - Graceful fallback when quota is exhausted
  - Drop-in replacement for the old Gemini module (same public API)
  - Structured logging
"""
import os
import json
import re
import time
import logging
import hashlib
import threading
from openai import OpenAI, RateLimitError, APIStatusError
from dotenv import load_dotenv

load_dotenv()

# ─── Logging ──────────────────────────────────────────────────────────────────
logger = logging.getLogger("quiz_app.nvidia")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(_handler)

# ─── Config ───────────────────────────────────────────────────────────────────
NVIDIA_API_KEY    = os.getenv("NVIDIA_API_KEY", "").strip()
NVIDIA_BASE_URL   = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").strip()
NVIDIA_MODEL      = os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct").strip()
MAX_RETRIES       = 3
BASE_BACKOFF      = 2  # seconds

# ─── Request cache (avoids duplicate API calls within the same process) ───────
_request_cache: dict[str, str] = {}

# ─── Concurrency guard (one API call at a time to stay under rate limits) ─────
_api_lock = threading.Lock()

# ─── NVIDIA client (lazy singleton) ───────────────────────────────────────────
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not NVIDIA_API_KEY:
            logger.error("NVIDIA_API_KEY is missing or empty in .env")
            raise EnvironmentError(
                "NVIDIA_API_KEY is not configured. Add it to your .env file.\n"
                "Get your key at: https://build.nvidia.com/"
            )
        _client = OpenAI(
            base_url=NVIDIA_BASE_URL,
            api_key=NVIDIA_API_KEY,
        )
        logger.info(f"NVIDIA NIM client initialised (model={NVIDIA_MODEL}, base_url={NVIDIA_BASE_URL})")
    return _client


def _cache_key(*parts: str) -> str:
    """Create a deterministic cache key from request parameters."""
    return hashlib.md5("|".join(parts).encode()).hexdigest()


# ─── Core call helper with retry + backoff ────────────────────────────────────
def _call_nvidia(prompt: str, cache_key: str | None = None, max_tokens: int = 2048) -> str:
    """
    Call NVIDIA NIM with automatic retry on 429 Rate Limit errors.
    Uses a threading lock to prevent multiple simultaneous requests.
    Returns the raw text response.
    """
    # Check cache first (outside lock for speed)
    if cache_key and cache_key in _request_cache:
        logger.info(f"Cache hit for key {cache_key[:8]}...")
        return _request_cache[cache_key]

    with _api_lock:
        # Re-check inside lock (another thread may have populated it)
        if cache_key and cache_key in _request_cache:
            logger.info(f"Cache hit (inside lock) for key {cache_key[:8]}...")
            return _request_cache[cache_key]

        client = _get_client()
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"NVIDIA API call (attempt {attempt}/{MAX_RETRIES}, model={NVIDIA_MODEL})")
                completion = client.chat.completions.create(
                    model=NVIDIA_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=max_tokens,
                )
                raw = completion.choices[0].message.content.strip()

                if cache_key:
                    _request_cache[cache_key] = raw
                return raw

            except RateLimitError as e:
                last_error = e
                wait = BASE_BACKOFF ** attempt
                logger.warning(f"Rate limited (429). Retrying in {wait}s... (attempt {attempt}/{MAX_RETRIES})")
                time.sleep(wait)

            except APIStatusError as e:
                # Some providers return 429 as an APIStatusError
                if e.status_code == 429:
                    last_error = e
                    wait = BASE_BACKOFF ** attempt
                    logger.warning(f"API status 429. Retrying in {wait}s... (attempt {attempt}/{MAX_RETRIES})")
                    time.sleep(wait)
                else:
                    logger.error(f"NVIDIA APIStatusError {e.status_code}: {e}")
                    raise

            except Exception as e:
                logger.error(f"Unexpected NVIDIA API error: {e}")
                raise

        logger.error(f"All {MAX_RETRIES} retries exhausted. Last error: {last_error}")
        raise last_error


def _parse_json_array(raw: str) -> list[dict]:
    """Robustly extract a JSON array from the model's response text."""
    # Strip markdown code fences
    cleaned = re.sub(r'^```(?:json)?\s*', '', raw.strip())
    cleaned = re.sub(r'\s*```$', '', cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r'\[.*\]', cleaned, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"Model returned invalid JSON. Raw response:\n{raw[:500]}")


# ─── Quiz generation ─────────────────────────────────────────────────────────
def generate_quiz_questions(topic: str, difficulty: str = "Medium", count: int = 5) -> list[dict]:
    """
    Ask NVIDIA NIM to generate MCQ quiz questions.
    Returns a list of dicts with keys:
        question_text, option1, option2, option3, option4, correct_answer, explanation
    Falls back to an empty list if quota is fully exhausted.
    """
    prompt = f"""Generate exactly {count} multiple-choice quiz questions about "{topic}" \
at {difficulty} difficulty level.

IMPORTANT: Return ONLY a valid JSON array. No markdown, no code fences, no extra text.

Each element must be a JSON object with exactly these keys:
- "question_text": the question string
- "option1": first option
- "option2": second option
- "option3": third option
- "option4": fourth option
- "correct_answer": the full text of the correct option (must match one of option1–option4 exactly)
- "explanation": a short explanation of why the correct answer is right (2-3 sentences)

Rules:
1. All four options must be plausible.
2. Only one option is correct.
3. Vary the position of the correct answer across questions.
4. Make sure explanations are educational and concise.
"""

    cache_k = _cache_key("quiz", topic, difficulty, str(count))

    try:
        raw = _call_nvidia(prompt, cache_key=cache_k, max_tokens=3000)
    except (RateLimitError, APIStatusError) as e:
        logger.warning(f"Quota/rate-limit exhausted – returning empty list. Error: {e}")
        return []
    except Exception as e:
        logger.error(f"generate_quiz_questions failed: {e}")
        return []

    try:
        questions = _parse_json_array(raw)
    except ValueError as e:
        logger.error(f"JSON parse error: {e}")
        return []

    # Validate structure
    required_keys = {"question_text", "option1", "option2", "option3", "option4", "correct_answer", "explanation"}
    validated = [q for q in questions if required_keys.issubset(q.keys())]

    logger.info(f"Generated {len(validated)} valid questions for '{topic}' ({difficulty})")
    return validated


# ─── Explanation generation ───────────────────────────────────────────────────
def generate_explanation(question: str, correct_answer: str, user_answer: str = None) -> str:
    """Generate an AI explanation for a quiz question."""
    prompt = f"""Explain the following quiz question and its correct answer in a clear, educational way.

Question: {question}
Correct Answer: {correct_answer}
"""
    if user_answer and user_answer != correct_answer:
        prompt += f"User's Answer: {user_answer}\nAlso explain why the user's answer is incorrect.\n"

    prompt += "\nKeep the explanation concise (3-5 sentences). Be educational and encouraging."

    cache_k = _cache_key("explain", question, correct_answer, user_answer or "")

    try:
        return _call_nvidia(prompt, cache_key=cache_k, max_tokens=500)
    except (RateLimitError, APIStatusError):
        return f"The correct answer is: {correct_answer}. (AI explanation unavailable – quota exceeded.)"
    except Exception as e:
        logger.error(f"generate_explanation error: {e}")
        return f"The correct answer is: {correct_answer}."


# ─── Smart recommendation prompt ─────────────────────────────────────────────
def suggest_topics(interests: list[str], past_topics: list[str] = None) -> list[str]:
    """Suggest quiz topics based on user interests using NVIDIA NIM."""
    past_str = ""
    if past_topics:
        past_str = f"\nThey have already taken quizzes on: {', '.join(past_topics)}. Suggest different sub-topics."

    prompt = f"""A quiz app user is interested in: {', '.join(interests)}.{past_str}

Suggest exactly 5 specific quiz topic names they might enjoy.
Return ONLY a JSON array of strings. No markdown, no code fences, no explanation.
Example: ["SQL Injection Prevention", "Python Data Structures", "Neural Network Basics"]
"""

    cache_k = _cache_key("suggest", ",".join(interests), ",".join(past_topics or []))

    try:
        raw = _call_nvidia(prompt, cache_key=cache_k, max_tokens=200)
    except Exception:
        return [f"{interest} Basics" for interest in interests[:5]]

    cleaned = re.sub(r'^```(?:json)?\s*', '', raw.strip())
    cleaned = re.sub(r'\s*```$', '', cleaned)

    try:
        topics = json.loads(cleaned)
        return [str(t) for t in topics[:5]]
    except json.JSONDecodeError:
        return [f"{interest} Basics" for interest in interests[:5]]


def clear_cache():
    """Clear the in-memory request cache."""
    global _request_cache
    _request_cache.clear()
    logger.info("Request cache cleared")
