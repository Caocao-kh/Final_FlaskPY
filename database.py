import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')


def get_db_connection():
    """Establish and return a SQLite database connection with Row factory and foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables if not existing and seed default initial data if empty."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Users Table
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

        # 2. Category Table (Category 5pts)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                image VARCHAR(255),
                description TEXT
            )
        ''')

        # 3. Product Table (Product 5pts)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                thumbnail VARCHAR(255),
                Cost DECIMAL(10,2) DEFAULT 0.00,
                Price DECIMAL(10,2) DEFAULT 0.00,
                Stock INTEGER DEFAULT 0,
                CategoryId INTEGER NOT NULL,
                description TEXT,
                FOREIGN KEY (CategoryId) REFERENCES categories (id) ON DELETE CASCADE
            )
        ''')

        # 4. ProductImage Table (ProductImage 5pts)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ProductId INTEGER NOT NULL,
                name VARCHAR(255) NOT NULL,
                FOREIGN KEY (ProductId) REFERENCES products (id) ON DELETE CASCADE
            )
        ''')

        # Ensure default accounts always exist
        cursor.execute('SELECT id FROM users WHERE email = ? COLLATE NOCASE', ('admin@superman.com',))
        if not cursor.fetchone():
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

        cursor.execute('SELECT id FROM users WHERE email = ? COLLATE NOCASE', ('jane.smith@example.com',))
        if not cursor.fetchone():
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

        # Seed categories if empty
        cursor.execute('SELECT COUNT(*) as count FROM categories')
        cat_count = cursor.fetchone()['count']
        if cat_count == 0:
            default_categories = [
                (1, "Electronics", "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500", "State of the art audio, gadgets, and personal electronics."),
                (2, "Jewelery", "https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=500", "Fine handcrafted jewelry, bracelets, gold, and silver pieces."),
                (3, "Men's Clothing", "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=500", "Premium casual and formal wear, jackets, and everyday apparel."),
                (4, "Women's Clothing", "https://images.unsplash.com/photo-1525507119028-ed4c629a60a3?w=500", "Chic modern fashion, outerwear, casual tops, and dresses.")
            ]
            cursor.executemany('''
                INSERT INTO categories (id, name, image, description)
                VALUES (?, ?, ?, ?)
            ''', default_categories)

        # Seed products if empty (using initial items from fakeApi)
        cursor.execute('SELECT COUNT(*) as count FROM products')
        prod_count = cursor.fetchone()['count']
        if prod_count == 0:
            try:
                from fakeApi import data as fake_data
            except ImportError:
                fake_data = []

            cat_name_to_id = {
                "electronics": 1,
                "jewelery": 2,
                "men's clothing": 3,
                "women's clothing": 4
            }

            for p in fake_data:
                c_key = p.get('category', '').lower().strip()
                cat_id = cat_name_to_id.get(c_key, 1)
                cost = round(float(p.get('price', 0)) * 0.7, 2)
                price = round(float(p.get('price', 0)), 2)
                stock = 45 + (p.get('id', 1) * 3 % 50)
                cursor.execute('''
                    INSERT INTO products (id, name, thumbnail, Cost, Price, Stock, CategoryId, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    p.get('id'),
                    p.get('title', 'Product Item'),
                    p.get('image', ''),
                    cost,
                    price,
                    stock,
                    cat_id,
                    p.get('description', '')
                ))

                # Add a sample product image in product_images
                cursor.execute('''
                    INSERT INTO product_images (ProductId, name)
                    VALUES (?, ?)
                ''', (p.get('id'), p.get('image', '')))

        conn.commit()


# ==========================================
# USER CRUD FUNCTIONS (User [upload image])
# ==========================================

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


# ==========================================
# CATEGORY CRUD FUNCTIONS (Category 5pts)
# ==========================================

def get_all_categories():
    """Retrieve all categories."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.*, COUNT(p.id) as product_count
            FROM categories c
            LEFT JOIN products p ON c.id = p.CategoryId
            GROUP BY c.id
            ORDER BY c.name ASC
        ''')
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def get_category_by_id(category_id):
    """Retrieve category by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM categories WHERE id = ?', (category_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def create_category(name, image=None, description=None):
    """Insert a new category into the SQLite database."""
    if not image:
        image = "https://images.unsplash.com/photo-1526738549149-8e07eca6c147?w=500"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO categories (name, image, description)
            VALUES (?, ?, ?)
        ''', (name.strip(), image.strip() if image else '', description.strip() if description else ''))
        conn.commit()
        cat_id = cursor.lastrowid
        return get_category_by_id(cat_id)


def update_category(category_id, name=None, image=None, description=None):
    """Update a category in SQLite database."""
    current = get_category_by_id(category_id)
    if not current:
        return None

    updated_name = name.strip() if name is not None else current['name']
    updated_image = image.strip() if image is not None else current['image']
    updated_desc = description.strip() if description is not None else current['description']

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE categories
            SET name = ?, image = ?, description = ?
            WHERE id = ?
        ''', (updated_name, updated_image, updated_desc, category_id))
        conn.commit()
        return get_category_by_id(category_id)


def delete_category(category_id):
    """Delete a category by ID (cascades to products if FK enabled)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        conn.commit()
        return cursor.rowcount > 0


# ==========================================
# PRODUCT CRUD FUNCTIONS (Product 5pts)
# ==========================================

def _format_product_row(row, images=None):
    """Helper to convert product row to dict with exact schema and template compatibility aliases."""
    if not row:
        return None
    d = dict(row)
    # Exact requested schema keys
    cost_val = float(d.get('Cost', 0.0) or 0.0)
    price_val = float(d.get('Price', 0.0) or 0.0)
    stock_val = int(d.get('Stock', 0) or 0)
    cat_id = int(d.get('CategoryId', 1))

    # Compatibility aliases for legacy templates, cart, and telegram orders
    d['title'] = d.get('name', '')
    d['image'] = d.get('thumbnail', '')
    d['cost'] = cost_val
    d['price'] = price_val
    d['stock'] = stock_val
    d['category_id'] = cat_id
    d['category'] = d.get('category_name') or 'General'
    d['rating'] = {"rate": 4.5, "count": 28}
    d['images'] = images if images is not None else []
    return d


def get_all_products(category_id=None, search=None):
    """Retrieve all products with optional category and search filters."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = '''
            SELECT p.*, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.CategoryId = c.id
            WHERE 1=1
        '''
        params = []
        if category_id:
            query += ' AND p.CategoryId = ?'
            params.append(category_id)
        if search:
            query += ' AND (p.name LIKE ? OR p.description LIKE ? OR c.name LIKE ?)'
            term = f"%{search}%"
            params.extend([term, term, term])

        query += ' ORDER BY p.id DESC'
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [_format_product_row(r) for r in rows]


def get_product_by_id(product_id):
    """Retrieve a single product by ID including its additional images."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.CategoryId = c.id
            WHERE p.id = ?
        ''', (product_id,))
        row = cursor.fetchone()
        if not row:
            return None

        # Fetch product images
        cursor.execute('SELECT * FROM product_images WHERE ProductId = ?', (product_id,))
        img_rows = cursor.fetchall()
        images = [dict(ir) for ir in img_rows]
        return _format_product_row(row, images=images)


def create_product(name, thumbnail='', Cost=0.0, Price=0.0, Stock=0, CategoryId=1, description='', additional_images=None):
    """Insert a new product into the SQLite database."""
    if not thumbnail:
        thumbnail = "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO products (name, thumbnail, Cost, Price, Stock, CategoryId, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            name.strip(),
            thumbnail.strip() if thumbnail else '',
            float(Cost or 0.0),
            float(Price or 0.0),
            int(Stock or 0),
            int(CategoryId or 1),
            description.strip() if description else ''
        ))
        prod_id = cursor.lastrowid

        # Insert primary thumbnail as first product_image
        if thumbnail:
            cursor.execute('''
                INSERT INTO product_images (ProductId, name)
                VALUES (?, ?)
            ''', (prod_id, thumbnail.strip()))

        # Insert additional images if provided
        if additional_images and isinstance(additional_images, list):
            for img_url in additional_images:
                if img_url and img_url.strip():
                    cursor.execute('''
                        INSERT INTO product_images (ProductId, name)
                        VALUES (?, ?)
                    ''', (prod_id, img_url.strip()))

        conn.commit()
        return get_product_by_id(prod_id)


def update_product(product_id, name=None, thumbnail=None, Cost=None, Price=None, Stock=None, CategoryId=None, description=None):
    """Update an existing product in the SQLite database."""
    current = get_product_by_id(product_id)
    if not current:
        return None

    new_name = name.strip() if name is not None else current['name']
    new_thumbnail = thumbnail.strip() if thumbnail is not None else current['thumbnail']
    new_cost = float(Cost) if Cost is not None else current['Cost']
    new_price = float(Price) if Price is not None else current['Price']
    new_stock = int(Stock) if Stock is not None else current['Stock']
    new_cat_id = int(CategoryId) if CategoryId is not None else current['CategoryId']
    new_desc = description.strip() if description is not None else current['description']

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE products
            SET name = ?, thumbnail = ?, Cost = ?, Price = ?, Stock = ?, CategoryId = ?, description = ?
            WHERE id = ?
        ''', (new_name, new_thumbnail, new_cost, new_price, new_stock, new_cat_id, new_desc, product_id))
        conn.commit()
        return get_product_by_id(product_id)


def delete_product(product_id):
    """Delete a product by ID (cascades to product_images)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
        conn.commit()
        return cursor.rowcount > 0


# ==========================================
# PRODUCT IMAGE CRUD FUNCTIONS (ProductImage 5pts)
# ==========================================

def get_images_by_product_id(product_id):
    """Retrieve all gallery images for a specific product."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM product_images WHERE ProductId = ? ORDER BY id ASC', (product_id,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def get_product_image_by_id(image_id):
    """Retrieve single product image entry by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM product_images WHERE id = ?', (image_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def create_product_image(product_id, name):
    """Insert a new image record for a product."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO product_images (ProductId, name)
            VALUES (?, ?)
        ''', (int(product_id), name.strip()))
        conn.commit()
        img_id = cursor.lastrowid
        return get_product_image_by_id(img_id)


def delete_product_image(image_id):
    """Delete a product image by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM product_images WHERE id = ?', (image_id,))
        conn.commit()
        return cursor.rowcount > 0
