
import os
import psycopg2

from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """Create a PostgreSQL connection."""
    try:
        return psycopg2.connect(
            dbname=os.getenv("DB_NAME", "nutrition_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASS", "yourpassword"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
        )
    except Exception as e:
        print(f"Database connection error: {e}")
        return None


def init_db():
    """Create or migrate the NutritionAI database tables."""
    conn = get_db_connection()

    if not conn:
        raise RuntimeError("Could not connect to PostgreSQL.")

    try:
        with conn.cursor() as cur:

            # 1. User profile and current nutrition targets
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id SERIAL PRIMARY KEY,
                    user_name VARCHAR(100) UNIQUE NOT NULL,
                    height FLOAT,
                    weight FLOAT,
                    goal VARCHAR(50),
                    diet_preference VARCHAR(50),
                    age SMALLINT,
                    gender VARCHAR(30),
                    daily_nutrition_targets JSONB NOT NULL DEFAULT '{}'::jsonb,
                    last_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Migrate an existing user_profiles table safely.
            cur.execute("""
                ALTER TABLE user_profiles
                ADD COLUMN IF NOT EXISTS age SMALLINT,
                ADD COLUMN IF NOT EXISTS gender VARCHAR(30),
                ADD COLUMN IF NOT EXISTS daily_nutrition_targets
                    JSONB NOT NULL DEFAULT '{}'::jsonb;
            """)

            # 2. Persistent food logs
            cur.execute("""
                CREATE TABLE IF NOT EXISTS food_logs (
                    id BIGSERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL
                        REFERENCES user_profiles(user_id)
                        ON DELETE CASCADE,
                    food_name TEXT NOT NULL,
                    quantity_g NUMERIC(10, 2) NOT NULL
                        CHECK (quantity_g > 0),
                    nutrients JSONB NOT NULL DEFAULT '{}'::jsonb,
                    source TEXT,
                    logged_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_food_logs_user_time
                ON food_logs (user_id, logged_at);
            """)

            # 3. Saved generated diet plans
            cur.execute("""
                CREATE TABLE IF NOT EXISTS diet_plans (
                    id BIGSERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL
                        REFERENCES user_profiles(user_id)
                        ON DELETE CASCADE,
                    plan_date DATE NOT NULL,
                    goal VARCHAR(50),
                    plan JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_diet_plans_user_date
                ON diet_plans (user_id, plan_date);
            """)

        conn.commit()
        print("NutritionAI database initialized successfully.")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_user_profile(user_name):
    """Retrieve a user's profile and current nutrition targets."""
    conn = get_db_connection()

    if not conn:
        return None

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT *
                FROM user_profiles
                WHERE user_name = %s;
            """, (user_name,))

            row = cur.fetchone()
            return dict(row) if row else None

    finally:
        conn.close()


def save_user_profile(
    user_name,
    height=None,
    weight=None,
    goal=None,
    diet_preference=None,
    age=None,
    gender=None,
    daily_nutrition_targets=None,
):
    """Insert or update a user's profile without overwriting
    existing values with missing information.
    """
    conn = get_db_connection()

    if not conn:
        raise RuntimeError("Could not connect to PostgreSQL.")

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_profiles (
                    user_name,
                    height,
                    weight,
                    goal,
                    diet_preference,
                    age,
                    gender,
                    daily_nutrition_targets
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_name)
                DO UPDATE SET
                    height = COALESCE(
                        EXCLUDED.height, user_profiles.height
                    ),
                    weight = COALESCE(
                        EXCLUDED.weight, user_profiles.weight
                    ),
                    goal = COALESCE(
                        EXCLUDED.goal, user_profiles.goal
                    ),
                    diet_preference = COALESCE(
                        EXCLUDED.diet_preference,
                        user_profiles.diet_preference
                    ),
                    age = COALESCE(
                        EXCLUDED.age, user_profiles.age
                    ),
                    gender = COALESCE(
                        EXCLUDED.gender, user_profiles.gender
                    ),
                    daily_nutrition_targets = CASE
                        WHEN %s THEN EXCLUDED.daily_nutrition_targets
                        ELSE user_profiles.daily_nutrition_targets
                    END,
                    last_updated = CURRENT_TIMESTAMP;
            """, (
                user_name,
                height,
                weight,
                goal,
                diet_preference,
                age,
                gender,
                Json(daily_nutrition_targets or {}),
                daily_nutrition_targets is not None,
            ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def save_food_log(
    user_id,
    food_name,
    quantity_g,
    nutrients,
    source="USDA",
):
    """Persist a food entry with its nutrients for the actual quantity."""
    conn = get_db_connection()

    if not conn:
        raise RuntimeError("Could not connect to PostgreSQL.")

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO food_logs (
                    user_id,
                    food_name,
                    quantity_g,
                    nutrients,
                    source
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *;
            """, (
                user_id,
                food_name,
                quantity_g,
                Json(nutrients),
                source,
            ))

            row = dict(cur.fetchone())

        conn.commit()
        return row

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_food_logs_for_date(user_id, target_date, timezone="Asia/Kolkata"):
    """Retrieve a user's food entries for a date in their local timezone."""
    conn = get_db_connection()

    if not conn:
        raise RuntimeError("Could not connect to PostgreSQL.")

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT *
                FROM food_logs
                WHERE user_id = %s
                  AND (logged_at AT TIME ZONE %s)::date = %s
                ORDER BY logged_at;
            """, (user_id, timezone, target_date))

            return [dict(row) for row in cur.fetchall()]

    finally:
        conn.close()


def update_nutrition_targets(user_id, targets):
    """Update the current daily targets stored in the user's profile."""
    conn = get_db_connection()

    if not conn:
        raise RuntimeError("Could not connect to PostgreSQL.")

    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE user_profiles
                SET daily_nutrition_targets = %s,
                    last_updated = CURRENT_TIMESTAMP
                WHERE user_id = %s;
            """, (Json(targets), user_id))

            if cur.rowcount == 0:
                raise ValueError(f"User ID {user_id} was not found.")

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def save_diet_plan(user_id, plan_date, goal, plan):
    """Save a generated diet plan as JSONB."""
    conn = get_db_connection()

    if not conn:
        raise RuntimeError("Could not connect to PostgreSQL.")

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO diet_plans (
                    user_id,
                    plan_date,
                    goal,
                    plan
                )
                VALUES (%s, %s, %s, %s)
                RETURNING *;
            """, (user_id, plan_date, goal, Json(plan)))

            row = dict(cur.fetchone())

        conn.commit()
        return row

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
