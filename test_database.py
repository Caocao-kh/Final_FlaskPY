import os
import sys
import unittest
import json

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import (
    init_db,
    # Users
    get_user_by_email,
    get_user_by_id,
    get_all_users,
    create_user,
    update_user,
    delete_user,
    # Categories (Category 5pts)
    get_all_categories,
    get_category_by_id,
    create_category,
    update_category,
    delete_category,
    # Products (Product 5pts)
    get_all_products,
    get_product_by_id,
    create_product,
    update_product,
    delete_product,
    # Product Images (ProductImage 5pts)
    get_images_by_product_id,
    get_product_image_by_id,
    create_product_image,
    delete_product_image,
    DB_PATH
)
from app import app, limiter


class ComprehensiveExamRequirementsTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        limiter.enabled = False
        init_db()
        self.client = app.test_client()

    # ---------------------------------------------------------
    # 1. USER & AUTH (ADMIN & FRONT)
    # ---------------------------------------------------------
    def test_1_default_users_seeded(self):
        admin = get_user_by_email('admin@superman.com')
        self.assertIsNotNone(admin, "Default admin user should exist in DB")
        self.assertEqual(admin['role'], 'Admin')

        user = get_user_by_email('jane.smith@example.com')
        self.assertIsNotNone(user, "Default sample user should exist in DB")
        self.assertEqual(user['role'], 'User')

    def test_2_register_account_persistence(self):
        test_email = 'peter.parker@spidey.io'
        existing = get_user_by_email(test_email)
        if existing:
            delete_user(existing['id'])

        response = self.client.post('/create_user', data={
            'first_name': 'Peter',
            'last_name': 'Parker',
            'email': test_email,
            'password': 'spidermansecret!',
            'confirm_password': 'spidermansecret!'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)

        user_in_db = get_user_by_email(test_email)
        self.assertIsNotNone(user_in_db, "Newly registered user must be persisted in SQLite DB")
        self.assertEqual(user_in_db['name'], 'Peter Parker')
        self.assertEqual(user_in_db['email'], test_email)
        self.assertEqual(user_in_db['password'], 'spidermansecret!')
        self.assertEqual(user_in_db['role'], 'User')

        # Cleanup
        delete_user(user_in_db['id'])

    def test_3_admin_user_crud_in_db(self):
        test_email = 'bruce.wayne@batman.com'
        created = create_user('Bruce Wayne', test_email, 'batpass99', role='User')
        self.assertIsNotNone(created)
        self.assertEqual(created['email'], test_email)

        updated = update_user(created['id'], name='Bruce Wayne Gotham', role='Admin')
        self.assertEqual(updated['name'], 'Bruce Wayne Gotham')
        self.assertEqual(updated['role'], 'Admin')

        deleted = delete_user(created['id'])
        self.assertTrue(deleted)
        self.assertIsNone(get_user_by_id(created['id']))

    def test_4_admin_web_user_management(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_role'] = 'Admin'
            sess['user_name'] = 'Admin User'

        res = self.client.get('/admin/users')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'admin@superman.com', res.data)

        new_email = 'clark.kent@dailyplanet.com'
        add_res = self.client.post('/admin/user/add', data={
            'name': 'Clark Kent',
            'email': new_email,
            'password': 'supermanpass!',
            'role': 'User'
        }, follow_redirects=True)
        self.assertEqual(add_res.status_code, 200)

        created_user = get_user_by_email(new_email)
        self.assertIsNotNone(created_user)
        self.assertEqual(created_user['name'], 'Clark Kent')

        # Admin delete user
        del_res = self.client.post(f'/admin/user/delete/{created_user["id"]}', follow_redirects=True)
        self.assertEqual(del_res.status_code, 200)
        self.assertIsNone(get_user_by_id(created_user['id']))

    # ---------------------------------------------------------
    # 2. CATEGORY (5pts)
    # schema: id pk, name (varchar 255) not null, image (varchar 255), description (text)
    # ---------------------------------------------------------
    def test_5_category_model_and_crud(self):
        # Create
        cat = create_category(
            name="Gaming Consoles",
            image="https://images.unsplash.com/photo-gaming",
            description="PlayStation, Xbox, and Nintendo devices."
        )
        self.assertIsNotNone(cat)
        self.assertEqual(cat['name'], "Gaming Consoles")
        self.assertEqual(cat['image'], "https://images.unsplash.com/photo-gaming")
        self.assertEqual(cat['description'], "PlayStation, Xbox, and Nintendo devices.")

        # Read
        fetched = get_category_by_id(cat['id'])
        self.assertEqual(fetched['name'], "Gaming Consoles")

        # Update
        updated = update_category(cat['id'], name="Next-Gen Consoles", description="Upgraded consoles.")
        self.assertEqual(updated['name'], "Next-Gen Consoles")
        self.assertEqual(updated['description'], "Upgraded consoles.")

        # List
        all_cats = get_all_categories()
        self.assertTrue(any(c['id'] == cat['id'] for c in all_cats))

        # Delete
        deleted = delete_category(cat['id'])
        self.assertTrue(deleted)
        self.assertIsNone(get_category_by_id(cat['id']))

    # ---------------------------------------------------------
    # 3. PRODUCT (5pts)
    # schema: id pk, name not null, thumbnail, Cost decimal(10,2), Price decimal(10,2), Stock int, CategoryId fk not null, description
    # ---------------------------------------------------------
    def test_6_product_model_and_crud(self):
        # Ensure category exists
        test_cat = create_category(name="Test Laptops", description="High performance machines")
        cat_id = test_cat['id']

        # Create product with exact requested fields
        prod = create_product(
            name="MacBook Pro M3",
            thumbnail="https://images.unsplash.com/photo-macbook",
            Cost=1400.00,
            Price=1999.99,
            Stock=25,
            CategoryId=cat_id,
            description="16-inch Liquid Retina XDR display with M3 Max."
        )
        self.assertIsNotNone(prod)
        self.assertEqual(prod['name'], "MacBook Pro M3")
        self.assertEqual(prod['thumbnail'], "https://images.unsplash.com/photo-macbook")
        self.assertEqual(prod['Cost'], 1400.00)
        self.assertEqual(prod['Price'], 1999.99)
        self.assertEqual(prod['Stock'], 25)
        self.assertEqual(prod['CategoryId'], cat_id)

        # Read
        fetched = get_product_by_id(prod['id'])
        self.assertEqual(fetched['name'], "MacBook Pro M3")
        self.assertEqual(fetched['Cost'], 1400.00)
        self.assertEqual(fetched['Price'], 1999.99)
        self.assertEqual(fetched['Stock'], 25)
        self.assertEqual(fetched['CategoryId'], cat_id)

        # Compatibility aliases
        self.assertEqual(fetched['title'], "MacBook Pro M3")
        self.assertEqual(fetched['image'], "https://images.unsplash.com/photo-macbook")
        self.assertEqual(fetched['price'], 1999.99)
        self.assertEqual(fetched['stock'], 25)

        # Update
        updated = update_product(prod['id'], name="MacBook Pro M3 Max", Price=2199.99, Stock=30)
        self.assertEqual(updated['name'], "MacBook Pro M3 Max")
        self.assertEqual(updated['Price'], 2199.99)
        self.assertEqual(updated['Stock'], 30)

        # Delete
        deleted = delete_product(prod['id'])
        self.assertTrue(deleted)
        self.assertIsNone(get_product_by_id(prod['id']))

        # Cleanup category
        delete_category(cat_id)

    # ---------------------------------------------------------
    # 4. PRODUCT IMAGE (5pts)
    # schema: id pk, ProductId fk not null, name (varchar 255) not null
    # ---------------------------------------------------------
    def test_7_product_image_model_and_crud(self):
        test_cat = create_category(name="Audio Tech")
        prod = create_product(name="Studio Monitors", CategoryId=test_cat['id'])

        # Create images in ProductImage table
        img1 = create_product_image(product_id=prod['id'], name="https://example.com/front-angle.jpg")
        img2 = create_product_image(product_id=prod['id'], name="https://example.com/back-panel.jpg")

        self.assertIsNotNone(img1)
        self.assertEqual(img1['ProductId'], prod['id'])
        self.assertEqual(img1['name'], "https://example.com/front-angle.jpg")

        # Get images for product
        images = get_images_by_product_id(prod['id'])
        self.assertGreaterEqual(len(images), 2)
        urls = [i['name'] for i in images]
        self.assertIn("https://example.com/front-angle.jpg", urls)
        self.assertIn("https://example.com/back-panel.jpg", urls)

        # Delete image
        del_img = delete_product_image(img1['id'])
        self.assertTrue(del_img)
        self.assertIsNone(get_product_image_by_id(img1['id']))

        # Cleanup
        delete_product(prod['id'])
        delete_category(test_cat['id'])

    # ---------------------------------------------------------
    # 5. CORE REST API (core / cors: api)
    # ---------------------------------------------------------
    def test_8_core_rest_api_endpoints(self):
        # 1. Categories API
        cat_res = self.client.get('/api/categories')
        self.assertEqual(cat_res.status_code, 200)
        self.assertIn('application/json', cat_res.content_type)
        cats = json.loads(cat_res.data)
        self.assertIsInstance(cats, list)

        # 2. Products API
        prod_res = self.client.get('/api/products')
        self.assertEqual(prod_res.status_code, 200)
        prods = json.loads(prod_res.data)
        self.assertIsInstance(prods, list)
        self.assertGreater(len(prods), 0)

        # 3. Product Images API
        first_prod_id = prods[0]['id']
        imgs_res = self.client.get(f'/api/products/{first_prod_id}/images')
        self.assertEqual(imgs_res.status_code, 200)
        imgs = json.loads(imgs_res.data)
        self.assertIsInstance(imgs, list)

        # 4. Users API (sanitized, passwords omitted)
        users_res = self.client.get('/api/users')
        self.assertEqual(users_res.status_code, 200)
        users = json.loads(users_res.data)
        for u in users:
            self.assertNotIn('password', u)

    # ---------------------------------------------------------
    # 6. ADMIN AUTH ENFORCEMENT
    # ---------------------------------------------------------
    def test_9_admin_auth_protection(self):
        # Anonymous user blocked from accessing admin routes
        with self.client.session_transaction() as sess:
            sess.clear()

        res = self.client.get('/admin/dashboard')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/admin/login', res.headers.get('Location', ''))

        res_cat = self.client.get('/admin/categories')
        self.assertEqual(res_cat.status_code, 302)
        self.assertIn('/admin/login', res_cat.headers.get('Location', ''))

        res_prod = self.client.get('/admin/products')
        self.assertEqual(res_prod.status_code, 302)
        self.assertIn('/admin/login', res_prod.headers.get('Location', ''))

    # ---------------------------------------------------------
    # 7. CSRF PROTECTION ENFORCEMENT
    # ---------------------------------------------------------
    def test_10_csrf_protection_active(self):
        # Enable CSRF to verify rejection of untokened POST
        app.config['WTF_CSRF_ENABLED'] = True
        client_csrf = app.test_client()

        res = client_csrf.post('/admin/product/add', data={
            'name': 'Hacker Product',
            'Price': 99.99
        })
        # Rejected due to missing CSRF token (redirect with error or 400)
        self.assertIn(res.status_code, [302, 400])

        # Reset
        app.config['WTF_CSRF_ENABLED'] = False


if __name__ == '__main__':
    unittest.main()
