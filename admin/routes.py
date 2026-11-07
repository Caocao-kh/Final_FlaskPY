from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from extensions import limiter
from utils import save_uploaded_image, orders_log
from database import (
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

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id') or session.get('user_role') != 'Admin':
            flash("Please log in with an Administrator account to access the Admin Console.", "warning")
            next_param = request.full_path if request.query_string else request.path
            return redirect(url_for('admin_login', next=next_param))
        return f(*args, **kwargs)
    return decorated_function


# ==============================================================================
# ADMIN AUTHENTICATION
# ==============================================================================

@admin_bp.route('/admin/login', methods=['GET', 'POST'])
@limiter.limit("15 per minute")
def admin_login():
    if session.get('user_id') and session.get('user_role') == 'Admin':
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        remember = bool(request.form.get('remember'))

        user = get_user_by_email(email)
        if not user or user.get('password') != password:
            flash("Invalid administrator email or password.", "error")
            return render_template('admin/login.html')

        if user.get('role') != 'Admin':
            flash("Access Denied: Only Administrator accounts can log in here.", "warning")
            return render_template('admin/login.html')

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


@admin_bp.route('/admin/logout', methods=['GET', 'POST'])
def admin_logout():
    user_name = session.get('user_name', 'Admin')
    session.clear()
    flash(f"Goodbye {user_name}, you have been securely logged out.", "info")
    return redirect(url_for('admin_login'))


# ==============================================================================
# ADMIN DASHBOARD
# ==============================================================================

@admin_bp.get('/home/dashborad')
@admin_bp.get('/admin/dashborad')
@admin_bp.get('/dashboard')
@admin_bp.get('/admin/dashboard')
@admin_bp.get('/admin')
@admin_required
def admin_dashboard():
    all_products = get_all_products()
    total_products = len(all_products)
    total_revenue = sum(o.get('total_amount', 0) for o in orders_log) + sum((p.get('Price', 0) or 0) * 10 for p in all_products)
    total_orders = len(orders_log)

    ratings = [p['rating']['rate'] for p in all_products if isinstance(p.get('rating'), dict) and 'rate' in p['rating']]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

    category_counts = {}
    for p in all_products:
        cat = p.get('category', 'uncategorized')
        category_counts[cat] = category_counts.get(cat, 0) + 1

    top_products = sorted(all_products, key=lambda x: x.get('rating', {}).get('rate', 0) if isinstance(x.get('rating'), dict) else 0, reverse=True)[:5]
    recent_orders = orders_log[:5]

    stats = {
        "total_products": total_products,
        "total_revenue": round(total_revenue, 2),
        "total_orders": total_orders,
        "avg_rating": round(avg_rating, 1)
    }

    return render_template(
        'admin/dashboard.html',
        active_page='dashboard',
        stats=stats,
        category_counts=category_counts,
        top_products=top_products,
        recent_orders=recent_orders
    )


# ==============================================================================
# CATEGORY MANAGEMENT (Category 5pts)
# ==============================================================================

@admin_bp.get('/admin/categories')
@admin_required
def admin_categories():
    categories_list = get_all_categories()
    return render_template('admin/categories.html', active_page='categories', categories=categories_list)


@admin_bp.post('/admin/category/add')
@admin_required
def admin_add_category():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    image = save_uploaded_image('image_file', 'image', 'https://images.unsplash.com/photo-1526738549149-8e07eca6c147?w=500')

    if not name:
        flash("Category name is required.", "error")
        return redirect(url_for('admin_categories'))

    db_create_category(name=name, image=image, description=description)
    flash(f"Category '{name}' created successfully!", "success")
    return redirect(url_for('admin_categories'))


@admin_bp.post('/admin/category/edit/<int:category_id>')
@admin_required
def admin_edit_category(category_id):
    cat = get_category_by_id(category_id)
    if not cat:
        flash("Category not found.", "error")
        return redirect(url_for('admin_categories'))

    name = request.form.get('name', cat['name']).strip()
    description = request.form.get('description', cat['description']).strip()
    new_image = save_uploaded_image('image_file', 'image', cat.get('image', ''))

    db_update_category(category_id, name=name, image=new_image, description=description)
    flash(f"Category '{name}' updated successfully!", "success")
    return redirect(url_for('admin_categories'))


@admin_bp.route('/admin/category/delete/<int:category_id>', methods=['POST', 'GET'])
@admin_required
def admin_delete_category(category_id):
    success = db_delete_category(category_id)
    if success:
        flash(f"Category #{category_id} deleted successfully!", "success")
    else:
        flash("Category not found.", "error")
    return redirect(url_for('admin_categories'))


# ==============================================================================
# PRODUCT MANAGEMENT (Product 5pts)
# ==============================================================================

@admin_bp.get('/admin/products')
@admin_required
def admin_products():
    products_list = get_all_products()
    categories_list = get_all_categories()
    return render_template('admin/products.html', active_page='products', products=products_list, categories=categories_list)


@admin_bp.post('/admin/product/add')
@admin_required
def admin_add_product():
    try:
        name = request.form.get('name') or request.form.get('title', '').strip()
        cost = float(request.form.get('Cost') or request.form.get('cost') or 0.0)
        price = float(request.form.get('Price') or request.form.get('price') or 0.0)
        stock = int(request.form.get('Stock') or request.form.get('stock') or 50)
        category_id = int(request.form.get('CategoryId') or request.form.get('category_id') or 1)
        description = request.form.get('description', '').strip()
        thumbnail = save_uploaded_image('thumbnail_file', 'thumbnail', '')
        if not thumbnail:
            thumbnail = save_uploaded_image('image_file', 'image', 'https://via.placeholder.com/200')

        db_create_product(name=name, thumbnail=thumbnail, Cost=cost, Price=price, Stock=stock, CategoryId=category_id, description=description)
        flash(f"Product '{name}' created successfully!", "success")
    except Exception as e:
        flash(f"Error adding product: {str(e)}", "error")

    return redirect(url_for('admin_products'))


@admin_bp.post('/admin/product/edit/<int:product_id>')
@admin_required
def admin_edit_product(product_id):
    product_item = get_product_by_id(product_id)
    if not product_item:
        flash("Product not found", "error")
        return redirect(url_for('admin_products'))

    try:
        name = request.form.get('name') or request.form.get('title', product_item['name'])
        cost = float(request.form.get('Cost') or request.form.get('cost') or product_item['Cost'])
        price = float(request.form.get('Price') or request.form.get('price') or product_item['Price'])
        stock = int(request.form.get('Stock') or request.form.get('stock') or product_item['Stock'])
        category_id = int(request.form.get('CategoryId') or request.form.get('category_id') or product_item['CategoryId'])
        description = request.form.get('description', product_item['description'])

        new_thumb = save_uploaded_image('thumbnail_file', 'thumbnail', '')
        if not new_thumb:
            new_thumb = save_uploaded_image('image_file', 'image', product_item.get('thumbnail', ''))

        db_update_product(
            product_id=product_id,
            name=name,
            thumbnail=new_thumb if new_thumb else product_item.get('thumbnail'),
            Cost=cost,
            Price=price,
            Stock=stock,
            CategoryId=category_id,
            description=description
        )
        flash(f"Product '{name}' updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating product: {str(e)}", "error")

    return redirect(url_for('admin_products'))


@admin_bp.route('/admin/product/delete/<int:product_id>', methods=['POST', 'GET'])
@admin_required
def admin_delete_product(product_id):
    success = db_delete_product(product_id)
    if success:
        flash(f"Product #{product_id} deleted successfully!", "success")
    else:
        flash("Product not found", "error")
    return redirect(url_for('admin_products'))


# ==============================================================================
# PRODUCT IMAGE MANAGEMENT (ProductImage 5pts)
# ==============================================================================

@admin_bp.post('/admin/product/<int:product_id>/image/add')
@admin_required
def admin_add_product_image(product_id):
    img_name = save_uploaded_image('image_file', 'name', '')
    if not img_name:
        flash("Image file or URL is required.", "error")
        return redirect(url_for('admin_products'))

    db_create_product_image(product_id=product_id, name=img_name)
    flash("Gallery image added successfully!", "success")
    return redirect(url_for('admin_products'))


@admin_bp.route('/admin/product/image/delete/<int:image_id>', methods=['POST', 'GET'])
@admin_required
def admin_delete_product_image(image_id):
    success = db_delete_product_image(image_id)
    if success:
        flash("Gallery image removed successfully.", "success")
    else:
        flash("Gallery image not found.", "error")
    return redirect(url_for('admin_products'))


# ==============================================================================
# ORDER MANAGEMENT
# ==============================================================================

@admin_bp.get('/admin/orders')
@admin_required
def admin_orders():
    return render_template('admin/orders.html', active_page='orders', orders=orders_log)


# ==============================================================================
# USER MANAGEMENT (CRUD user [upload image])
# ==============================================================================

@admin_bp.get('/admin/users')
@admin_required
def admin_users():
    users_list = get_all_users()
    return render_template('admin/users.html', active_page='users', users=users_list)


@admin_bp.route('/admin/user/add', methods=['GET', 'POST'])
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


@admin_bp.route('/admin/user/edit/<int:user_id>', methods=['GET', 'POST'])
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


@admin_bp.route('/admin/user/delete/<int:user_id>', methods=['POST', 'GET'])
@admin_required
def admin_delete_user(user_id):
    success = db_delete_user(user_id)
    if success:
        flash(f"User #{user_id} deleted successfully!", "success")
    else:
        flash("User not found", "error")
    return redirect(url_for('admin_users'))
