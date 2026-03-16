# 🧠 AI Quiz Application

An AI-powered quiz application built with **Streamlit**, **MySQL**, and **Google Gemini API**.

## ✨ Features

- **AI-Generated Questions** – Gemini generates MCQs with explanations
- **Personalized Quizzes** – Recommendations based on user interests
- **User Authentication** – Email/password + Google OAuth
- **Timed Quiz Gameplay** – With question navigation and progress tracking
- **Results & Analytics** – Score trends, radar charts, per-question review
- **Leaderboard** – Global rankings with podium display
- **Admin Dashboard** – Manage questions, categories, users; generate with AI

## 📁 Project Structure

```
quiz app/
├── app.py                    # Main entry (home page)
├── requirements.txt          # Dependencies
├── .env.example              # Environment template
├── assets/style.css          # Custom CSS
├── database/
│   ├── schema.sql            # MySQL DDL
│   └── init_db.py            # DB initializer
├── utils/
│   ├── db.py                 # MySQL connection pool
│   ├── auth.py               # Authentication logic
│   ├── gemini_ai.py          # Gemini API integration
│   └── quiz.py               # Quiz logic & analytics
└── pages/
    ├── 1_🔐_Login.py         # Login / Register / Google
    ├── 2_📊_Dashboard.py     # User dashboard
    ├── 3_🧠_Quiz.py          # Quiz gameplay
    ├── 4_📈_Results.py       # Analytics & history
    ├── 5_🏆_Leaderboard.py   # Rankings
    └── 6_⚙️_Admin.py         # Admin panel
```

## 🚀 Setup Instructions

### Prerequisites
- Python 3.10+
- MySQL Server (running)
- Google Gemini API Key

### Step 1: Install Dependencies
```bash
cd "quiz app"
pip install -r requirements.txt
```

### Step 2: Configure Environment
```bash
copy .env.example .env
```
Edit `.env` with your credentials:
```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=quiz_app
GEMINI_API_KEY=your_gemini_api_key
```

### Step 3: Initialize Database
```bash
python database/init_db.py
```
This creates the `quiz_app` database, all tables, default categories, and an admin user.

### Step 4: Run the App
```bash
streamlit run app.py
```

### Step 5: Login
- **Admin:** `admin@quizapp.com` / `admin123`
- Or register a new user account

## 🗄️ Database Schema

| Table | Description |
|---|---|
| `users` | User accounts (email, hashed password, google_id, role) |
| `user_interests` | User interest selections |
| `categories` | Quiz categories with icons |
| `questions` | MCQ questions with 4 options, answer, explanation |
| `quiz_sessions` | Quiz attempt metadata (score, time, difficulty) |
| `quiz_answers` | Per-question answer records |

## 🤖 Gemini API Integration

The app uses Gemini to:
1. **Generate quiz questions** – Admin enters topic, difficulty, count → AI creates MCQs
2. **Auto-fill gaps** – If a category lacks questions, AI generates more on-the-fly
3. **Explain answers** – AI provides explanations for incorrect answers
4. **Suggest topics** – Personalized quiz topic recommendations based on interests

### Example Prompt
```
Generate 5 multiple-choice quiz questions about "SQL Injection" at Medium difficulty.
Each with: question_text, option1-4, correct_answer, explanation.
```

## 🔑 Google OAuth (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create OAuth 2.0 credentials
3. Set redirect URI to `http://localhost:8501`
4. Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to `.env`

## 📸 Pages Overview

| Page | Description |
|---|---|
| 🏠 Home | Landing page with feature cards and platform stats |
| 🔐 Login | Email login, registration with interests, Google OAuth |
| 📊 Dashboard | Stats, quick-start buttons, AI suggestions, history charts |
| 🧠 Quiz | Category selection → timed gameplay → instant results |
| 📈 Results | Score trends, radar chart, difficulty analysis, attempt history |
| 🏆 Leaderboard | Top-3 podium, full rankings with user highlight |
| ⚙️ Admin | AI generation, question CRUD, category management, user stats |
