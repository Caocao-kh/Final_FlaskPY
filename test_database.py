import os
import sys
import unittest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import (
    init_db,
    get_user_by_email,
    get_user_by_id,
    get_all_users,
    create_user,
    update_user,
    delete_user,
    DB_PATH
)
from app import app

class DatabaseAndAuthTestCase(unittest.TestCase):
    def setUp(self):
        init_db()
        self.client = app.test_client()

    def test_1_default_users_seeded(self):
        admin = get_user_by_email('admin@superman.com')
        self.assertIsNotNone(admin, "Default admin user should exist in DB")
        self.assertEqual(admin['role'], 'Admin')

        user = get_user_by_email('jane.smith@example.com')
        self.assertIsNotNone(user, "Default sample user should exist in DB")
        self.assertEqual(user['role'], 'User')

    def test_2_register_account_persistence(self):
        test_email = 'peter.parker@spidey.io'
        # Clean up if existed
        existing = get_user_by_email(test_email)
        if existing:
            delete_user(existing['id'])

        # Register through web route
        response = self.client.post('/create_user', data={
            'first_name': 'Peter',
            'last_name': 'Parker',
            'email': test_email,
            'password': 'spidermansecret!',
            'confirm_password': 'spidermansecret!'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)

        # Check directly from SQLite database
        user_in_db = get_user_by_email(test_email)
        self.assertIsNotNone(user_in_db, "Newly registered user must be persisted in SQLite DB")
        self.assertEqual(user_in_db['name'], 'Peter Parker')
        self.assertEqual(user_in_db['email'], test_email)
        self.assertEqual(user_in_db['password'], 'spidermansecret!')
        self.assertEqual(user_in_db['role'], 'User')

        # Test login with the newly created user
        with self.client.session_transaction() as sess:
            sess.clear()

        login_res = self.client.post('/login', data={
            'email': test_email,
            'password': 'spidermansecret!'
        }, follow_redirects=True)

        self.assertEqual(login_res.status_code, 200)
        self.assertIn(b'Peter Parker', login_res.data)

        # Test duplicate registration rejection
        with self.client.session_transaction() as sess:
            sess.clear()

        dup_res = self.client.post('/create_user', data={
            'first_name': 'Peter',
            'last_name': 'Parker',
            'email': test_email,
            'password': 'different_password',
            'confirm_password': 'different_password'
        }, follow_redirects=True)

        self.assertIn(b'already exists', dup_res.data)

        # Cleanup
        delete_user(user_in_db['id'])

    def test_3_admin_user_crud_in_db(self):
        test_email = 'bruce.wayne@batman.com'
        # Create user via DB function
        created = create_user('Bruce Wayne', test_email, 'batpass99', role='User')
        self.assertIsNotNone(created)
        self.assertEqual(created['email'], test_email)

        # Update user
        updated = update_user(created['id'], name='Bruce Wayne Gotham', role='Admin')
        self.assertEqual(updated['name'], 'Bruce Wayne Gotham')
        self.assertEqual(updated['role'], 'Admin')

        # Delete user
        deleted = delete_user(created['id'])
        self.assertTrue(deleted)
        self.assertIsNone(get_user_by_id(created['id']))

    def test_4_admin_web_user_management(self):
        # Admin login
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_role'] = 'Admin'
            sess['user_name'] = 'Admin User'

        # View users table
        res = self.client.get('/admin/users')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'admin@superman.com', res.data)

        # Admin add user via web POST
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

        # Admin edit user
        edit_res = self.client.post(f'/admin/user/edit/{created_user["id"]}', data={
            'name': 'Clark Kent Superman',
            'email': new_email,
            'password': 'newsupermanpass!',
            'role': 'Admin'
        }, follow_redirects=True)
        self.assertEqual(edit_res.status_code, 200)

        updated_user = get_user_by_id(created_user['id'])
        self.assertEqual(updated_user['name'], 'Clark Kent Superman')
        self.assertEqual(updated_user['role'], 'Admin')

        # Admin delete user
        del_res = self.client.post(f'/admin/user/delete/{created_user["id"]}', follow_redirects=True)
        self.assertEqual(del_res.status_code, 200)
        self.assertIsNone(get_user_by_id(created_user['id']))

    def test_5_sqlite_file_exists_and_persists(self):
        self.assertTrue(os.path.exists(DB_PATH), "database.db SQLite file must exist on disk")
        all_users = get_all_users()
        self.assertGreaterEqual(len(all_users), 2, "Must contain at least initial accounts")

if __name__ == '__main__':
    unittest.main()
