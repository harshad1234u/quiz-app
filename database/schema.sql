-- ============================================
-- AI Quiz Application – MySQL Database Schema
-- ============================================

CREATE DATABASE IF NOT EXISTS quiz_app
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE quiz_app;

-- ------------------------------------------
-- 1. Users
-- ------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id       INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100)  NOT NULL,
    email         VARCHAR(255)  NOT NULL UNIQUE,
    password      VARCHAR(255)  DEFAULT NULL,   -- NULL when signed-in via Google
    google_id     VARCHAR(255)  DEFAULT NULL UNIQUE,
    role          ENUM('admin', 'user') NOT NULL DEFAULT 'user',
    avatar_url    VARCHAR(512)  DEFAULT NULL,
    created_at    TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ------------------------------------------
-- 2. User Interests
-- ------------------------------------------
CREATE TABLE IF NOT EXISTS user_interests (
    interest_id   INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT           NOT NULL,
    interest_name VARCHAR(100)  NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE KEY uq_user_interest (user_id, interest_name)
) ENGINE=InnoDB;

-- ------------------------------------------
-- 3. Categories
-- ------------------------------------------
CREATE TABLE IF NOT EXISTS categories (
    category_id   INT AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(100)  NOT NULL UNIQUE,
    description   VARCHAR(500)  DEFAULT NULL,
    icon          VARCHAR(10)   DEFAULT '📚',
    created_at    TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ------------------------------------------
-- 4. Questions
-- ------------------------------------------
CREATE TABLE IF NOT EXISTS questions (
    question_id   INT AUTO_INCREMENT PRIMARY KEY,
    category_id   INT           NOT NULL,
    question_text TEXT          NOT NULL,
    option1       VARCHAR(500)  NOT NULL,
    option2       VARCHAR(500)  NOT NULL,
    option3       VARCHAR(500)  NOT NULL,
    option4       VARCHAR(500)  NOT NULL,
    correct_answer VARCHAR(500) NOT NULL,
    explanation   TEXT          DEFAULT NULL,
    difficulty    ENUM('Easy', 'Medium', 'Hard') NOT NULL DEFAULT 'Medium',
    created_at    TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE CASCADE,
    INDEX idx_cat_diff (category_id, difficulty)
) ENGINE=InnoDB;

-- ------------------------------------------
-- 5. Quiz Sessions (one row per attempt)
-- ------------------------------------------
CREATE TABLE IF NOT EXISTS quiz_sessions (
    session_id      INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT           NOT NULL,
    category_id     INT           NOT NULL,
    difficulty      ENUM('Easy', 'Medium', 'Hard') NOT NULL DEFAULT 'Medium',
    score           INT           NOT NULL DEFAULT 0,
    total_questions INT           NOT NULL DEFAULT 0,
    time_taken      INT           DEFAULT NULL,   -- seconds
    date_taken      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)     REFERENCES users(user_id)         ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------
-- 6. Quiz Answers (one row per question)
-- ------------------------------------------
CREATE TABLE IF NOT EXISTS quiz_answers (
    answer_id       INT AUTO_INCREMENT PRIMARY KEY,
    session_id      INT           NOT NULL,
    question_id     INT           NOT NULL,
    selected_answer VARCHAR(500)  DEFAULT NULL,
    is_correct      BOOLEAN       NOT NULL DEFAULT FALSE,
    FOREIGN KEY (session_id)  REFERENCES quiz_sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(question_id)    ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------
-- Seed: Default Categories
-- ------------------------------------------
INSERT IGNORE INTO categories (category_name, description, icon) VALUES
    ('Cybersecurity',       'Network security, ethical hacking, and cyber defense',           '🔒'),
    ('Programming',         'Coding concepts, algorithms, and data structures',               '💻'),
    ('AI & Machine Learning','Neural networks, deep learning, and intelligent systems',       '🤖'),
    ('Databases',           'SQL, NoSQL, database design and optimization',                   '🗄️'),
    ('Networking',          'TCP/IP, routing, switching, and network protocols',               '🌐'),
    ('General Knowledge',   'Science, history, geography, and current affairs',               '📖'),
    ('Technology',          'Latest tech trends, gadgets, and innovations',                   '⚡'),
    ('Web Development',     'HTML, CSS, JavaScript, and modern web frameworks',               '🕸️');

-- ------------------------------------------
-- Seed: Default Admin User
-- password = bcrypt hash of "admin123"
-- ------------------------------------------
INSERT IGNORE INTO users (name, email, password, role) VALUES
    ('Admin', 'admin@quizapp.com',
     '$2b$12$7rh2javPzVAY8dNAb8/GkuJSmhQ/F/yHNvXZ8doBC.KKx.To.0z0q',
     'admin');
