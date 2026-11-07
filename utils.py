import os
import uuid
from flask import request, url_for
from werkzeug.utils import secure_filename

# Upload directory
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def save_uploaded_image(file_key='image_file', text_url_key='image', default_val=''):
    """Helper to save uploaded file or return fallback text URL."""
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
