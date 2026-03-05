import psycopg2
from psycopg2.extras import RealDictCursor
import os

def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "nutrition_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASS", "yourpassword"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
        return conn
    except Exception as e:
        print(f"❌ Database Connection Error: {e}")
        return None

def init_db():
    """Run this once to create your table."""
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id SERIAL PRIMARY KEY,
                user_name VARCHAR(100) UNIQUE,
                height FLOAT,
                weight FLOAT,
                goal VARCHAR(50),
                diet_preference VARCHAR(50),
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Database Initialized")