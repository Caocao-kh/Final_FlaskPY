import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')


def get_db_connection():
    """Establish and return a SQLite database connection with Row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if not existing and seed default initial accounts if empty."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL COLLATE NOCASE,
                password TEXT NOT NULL,
                image TEXT,
                role TEXT DEFAULT 'User',
                created_at TEXT NOT NULL
            )
        ''')

        # Seed initial accounts if database has no users
        cursor.execute('SELECT COUNT(*) as count FROM users')
        row = cursor.fetchone()
        if row and row['count'] == 0:
            cursor.execute('''
                INSERT INTO users (id, name, email, password, image, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                1,
                'Admin User',
                'admin@superman.com',
                'adminpassword123',
                'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150',
                'Admin',
                '2026-01-15 10:00'
            ))
            cursor.execute('''
                INSERT INTO users (id, name, email, password, image, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                2,
                'Jane Smith',
                'jane.smith@example.com',
                'janesmithpass!#',
                'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150',
                'User',
                '2026-03-22 14:15'
            ))
        conn.commit()


def get_user_by_email(email):
    """Fetch a single user by email address (case-insensitive)."""
    if not email:
        return None
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ? COLLATE NOCASE', (email.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id):
    """Fetch a single user by user ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_users():
    """Retrieve all users ordered by newest first."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users ORDER BY id DESC')
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def create_user(name, email, password, image=None, role='User', created_at=None):
    """Insert a new user account into the SQLite database and return user dictionary."""
    if not created_at:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    if not image:
        image = f"https://api.dicebear.com/7.x/bottts/svg?seed={name}"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (name, email, password, image, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name.strip(), email.strip().lower(), password, image, role, created_at))
        conn.commit()
        user_id = cursor.lastrowid
        return get_user_by_id(user_id)


def update_user(user_id, name=None, email=None, password=None, image=None, role=None):
    """Update user information in SQLite database."""
    current_user = get_user_by_id(user_id)
    if not current_user:
        return None

    updated_name = name if name is not None else current_user['name']
    updated_email = email.strip().lower() if email is not None else current_user['email']
    updated_password = password if password is not None and password.strip() else current_user['password']
    updated_image = image if image is not None and image.strip() else current_user['image']
    updated_role = role if role is not None else current_user['role']

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users
            SET name = ?, email = ?, password = ?, image = ?, role = ?
            WHERE id = ?
        ''', (updated_name, updated_email, updated_password, updated_image, updated_role, user_id))
        conn.commit()
        return get_user_by_id(user_id)


def delete_user(user_id):
    """Delete a user account by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        return cursor.rowcount > 0
