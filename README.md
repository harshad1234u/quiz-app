# 🧠 AI Quiz Application

An AI-powered quiz application built with **Streamlit**, **Supabase (PostgreSQL)**, and **NVIDIA NIM API**.

## ✨ Features

- **AI-Generated Questions** – NVIDIA NIM generates MCQs with explanations
- **Personalized Quizzes** – Recommendations based on user interests
- **User Authentication** – Email/password + Google OAuth
- **Timed Quiz Gameplay** – With question navigation and progress tracking
- **Results & Analytics** – Score trends, radar charts, per-question review
- **Leaderboard** – Global rankings with podium display
- **Admin Dashboard** – Manage questions, categories, users; generate with AI

## 📁 Project Structure

```
quiz-app/
├── app.py                    # Main entry (home page)
├── requirements.txt          # Dependencies
├── .gitignore                # Git exclusions
├── README.md                 # This file
├── assets/
│   └── style.css             # Custom CSS
├── data/
│   └── fallback_questions.json  # Offline question bank
├── database/
│   ├── schema.sql            # PostgreSQL DDL (run in Supabase SQL Editor)
│   └── init_db.py            # Setup instructions
├── utils/
│   ├── __init__.py
│   ├── db.py                 # Supabase client singleton
│   ├── auth.py               # Authentication logic
│   ├── gemini_ai.py          # NVIDIA NIM API integration
│   └── quiz.py               # Quiz logic & analytics
├── pages/
│   ├── 1_🔐_Login.py         # Login / Register / Google
│   ├── 2_📊_Dashboard.py     # User dashboard
│   ├── 3_🧠_Quiz.py          # Quiz gameplay
│   ├── 4_📈_Results.py       # Analytics & history
│   ├── 5_🏆_Leaderboard.py   # Rankings
│   └── 6_⚙️_Admin.py         # Admin panel
└── .streamlit/
    └── secrets.toml.example  # Secrets template
```

## 🚀 Setup Instructions

### Prerequisites
- Python 3.10+
- A Supabase account ([supabase.com](https://supabase.com))
- NVIDIA NIM API Key ([build.nvidia.com](https://build.nvidia.com/))

### Step 1: Create Supabase Project
1. Go to [supabase.com](https://supabase.com) → **New Project**
2. Choose a name, password, and region
3. Once created, go to **Settings → API** and copy:
   - **Project URL** → `SUPABASE_URL`
   - **anon public key** → `SUPABASE_KEY`

### Step 2: Initialize Database
1. In Supabase, go to **SQL Editor**
2. Paste the contents of `database/schema.sql`
3. Click **Run**

This creates all tables, indexes, RLS policies, seed categories, and admin user.

### Step 3: Clone & Install Dependencies
```bash
git clone <your-repo-url>
cd quiz-app
pip install -r requirements.txt
```

### Step 4: Configure Secrets
```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```
Edit `.streamlit/secrets.toml` with your credentials:
```toml
SUPABASE_URL = "https://your-project-id.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUz..."
NVIDIA_API_KEY = "nvapi-..."
```

> ⚠️ **Never commit `secrets.toml` to Git!** It is already in `.gitignore`.

### Step 5: Run the App
```bash
streamlit run app.py
```

### Step 6: Login
- **Admin:** `admin@quizapp.com` / `admin123`
- Or register a new user account

---

## ☁️ Streamlit Cloud Deployment

1. **Push your code** to GitHub (secrets are excluded via `.gitignore`).

2. **Deploy on Streamlit Cloud:**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Connect your GitHub repo
   - Set the main file to `app.py`

3. **Add Secrets** in the Streamlit Cloud dashboard:
   - Go to **Settings → Secrets**
   - Paste the contents of `.streamlit/secrets.toml.example` and fill in real values

4. **Required secrets:**
   ```toml
   SUPABASE_URL = "https://your-project-id.supabase.co"
   SUPABASE_KEY = "eyJhbGciOiJIUz..."
   NVIDIA_API_KEY = "nvapi-..."
   ```

5. **Optional (Google OAuth):**
   ```toml
   GOOGLE_CLIENT_ID = "your_client_id"
   GOOGLE_CLIENT_SECRET = "your_client_secret"
   GOOGLE_REDIRECT_URI = "https://your-app.streamlit.app"
   ```

---

## 🔗 Supabase Connection Details

You need **two values** from your Supabase project:

| Secret | Where to find it | Example |
|--------|------------------|---------|
| `SUPABASE_URL` | Settings → API → Project URL | `https://abcdefgh.supabase.co` |
| `SUPABASE_KEY` | Settings → API → `anon` `public` key | `eyJhbGciOiJIUzI1NiIs...` |

> ⚠️ Use the **anon public** key, NOT the `service_role` key.
> Do NOT append `/rest/v1/` to the URL.

---

## 🗄️ Database Schema

| Table | Description |
|---|---|
| `users` | User accounts (email, hashed password, google_id, role, selected_topics JSONB) |
| `categories` | Quiz categories with icons |
| `questions` | MCQs with JSONB `options` array, correct answer, explanation |
| `quiz_sessions` | Quiz attempt metadata (score, time, difficulty) |
| `quiz_answers` | Per-question answer records |

### Questions Options Format
The `options` column stores choices as a JSONB array:
```json
["Option A", "Option B", "Option C", "Option D"]
```

## 🤖 AI Integration

The app uses NVIDIA NIM API to:
1. **Generate quiz questions** – Admin enters topic, difficulty, count → AI creates MCQs
2. **Auto-fill gaps** – If a category lacks questions, AI generates more on-the-fly
3. **Explain answers** – AI provides explanations for incorrect answers
4. **Suggest topics** – Personalized quiz topic recommendations based on interests

## 🔑 Google OAuth (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create OAuth 2.0 credentials
3. Set redirect URI to your app URL
4. Add `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI` to secrets
