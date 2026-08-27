from flask import Flask, render_template, abort, request, make_response, redirect, url_for, flash, send_from_directory, session
import json
import requests
import os
import uuid
from functools import wraps
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from fakeApi import data
from database import (
    init_db,
    get_user_by_email,
    get_user_by_id,
    get_all_users,
    create_user as db_create_user,
    update_user as db_update_user,
    delete_user as db_delete_user
)

app: Flask = Flask(__name__)
app.secret_key = 'superman_admin_secret_key_2026'
app.permanent_session_lifetime = timedelta(days=7)

# Initialize SQLite database
init_db()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id') or session.get('user_role') != 'Admin':
            flash("Please log in with an Administrator account to access the Admin Console.", "warning")
            next_param = request.full_path if request.query_string else request.path
            return redirect(url_for('admin_login', next=next_param))
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash("Please sign in to access your account.", "warning")
            next_param = request.full_path if request.query_string else request.path
            return redirect(url_for('login', next=next_param))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/favicon.ico')
def favicon():
    return '', 204

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def save_uploaded_image(file_key='image_file', text_url_key='image', default_val=''):
    file = request.files.get(file_key)
    if file and file.filename and file.filename.strip():
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex[:8]}_{filename}"
        save_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(save_path)
        return url_for('static', filename=f'uploads/{unique_filename}')
    
    url_val = request.form.get(text_url_key, '').strip()
    if url_val:
        return url_val
    return default_val


TELEGRAM_TOKEN_BOT = '8494492410:AAGWmIXOpMJVFvBNMaCXpZ6EBylhKMeapuI'
TELEGRAM_ID_CHAT = '-1003771965525'

# Global in-memory orders log
orders_log = [
    {
        "id": 1001,
        "customer_name": "John Doe",
        "email": "john@example.com",
        "phone": "+1 555-0192",
        "address": "742 Evergreen Terrace",
        "city": "Springfield",
        "items": [
            {"title": "Fjallraven - Foldsack No. 1 Backpack", "quantity": 1, "price": 109.95},
            {"title": "Mens Casual Slim Fit", "quantity": 2, "price": 15.99}
        ],
        "total_amount": 141.93,
        "timestamp": "2026-07-28 14:30",
        "status": "Completed"
    },
    {
        "id": 1002,
        "customer_name": "Sarah Connor",
        "email": "sarah@cyberdyne.com",
        "phone": "+1 555-0847",
        "address": "1200 Market Street",
        "city": "Los Angeles",
        "items": [
            {"title": "John Hardy Women's Dragon Bracelet", "quantity": 1, "price": 695.00}
        ],
        "total_amount": 695.00,
        "timestamp": "2026-07-30 09:15",
        "status": "Processing"
    },
    {
        "id": 1003,
        "customer_name": "Alex Mercer",
        "email": "alex@prototype.org",
        "phone": "+1 555-9482",
        "address": "450 5th Avenue",
        "city": "New York",
        "items": [
            {"title": "Mens Cotton Jacket", "quantity": 1, "price": 55.99}
        ],
        "total_amount": 55.99,
        "timestamp": "2026-08-01 08:40",
        "status": "Pending"
    }
]


@app.get('/')
def home():
    return render_template('front/index.html', products=data)


@app.get('/products')
def products():
    categories = sorted(list(set(p["category"] for p in data if "category" in p)))
    selected_category = request.args.get('category', '').strip().lower()
    search_query = request.args.get('q', '').strip()
    return render_template(
        'front/products.html',
        products=data,
        categories=categories,
        selected_category=selected_category,
        search_query=search_query,
        current_page='products'
    )


@app.get('/product/<int:product_id>')
def product(product_id):
    product_detail = next((p for p in data if p["id"] == product_id), None)

    if product_detail is None:
        abort(404)

    similar_products = [
        p for p in data
        if p["category"] == product_detail["category"] and p["id"] != product_detail["id"]
    ]
    similar_products = similar_products[:4]

    return render_template(
        'front/product.html',
        product=product_detail,
        related_products=similar_products
    )


@app.post('/add-to-cart/<int:product_id>')
def add_to_cart(product_id):
    existing_cart_cookie = request.cookies.get('shopping_cart')
    cart_list = []

    if existing_cart_cookie:
        try:
            cart_list = json.loads(existing_cart_cookie)
            # Safe-check: If the cookie format is outdated, reset it
            if cart_list and not isinstance(cart_list[0], dict):
                cart_list = []
        except json.JSONDecodeError:
            cart_list = []

    try:
        input_qty = int(request.form.get('quantity', 1))
    except (ValueError, TypeError):
        input_qty = 1

    product_exists = False
    for item in cart_list:
        if isinstance(item, dict) and item.get("id") == product_id:
            item["qty"] += input_qty
            product_exists = True
            break

    if not product_exists:
        cart_list.append({"id": product_id, "qty": input_qty})

    is_buy_now = request.form.get('action') == 'buy_now'
    target_url = url_for('checkout') if is_buy_now else url_for('cart')
    response = make_response(redirect(target_url))

    response.set_cookie('shopping_cart', json.dumps(cart_list), max_age=2592000, httponly=True)
    return response


@app.get('/cart')
def cart():
    cart_cookie = request.cookies.get('shopping_cart')
    cart_items = []
    subtotal = 0.0

    if cart_cookie:
        try:
            cookie_data = json.loads(cart_cookie)

            # FIX: If the data array structure is an old list format, ignore it
            if isinstance(cookie_data, list):
                for cookie_item in cookie_data:
                    # Double-check that the item is a dictionary to prevent crashes
                    if isinstance(cookie_item, dict):
                        product_lookup = next((p for p in data if p["id"] == cookie_item.get("id")), None)
                        if product_lookup:
                            item_copy = product_lookup.copy()
                            item_copy["quantity"] = cookie_item.get("qty", 1)

                            cart_items.append(item_copy)
                            subtotal += item_copy['price'] * item_copy['quantity']
        except json.JSONDecodeError:
            pass

    return render_template('front/cart.html', cart_items=cart_items, subtotal=subtotal, total=subtotal)


@app.post('/update-quantity-nojs/<int:product_id>')
def update_quantity_nojs(product_id):
    cart_cookie = request.cookies.get('shopping_cart')
    cart_list = []

    if cart_cookie:
        try:
            cart_list = json.loads(cart_cookie)
        except json.JSONDecodeError:
            pass

    # Read the data natively from the form submission payload
    change_direction = request.form.get('direction')  # Captures 'up' or 'down'

    for item in cart_list:
        if isinstance(item, dict) and item.get("id") == product_id:
            if change_direction == 'up':
                item["qty"] += 1
            elif change_direction == 'down' and item["qty"] > 1:
                item["qty"] -= 1
            break

    # Build response redirect back to the cart page
    response = make_response(redirect(url_for('cart')))

    # Save the updated cart state back inside browser cookie memory
    response.set_cookie('shopping_cart', json.dumps(cart_list), max_age=2592000, httponly=True)
    return response


@app.get('/remove-from-cart/<int:product_id>')
def remove_from_cart(product_id):
    cart_cookie = request.cookies.get('shopping_cart')
    cart_list = []

    if cart_cookie:
        try:
            cart_list = json.loads(cart_cookie)
        except json.JSONDecodeError:
            pass

    # Rebuild the list, filtering out the item matching our target product_id
    updated_cart = [
        item for item in cart_list
        if isinstance(item, dict) and item.get("id") != product_id
    ]

    # Build a native redirect response back to your main cart page view
    response = make_response(redirect(url_for('cart')))

    # Update the browser cookie with our newly trimmed array string
    response.set_cookie('shopping_cart', json.dumps(updated_cart), max_age=2592000, httponly=True)
    return response

@app.get('/checkout')
def checkout():
    cart_cookie = request.cookies.get('shopping_cart')
    cart_items = []
    subtotal = 0.0

    if cart_cookie:
        try:
            cookie_data = json.loads(cart_cookie)

            # FIX: Double-check that the item is a dictionary to prevent crashes
            if isinstance(cookie_data, list):
                for cookie_item in cookie_data:
                    if isinstance(cookie_item, dict):
                        product_lookup = next((p for p in data if p["id"] == cookie_item.get("id")), None)
                        if product_lookup:
                            item_copy = product_lookup.copy()
                            item_copy["quantity"] = cookie_item.get("qty", 1)
                            cart_items.append(item_copy)
                            subtotal += item_copy['price'] * item_copy['quantity']
        except json.JSONDecodeError:
            pass

    return render_template('front/checkout.html', cart_items=cart_items, subtotal=subtotal, total=subtotal)


@app.route('/telegram_order', methods=['POST'])
def telegram_order():
    cart_cookie = request.cookies.get('shopping_cart')
    cart_items = []
    subtotal = 0.0

    if cart_cookie:
        try:
            cookie_data = json.loads(cart_cookie)
            if isinstance(cookie_data, list):
                for cookie_item in cookie_data:
                    if isinstance(cookie_item, dict):
                        product_lookup = next((p for p in data if p["id"] == cookie_item.get("id")), None)
                        if product_lookup:
                            item_copy = product_lookup.copy()
                            item_copy["quantity"] = cookie_item.get("qty", 1)
                            cart_items.append(item_copy)
                            subtotal += item_copy['price'] * item_copy['quantity']
        except json.JSONDecodeError:
            pass

    if not cart_items:
        return redirect(url_for('cart'))

    username = request.form.get('username', 'N/A')
    address = request.form.get('address', 'N/A')
    city = request.form.get('city', 'N/A')
    phone = request.form.get('phone', 'N/A')
    email = request.form.get('email', 'N/A')

    # Record order into internal orders_log for admin view
    new_order_id = 1000 + len(orders_log) + 1
    orders_log.insert(0, {
        "id": new_order_id,
        "customer_name": username,
        "email": email,
        "phone": phone,
        "address": address,
        "city": city,
        "items": cart_items,
        "total_amount": subtotal,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status": "Pending"
    })

    # Build text message for Telegram
    message = "🛍️ **NEW ORDER RECEIVED** 🛍️\n\n"
    message += "👤 **Customer Information:**\n"
    message += f"- **Name:** {username}\n"
    message += f"- **Email:** {email}\n"
    message += f"- **Phone:** {phone}\n"
    message += f"- **Address:** {address}\n"
    message += f"- **City:** {city}\n\n"
    message += "📦 **Items:**\n"
    
    for item in cart_items:
        item_total = item['price'] * item['quantity']
        message += f"- {item['title']} (x{item['quantity']}) — ${item_total:.2f}\n"
    
    message += f"\n💰 **Total Amount:** ${subtotal:.2f}"

    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN_BOT}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_ID_CHAT,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        telegram_response = requests.post(telegram_url, json=payload)
        telegram_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Telegram API Error: {e}")

    response = make_response(redirect(url_for('cart', order_success=1)))
    response.delete_cookie('shopping_cart')
    return response


@app.get('/account')
@login_required
def account():
    user = get_user_by_id(session.get('user_id')) if session.get('user_id') else None
    return render_template('front/account.html', user=user)


@app.get('/forget-password')
def forget_password():
    return render_template('front/forget-password.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        order_ref = request.form.get('order_ref', '').strip()
        subject = request.form.get('subject', '').strip()
        message_text = request.form.get('message', '').strip()

        # Build notification for Telegram if configured
        tg_text = f"📩 **NEW CONTACT INQUIRY**\n\n"
        tg_text += f"👤 **Name:** {name}\n"
        tg_text += f"✉️ **Email:** {email}\n"
        if order_ref:
            tg_text += f"🔖 **Order Ref:** {order_ref}\n"
        tg_text += f"📌 **Subject:** {subject}\n"
        tg_text += f"💬 **Message:**\n{message_text}"

        try:
            telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN_BOT}/sendMessage"
            requests.post(telegram_url, json={
                "chat_id": TELEGRAM_ID_CHAT,
                "text": tg_text,
                "parse_mode": "Markdown"
            }, timeout=3)
        except Exception as e:
            print(f"Telegram contact notification error: {e}")

        flash("Thank you! Your message has been received. Our support team will contact you within 24 hours.", "success")
        return render_template('front/contact.html', current_page='contact', submitted=True)

    return render_template('front/contact.html', current_page='contact')


# ==============================================================================
# AUTHENTICATION ROUTES (ADMIN & STOREFRONT)
# ==============================================================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    # If already logged in as Admin, redirect directly to dashboard
    if session.get('user_id') and session.get('user_role') == 'Admin':
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        remember = bool(request.form.get('remember'))

        # Find matching user from database
        user = get_user_by_email(email)

        if not user or user.get('password') != password:
            flash("Invalid administrator email or password.", "error")
            return render_template('admin/login.html')

        if user.get('role') != 'Admin':
            flash("Access Denied: Only Administrator accounts can log in here.", "warning")
            return render_template('admin/login.html')

        # Successful Admin Authentication
        session.permanent = remember
        session['user_id'] = user['id']
        session['user_name'] = user.get('name', 'Admin User')
        session['user_email'] = user.get('email', '')
        session['user_role'] = user.get('role', 'Admin')
        session['user_image'] = user.get('image', '')
        session['user'] = user.get('name', 'Admin User')

        flash(f"Welcome back, {user.get('name', 'Admin')}!", "success")

        next_url = request.args.get('next')
        if next_url and next_url.startswith('/') and not next_url.startswith('//'):
            return redirect(next_url)
        return redirect(url_for('admin_dashboard'))

    return render_template('admin/login.html')


@app.route('/admin/logout', methods=['GET', 'POST'])
def admin_logout():
    user_name = session.get('user_name', 'Admin')
    session.clear()
    flash(f"Goodbye {user_name}, you have been securely logged out.", "info")
    return redirect(url_for('admin_login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        remember = bool(request.form.get('remember'))

        user = get_user_by_email(email)

        if not user or user.get('password') != password:
            flash("Invalid email or password.", "error")
            return render_template('front/login.html')

        session.permanent = remember
        session['user_id'] = user['id']
        session['user_name'] = user.get('name', 'User')
        session['user_email'] = user.get('email', '')
        session['user_role'] = user.get('role', 'User')
        session['user_image'] = user.get('image', '')
        session['user'] = user.get('name', 'User')

        flash(f"Welcome back, {user.get('name', 'User')}!", "success")

        if user.get('role') == 'Admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('account'))

    if session.get('user_id'):
        if session.get('user_role') == 'Admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('account'))

    return render_template('front/login.html')


@app.route('/create_user', methods=['GET', 'POST'])
def create_user():
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        name = f"{first_name} {last_name}".strip() or "Customer"
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "error")
            return render_template('front/create-user.html')

        existing_user = get_user_by_email(email)
        if existing_user:
            flash("An account with this email already exists. Please log in.", "warning")
            return redirect(url_for('login'))

        default_avatar = f"https://api.dicebear.com/7.x/bottts/svg?seed={name}"
        new_user = db_create_user(
            name=name,
            email=email,
            password=password,
            image=default_avatar,
            role='User'
        )

        session['user_id'] = new_user['id']
        session['user_name'] = new_user['name']
        session['user_email'] = new_user['email']
        session['user_role'] = new_user['role']
        session['user_image'] = new_user['image']
        session['user'] = new_user['name']

        flash("Account created successfully! Welcome to Superman Electronics.", "success")
        return redirect(url_for('account'))

    return render_template('front/create-user.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for('home'))


# ==============================================================================
# ADMIN DASHBOARD & MANAGEMENT ROUTES (PROTECTED)
# ==============================================================================

@app.get('/home/dashborad')
@app.get('/admin/dashborad')
@app.get('/dashboard')
@app.get('/admin/dashboard')
@app.get('/admin')
@admin_required
def admin_dashboard():
    total_products = len(data)
    total_revenue = sum(o.get('total_amount', 0) for o in orders_log) + sum(p.get('price', 0) * 10 for p in data)
    total_orders = len(orders_log)

    ratings = [p['rating']['rate'] for p in data if isinstance(p.get('rating'), dict) and 'rate' in p['rating']]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

    category_counts = {}
    for p in data:
        cat = p.get('category', 'uncategorized')
        category_counts[cat] = category_counts.get(cat, 0) + 1

    top_products = sorted(data, key=lambda x: x.get('rating', {}).get('rate', 0) if isinstance(x.get('rating'), dict) else 0, reverse=True)[:5]
    recent_orders = orders_log[:5]

    stats = {
        "total_products": total_products,
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "avg_rating": avg_rating
    }

    return render_template(
        'admin/dashboard.html',
        active_page='dashboard',
        stats=stats,
        category_counts=category_counts,
        top_products=top_products,
        recent_orders=recent_orders
    )


@app.get('/admin/products')
@admin_required
def admin_products():
    categories = sorted(list(set(p.get('category', '') for p in data if p.get('category'))))
    return render_template('admin/products.html', active_page='products', products=data, categories=categories)


@app.post('/admin/product/add')
@admin_required
def admin_add_product():
    try:
        title = request.form.get('title')
        price = float(request.form.get('price', 0))
        category = request.form.get('category')
        description = request.form.get('description')
        image = save_uploaded_image('image_file', 'image', 'https://via.placeholder.com/200')

        max_id = max((p.get('id', 0) for p in data), default=0)
        new_product = {
            "id": max_id + 1,
            "title": title,
            "price": price,
            "category": category,
            "image": image,
            "description": description,
            "rating": {"rate": 5.0, "count": 1}
        }
        data.insert(0, new_product)
        flash(f"Product '{title}' created successfully!", "success")
    except Exception as e:
        flash(f"Error adding product: {str(e)}", "error")

    return redirect(url_for('admin_products'))


@app.post('/admin/product/edit/<int:product_id>')
@admin_required
def admin_edit_product(product_id):
    product_item = next((p for p in data if p["id"] == product_id), None)
    if not product_item:
        flash("Product not found", "error")
        return redirect(url_for('admin_products'))

    try:
        product_item['title'] = request.form.get('title', product_item['title'])
        product_item['price'] = float(request.form.get('price', product_item['price']))
        product_item['category'] = request.form.get('category', product_item['category'])
        product_item['description'] = request.form.get('description', product_item['description'])

        new_image = save_uploaded_image('image_file', 'image', product_item.get('image', ''))
        if new_image:
            product_item['image'] = new_image

        flash(f"Product '{product_item['title']}' updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating product: {str(e)}", "error")

    return redirect(url_for('admin_products'))


@app.route('/admin/product/delete/<int:product_id>', methods=['POST', 'GET'])
@admin_required
def admin_delete_product(product_id):
    global data
    product_item = next((p for p in data if p["id"] == product_id), None)
    if product_item:
        data.remove(product_item)
        flash(f"Product #{product_id} deleted successfully!", "success")
    else:
        flash("Product not found", "error")
    return redirect(url_for('admin_products'))


@app.get('/admin/orders')
@admin_required
def admin_orders():
    return render_template('admin/orders.html', active_page='orders', orders=orders_log)


@app.get('/admin/users')
@admin_required
def admin_users():
    users_list = get_all_users()
    return render_template('admin/users.html', active_page='users', users=users_list)


@app.route('/admin/user/add', methods=['GET', 'POST'])
@admin_required
def admin_add_user():
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '').strip()
            role = request.form.get('role', 'User')

            if get_user_by_email(email):
                flash("A user account with this email already exists.", "warning")
                return render_template('admin/add_user.html', active_page='users')

            default_avatar = f"https://api.dicebear.com/7.x/bottts/svg?seed={name}"
            image = save_uploaded_image('image_file', 'image', default_avatar)

            db_create_user(name=name, email=email, password=password, image=image, role=role)
            flash(f"User '{name}' created successfully!", "success")
            return redirect(url_for('admin_users'))
        except Exception as e:
            flash(f"Error adding user: {str(e)}", "error")

    return render_template('admin/add_user.html', active_page='users')


@app.route('/admin/user/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_user(user_id):
    user_item = get_user_by_id(user_id)
    if not user_item:
        flash("User not found", "error")
        return redirect(url_for('admin_users'))

    if request.method == 'POST':
        try:
            name = request.form.get('name', user_item['name']).strip()
            email = request.form.get('email', user_item['email']).strip().lower()
            password = request.form.get('password', '').strip()
            role = request.form.get('role', user_item['role'])

            existing = get_user_by_email(email)
            if existing and existing['id'] != user_id:
                flash("Another user account with this email already exists.", "warning")
                return render_template('admin/edit_user.html', active_page='users', user=user_item)

            new_image = save_uploaded_image('image_file', 'image', user_item.get('image', ''))
            image = new_image if new_image else user_item.get('image', '')

            db_update_user(user_id=user_id, name=name, email=email, password=password, image=image, role=role)
            flash(f"User '{name}' updated successfully!", "success")
            return redirect(url_for('admin_users'))
        except Exception as e:
            flash(f"Error updating user: {str(e)}", "error")

    return render_template('admin/edit_user.html', active_page='users', user=user_item)


@app.route('/admin/user/delete/<int:user_id>', methods=['POST', 'GET'])
@admin_required
def admin_delete_user(user_id):
    success = db_delete_user(user_id)
    if success:
        flash(f"User #{user_id} deleted successfully!", "success")
    else:
        flash("User not found", "error")
    return redirect(url_for('admin_users'))


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=True)


    