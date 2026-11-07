from flask import Flask, Blueprint, render_template, abort, request, make_response, redirect, url_for, flash, session, jsonify
from flask_wtf.csrf import CSRFError
from flask_cors import CORS
import json
import requests
import os
from datetime import datetime, timedelta

# Import extensions & shared utilities
from extensions import csrf, limiter
from utils import save_uploaded_image, orders_log, TELEGRAM_TOKEN_BOT, TELEGRAM_ID_CHAT

# Database operations
from database import (
    init_db,
    # Users
    get_user_by_email,
    get_user_by_id,
    get_all_users,
    create_user as db_create_user,
    update_user as db_update_user,
    delete_user as db_delete_user,
    # Categories (Category 5pts)
    get_all_categories,
    get_category_by_id,
    create_category as db_create_category,
    update_category as db_update_category,
    delete_category as db_delete_category,
    # Products (Product 5pts)
    get_all_products,
    get_product_by_id,
    create_product as db_create_product,
    update_product as db_update_product,
    delete_product as db_delete_product,
    # Product Images (ProductImage 5pts)
    get_images_by_product_id,
    get_product_image_by_id,
    create_product_image as db_create_product_image,
    delete_product_image as db_delete_product_image
)

# Import Admin blueprint and authentication decorator from admin folder
from admin import admin_bp, admin_required

app: Flask = Flask(__name__)
app.secret_key = 'superman_admin_secret_key_2026'
app.permanent_session_lifetime = timedelta(days=7)

# Initialize SQLite database
init_db()

# Initialize extensions
csrf.init_app(app)
limiter.init_app(app)

# Register Admin Blueprint from admin folder
app.register_blueprint(admin_bp)

# Maintain backwards compatibility with url_for('admin_xxx') across existing templates
for rule in list(app.url_map.iter_rules()):
    if rule.endpoint.startswith('admin.'):
        short_endpoint = rule.endpoint.split('.', 1)[1]
        if short_endpoint not in app.view_functions:
            app.add_url_rule(rule.rule, endpoint=short_endpoint, view_func=app.view_functions[rule.endpoint], methods=rule.methods)

# ==============================================================================
# CSRF ERROR HANDLER (CSRF: admin, front)
# ==============================================================================
@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    if request.path.startswith('/api/'):
        return jsonify({"error": "CSRF verification failed", "message": e.description}), 400
    flash(f"Security Notice: Session expired or invalid CSRF token. Please try again.", "error")
    return redirect(request.referrer or url_for('home'))

# ==============================================================================
# RATE LIMITER ERROR HANDLER (Limiter: admin, front)
# ==============================================================================
@app.errorhandler(429)
def ratelimit_handler(e):
    if request.path.startswith('/api/'):
        return jsonify({"error": "Rate limit exceeded", "message": str(e.description)}), 429
    flash("Too many requests sent in a short period. Please slow down and try again.", "warning")
    return make_response(render_template('front/index.html', products=get_all_products(), error_message="Rate limit exceeded"), 429)

# ==============================================================================
# CORS & CORE REST API (core / cors: api)
# ==============================================================================
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

api_bp = Blueprint('api', __name__, url_prefix='/api')
# Exempt REST API from form-based CSRF checks
csrf.exempt(api_bp)

# --- Category API ---
@api_bp.get('/categories')
def api_get_categories():
    categories = get_all_categories()
    return jsonify(categories), 200

@api_bp.get('/categories/<int:category_id>')
def api_get_category(category_id):
    cat = get_category_by_id(category_id)
    if not cat:
        return jsonify({"error": "Category not found"}), 404
    products = get_all_products(category_id=category_id)
    cat_dict = dict(cat)
    cat_dict['products'] = products
    return jsonify(cat_dict), 200

@api_bp.post('/categories')
def api_create_category():
    data = request.get_json(silent=True) or request.form
    name = data.get('name')
    if not name:
        return jsonify({"error": "Name is required"}), 400
    image = save_uploaded_image('image_file', 'image', data.get('image', ''))
    description = data.get('description', '')
    cat = db_create_category(name=name, image=image, description=description)
    return jsonify(cat), 201

@api_bp.put('/categories/<int:category_id>')
def api_update_category(category_id):
    data = request.get_json(silent=True) or request.form
    cat = get_category_by_id(category_id)
    if not cat:
        return jsonify({"error": "Category not found"}), 404
    name = data.get('name')
    image = data.get('image')
    description = data.get('description')
    updated = db_update_category(category_id, name=name, image=image, description=description)
    return jsonify(updated), 200

@api_bp.delete('/categories/<int:category_id>')
def api_delete_category(category_id):
    success = db_delete_category(category_id)
    if not success:
        return jsonify({"error": "Category not found"}), 404
    return jsonify({"message": f"Category #{category_id} deleted successfully"}), 200

# --- Product API ---
@api_bp.get('/products')
def api_get_products():
    category_id = request.args.get('category_id', type=int)
    search = request.args.get('search') or request.args.get('q')
    products = get_all_products(category_id=category_id, search=search)
    return jsonify(products), 200

@api_bp.get('/products/<int:product_id>')
def api_get_product(product_id):
    product = get_product_by_id(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    return jsonify(product), 200

@api_bp.post('/products')
def api_create_product():
    data = request.get_json(silent=True) or request.form
    name = data.get('name') or data.get('title')
    if not name:
        return jsonify({"error": "Product name is required"}), 400
    thumbnail = save_uploaded_image('thumbnail_file', 'thumbnail', data.get('thumbnail') or data.get('image') or '')
    cost = float(data.get('Cost') or data.get('cost') or 0.0)
    price = float(data.get('Price') or data.get('price') or 0.0)
    stock = int(data.get('Stock') or data.get('stock') or 0)
    category_id = int(data.get('CategoryId') or data.get('category_id') or 1)
    description = data.get('description', '')
    product = db_create_product(name=name, thumbnail=thumbnail, Cost=cost, Price=price, Stock=stock, CategoryId=category_id, description=description)
    return jsonify(product), 201

@api_bp.put('/products/<int:product_id>')
def api_update_product(product_id):
    data = request.get_json(silent=True) or request.form
    product = get_product_by_id(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    name = data.get('name') or data.get('title')
    thumbnail = data.get('thumbnail') or data.get('image')
    cost = float(data.get('Cost') or data.get('cost')) if ('Cost' in data or 'cost' in data) else None
    price = float(data.get('Price') or data.get('price')) if ('Price' in data or 'price' in data) else None
    stock = int(data.get('Stock') or data.get('stock')) if ('Stock' in data or 'stock' in data) else None
    category_id = int(data.get('CategoryId') or data.get('category_id')) if ('CategoryId' in data or 'category_id' in data) else None
    description = data.get('description')
    updated = db_update_product(product_id, name=name, thumbnail=thumbnail, Cost=cost, Price=price, Stock=stock, CategoryId=category_id, description=description)
    return jsonify(updated), 200

@api_bp.delete('/products/<int:product_id>')
def api_delete_product(product_id):
    success = db_delete_product(product_id)
    if not success:
        return jsonify({"error": "Product not found"}), 404
    return jsonify({"message": f"Product #{product_id} deleted successfully"}), 200

# --- ProductImage API ---
@api_bp.get('/products/<int:product_id>/images')
def api_get_product_images(product_id):
    images = get_images_by_product_id(product_id)
    return jsonify(images), 200

@api_bp.post('/products/<int:product_id>/images')
@api_bp.post('/product-images')
def api_create_product_image(product_id=None):
    data = request.get_json(silent=True) or request.form
    target_product_id = product_id or data.get('ProductId') or data.get('product_id')
    if not target_product_id:
        return jsonify({"error": "ProductId is required"}), 400
    image_url = save_uploaded_image('image_file', 'name', data.get('name', ''))
    if not image_url:
        return jsonify({"error": "Image URL or file is required"}), 400
    img = db_create_product_image(int(target_product_id), image_url)
    return jsonify(img), 201

@api_bp.delete('/product-images/<int:image_id>')
def api_delete_product_image(image_id):
    success = db_delete_product_image(image_id)
    if not success:
        return jsonify({"error": "Product image not found"}), 404
    return jsonify({"message": f"Product image #{image_id} deleted successfully"}), 200

# --- User API ---
@api_bp.get('/users')
def api_get_users():
    users = get_all_users()
    sanitized = []
    for u in users:
        d = dict(u)
        d.pop('password', None)
        sanitized.append(d)
    return jsonify(sanitized), 200

@api_bp.get('/users/<int:user_id>')
def api_get_user(user_id):
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    d = dict(user)
    d.pop('password', None)
    return jsonify(d), 200

@api_bp.post('/users')
def api_create_user():
    data = request.get_json(silent=True) or request.form
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    if not name or not email or not password:
        return jsonify({"error": "name, email, and password are required"}), 400
    if get_user_by_email(email):
        return jsonify({"error": "User with this email already exists"}), 409
    image = save_uploaded_image('image_file', 'image', data.get('image', ''))
    role = data.get('role', 'User')
    user = db_create_user(name=name, email=email, password=password, image=image, role=role)
    d = dict(user)
    d.pop('password', None)
    return jsonify(d), 201

@api_bp.put('/users/<int:user_id>')
def api_update_user(user_id):
    data = request.get_json(silent=True) or request.form
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    image = save_uploaded_image('image_file', 'image', data.get('image'))
    role = data.get('role')
    updated = db_update_user(user_id, name=name, email=email, password=password, image=image, role=role)
    d = dict(updated)
    d.pop('password', None)
    return jsonify(d), 200

@api_bp.delete('/users/<int:user_id>')
def api_delete_user(user_id):
    success = db_delete_user(user_id)
    if not success:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"message": f"User #{user_id} deleted successfully"}), 200

# Register Core API Blueprint
app.register_blueprint(api_bp)


# ==============================================================================
# ACCESS DECORATORS
# ==============================================================================
def login_required(f):
    from functools import wraps
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


# ==============================================================================
# PUBLIC STOREFRONT ROUTES
# ==============================================================================

@app.get('/')
def home():
    products_list = get_all_products()
    return render_template('front/index.html', products=products_list)


@app.get('/products')
def products():
    categories_list = get_all_categories()
    cat_names = sorted(list(set(c['name'] for c in categories_list)))
    selected_category = request.args.get('category', '').strip()
    search_query = request.args.get('q', '').strip() or request.args.get('search', '').strip()

    products_list = get_all_products(search=search_query)
    if selected_category:
        products_list = [p for p in products_list if p.get('category', '').lower() == selected_category.lower()]

    return render_template(
        'front/products.html',
        products=products_list,
        categories=cat_names,
        selected_category=selected_category,
        search_query=search_query,
        current_page='products'
    )


@app.get('/product/<int:product_id>')
def product(product_id):
    product_detail = get_product_by_id(product_id)
    if product_detail is None:
        abort(404)

    all_prods = get_all_products()
    similar_products = [
        p for p in all_prods
        if p.get("CategoryId") == product_detail.get("CategoryId") and p["id"] != product_detail["id"]
    ][:4]

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
    if is_buy_now:
        session['checkout_selected_ids'] = [product_id]
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
            if isinstance(cookie_data, list):
                for cookie_item in cookie_data:
                    if isinstance(cookie_item, dict):
                        product_lookup = get_product_by_id(cookie_item.get("id"))
                        if product_lookup:
                            item_copy = product_lookup.copy()
                            item_copy["quantity"] = cookie_item.get("qty", 1)
                            cart_items.append(item_copy)
                            subtotal += item_copy['price'] * item_copy['quantity']
        except json.JSONDecodeError:
            pass

    return render_template('front/cart.html', cart_items=cart_items, subtotal=round(subtotal, 2), total=round(subtotal, 2))


@app.post('/update-quantity-nojs/<int:product_id>')
def update_quantity_nojs(product_id):
    cart_cookie = request.cookies.get('shopping_cart')
    cart_list = []

    if cart_cookie:
        try:
            cart_list = json.loads(cart_cookie)
        except json.JSONDecodeError:
            pass

    change_direction = request.form.get('direction')
    for item in cart_list:
        if isinstance(item, dict) and item.get("id") == product_id:
            if change_direction == 'up':
                item["qty"] += 1
            elif change_direction == 'down' and item["qty"] > 1:
                item["qty"] -= 1
            break

    response = make_response(redirect(url_for('cart')))
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

    updated_cart = [
        item for item in cart_list
        if isinstance(item, dict) and item.get("id") != product_id
    ]

    response = make_response(redirect(url_for('cart')))
    response.set_cookie('shopping_cart', json.dumps(updated_cart), max_age=2592000, httponly=True)
    return response


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart_cookie = request.cookies.get('shopping_cart')
    cart_list = []

    if cart_cookie:
        try:
            cookie_data = json.loads(cart_cookie)
            if isinstance(cookie_data, list):
                cart_list = [item for item in cookie_data if isinstance(item, dict)]
        except json.JSONDecodeError:
            cart_list = []

    if not cart_list:
        flash("Your shopping cart is empty.", "info")
        return redirect(url_for('cart'))

    # Determine which product IDs are selected
    selected_ids = []
    if request.method == 'POST':
        raw_selected = request.form.getlist('selected_items')
        if not raw_selected and request.form.get('selected_ids'):
            raw_selected = [x.strip() for x in request.form.get('selected_ids').split(',') if x.strip()]
        for s in raw_selected:
            try:
                selected_ids.append(int(s))
            except (ValueError, TypeError):
                pass
        # Save selection to session
        session['checkout_selected_ids'] = selected_ids
    else:
        # GET request: query param takes priority, then session, then all items as fallback
        if 'selected' in request.args:
            for s in request.args.get('selected', '').split(','):
                try:
                    selected_ids.append(int(s.strip()))
                except (ValueError, TypeError):
                    pass
            session['checkout_selected_ids'] = selected_ids
        elif session.get('checkout_selected_ids'):
            selected_ids = session.get('checkout_selected_ids', [])
        else:
            selected_ids = [item.get('id') for item in cart_list if item.get('id')]
            session['checkout_selected_ids'] = selected_ids

    # Validate selected products on backend against user's cart and database
    cart_map = {item.get('id'): item.get('qty', 1) for item in cart_list if item.get('id')}
    selected_set = set(selected_ids)

    checkout_items = []
    subtotal = 0.0

    for item in cart_list:
        pid = item.get('id')
        if pid in selected_set:
            product_lookup = get_product_by_id(pid)
            if product_lookup:
                item_copy = product_lookup.copy()
                item_copy["quantity"] = cart_map.get(pid, 1)
                checkout_items.append(item_copy)
                subtotal += item_copy['price'] * item_copy['quantity']

    if not checkout_items:
        flash("Please select at least one product from your cart to proceed to checkout.", "warning")
        return redirect(url_for('cart'))

    # Update session with validated selected IDs
    session['checkout_selected_ids'] = [item['id'] for item in checkout_items]

    return render_template(
        'front/checkout.html',
        cart_items=checkout_items,
        subtotal=round(subtotal, 2),
        total=round(subtotal, 2),
        selected_ids=[item['id'] for item in checkout_items]
    )


@app.route('/telegram_order', methods=['POST'])
@limiter.limit("30 per minute")
def telegram_order():
    cart_cookie = request.cookies.get('shopping_cart')
    raw_cart_list = []
    if cart_cookie:
        try:
            cookie_data = json.loads(cart_cookie)
            if isinstance(cookie_data, list):
                raw_cart_list = [it for it in cookie_data if isinstance(it, dict)]
        except json.JSONDecodeError:
            raw_cart_list = []

    if not raw_cart_list:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({"success": False, "error": "Your shopping cart is empty"}), 400
        return redirect(url_for('cart'))

    # Determine purchased IDs from form or session
    selected_raw = request.form.getlist('selected_items')
    if not selected_raw and request.form.get('selected_ids'):
        selected_raw = [x.strip() for x in request.form.get('selected_ids').split(',') if x.strip()]

    selected_ids = []
    for sid in selected_raw:
        try:
            selected_ids.append(int(sid))
        except (ValueError, TypeError):
            pass

    if not selected_ids and session.get('checkout_selected_ids'):
        selected_ids = session.get('checkout_selected_ids', [])

    cart_map = {item.get('id'): item.get('qty', 1) for item in raw_cart_list if item.get('id')}

    if selected_ids:
        purchased_ids_set = set(selected_ids).intersection(cart_map.keys())
    else:
        purchased_ids_set = set(cart_map.keys())

    cart_items = []
    subtotal = 0.0

    for pid in purchased_ids_set:
        product_lookup = get_product_by_id(pid)
        if product_lookup:
            item_copy = product_lookup.copy()
            item_copy["quantity"] = cart_map.get(pid, 1)
            cart_items.append(item_copy)
            subtotal += item_copy['price'] * item_copy['quantity']

    if not cart_items:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({"success": False, "error": "No valid products found for checkout"}), 400
        flash("No valid products were selected for order.", "warning")
        return redirect(url_for('cart'))

    username = request.form.get('username', '').strip()
    if not username:
        first_name = request.form.get('firstName', '').strip()
        last_name = request.form.get('lastName', '').strip()
        username = f"{first_name} {last_name}".strip() or "N/A"

    address = request.form.get('address', 'N/A').strip() or 'N/A'
    city = request.form.get('city', 'Phnom Penh').strip() or 'Phnom Penh'
    phone = request.form.get('phone', 'N/A').strip() or 'N/A'
    email = request.form.get('email', 'N/A').strip() or 'N/A'

    new_order_id = 1000 + len(orders_log) + 1
    orders_log.insert(0, {
        "id": new_order_id,
        "customer_name": username,
        "email": email,
        "phone": phone,
        "address": address,
        "city": city,
        "items": cart_items,
        "total_amount": round(subtotal, 2),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status": "Pending"
    })

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
        requests.post(telegram_url, json=payload, timeout=3)
    except Exception as e:
        print(f"Telegram API Error: {e}")

    # Remove ONLY purchased products from the shopping cart cookie
    remaining_cart = [
        item for item in raw_cart_list
        if item.get("id") not in purchased_ids_set
    ]

    # Clear checkout session selection
    session.pop('checkout_selected_ids', None)

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json

    if is_ajax:
        response = make_response(jsonify({
            "success": True,
            "order_id": new_order_id,
            "redirect_url": url_for('cart', order_success=1)
        }))
    else:
        response = make_response(redirect(url_for('cart', order_success=1)))

    if remaining_cart:
        response.set_cookie('shopping_cart', json.dumps(remaining_cart), max_age=2592000, httponly=True)
    else:
        response.delete_cookie('shopping_cart')

    return response


@app.get('/account')
@login_required
def account():
    user = get_user_by_id(session.get('user_id')) if session.get('user_id') else None
    return render_template('front/account.html', user=user)


@app.post('/account/update')
@login_required
def update_account():
    user_id = session.get('user_id')
    user = get_user_by_id(user_id)
    if not user:
        flash("User session not found.", "error")
        return redirect(url_for('login'))

    name = request.form.get('name', user['name']).strip()
    password = request.form.get('password', '').strip()
    image_file = request.files.get('image_file')

    new_image = user.get('image')
    if image_file and image_file.filename and image_file.filename.strip():
        new_image = save_uploaded_image('image_file', 'image', user.get('image'))

    updated = db_update_user(user_id=user_id, name=name, password=password if password else None, image=new_image)
    if updated:
        session['user_name'] = updated['name']
        session['user_image'] = updated.get('image', '')
        session['user'] = updated['name']
        flash("Your profile information has been updated successfully.", "success")
    else:
        flash("Failed to update profile.", "error")

    return redirect(url_for('account'))


@app.get('/forget-password')
def forget_password():
    return render_template('front/forget-password.html')


@app.route('/contact', methods=['GET', 'POST'])
@limiter.limit("30 per minute")
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        order_ref = request.form.get('order_ref', '').strip()
        subject = request.form.get('subject', '').strip()
        message_text = request.form.get('message', '').strip()

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
# STOREFRONT AUTHENTICATION
# ==============================================================================

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("15 per minute")
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
@limiter.limit("15 per minute")
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
        avatar_img = save_uploaded_image('image_file', 'image', default_avatar)

        new_user = db_create_user(
            name=name,
            email=email,
            password=password,
            image=avatar_img,
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


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=True)