"""
Database Initialization Script
Reads schema.sql and executes it against the MySQL server.
Generates the admin password hash at runtime to ensure it always works.
"""
import os
import sys
import bcrypt
import mysql.connector
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))


def _validate_env():
    """Check that required environment variables are set."""
    required = {
        "MYSQL_HOST": "MySQL server host",
        "MYSQL_USER": "MySQL username",
        "MYSQL_PASSWORD": "MySQL password",
    }
    missing = []
    for var, desc in required.items():
        val = os.getenv(var, "").strip()
        if not val:
            missing.append(f"  {var} – {desc}")
    if missing:
        print("[ERROR] Missing required environment variables in .env:")
        for m in missing:
            print(m)
        print("\nCopy .env.example to .env and fill in the values.")
        return False
    return True


def init_database():
    """Create database and tables from schema.sql, then ensure admin user exists."""
    if not _validate_env():
        return False

    try:
        conn = mysql.connector.connect(
            host=os.getenv('MYSQL_HOST', 'localhost'),
            port=int(os.getenv('MYSQL_PORT', 3306)),
            user=os.getenv('MYSQL_USER', 'root'),
            password=os.getenv('MYSQL_PASSWORD', ''),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        cursor = conn.cursor()

        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')
        with open(schema_path, 'r', encoding='utf-8') as f:
            sql = f.read()

        # Execute each statement separately
        for statement in sql.split(';'):
            statement = statement.strip()
            if statement:
                try:
                    cursor.execute(statement)
                except mysql.connector.Error as e:
                    # Skip duplicate / already-exists errors
                    if e.errno not in (1007, 1050, 1061, 1062):
                        print(f"  Warning: {e.msg}")

        conn.commit()

        # ── Ensure admin user has a valid bcrypt hash ─────────────────────────
        # Generate hash at runtime so it's always correct
        admin_password = "admin123"
        admin_hash = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        cursor.execute("SELECT user_id, password FROM users WHERE email = %s", ("admin@quizapp.com",))
        row = cursor.fetchone()
        if row:
            # Update the password to a freshly-generated hash
            cursor.execute(
                "UPDATE users SET password = %s WHERE email = %s",
                (admin_hash, "admin@quizapp.com")
            )
            print("  [OK] Admin password hash refreshed")
        else:
            cursor.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, 'admin')",
                ("Admin", "admin@quizapp.com", admin_hash)
            )
            print("  [OK] Admin user created")

        conn.commit()
        cursor.close()
        conn.close()

        print("[SUCCESS] Database initialized successfully!")
        print("   Database: quiz_app")
        print("   Default admin: admin@quizapp.com / admin123")
        return True

    except mysql.connector.Error as e:
        print(f"[ERROR] MySQL Error: {e}")
        print("   Make sure your MySQL server is running and .env credentials are correct.")
        return False


if __name__ == '__main__':
    init_database()
