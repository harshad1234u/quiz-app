"""
Database Initialization Script (Supabase)

This script is NO LONGER needed for Supabase deployment.
The schema should be run directly in the Supabase SQL Editor.

See: database/schema.sql

This file is kept for reference and local development only.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def init_database():
    """
    For Supabase, run database/schema.sql in the Supabase SQL Editor.

    Steps:
      1. Go to your Supabase project dashboard
      2. Navigate to SQL Editor
      3. Paste the contents of database/schema.sql
      4. Click "Run"

    The schema creates all tables, indexes, RLS policies,
    seed categories, and the default admin user.
    """
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')

    print("=" * 60)
    print("  Supabase Database Initialization")
    print("=" * 60)
    print()
    print("  For Supabase, run the schema SQL directly:")
    print()
    print(f"  1. Open: {schema_path}")
    print("  2. Copy the entire contents")
    print("  3. Go to: Supabase Dashboard → SQL Editor")
    print("  4. Paste and click 'Run'")
    print()
    print("  The script will create:")
    print("    ✓ users, user_interests, categories tables")
    print("    ✓ questions (with JSONB options), quiz_sessions, quiz_answers")
    print("    ✓ RLS policies (open for app-managed auth)")
    print("    ✓ Default categories (8 topics)")
    print("    ✓ Default admin: admin@quizapp.com / admin123")
    print()
    print("  Connection details needed in .streamlit/secrets.toml:")
    print("    SUPABASE_URL = 'https://<project-id>.supabase.co'")
    print("    SUPABASE_KEY = '<anon-public-key>'")
    print()
    print("  Find these at: Supabase Dashboard → Settings → API")
    print("=" * 60)


if __name__ == '__main__':
    init_database()
