import sqlite3
import secrets
import string
from datetime import datetime

class APIKeyManager:
    def __init__(self):
        self.db_name = 'apikeys.db'
        self.setup_database()

    def setup_database(self):
        """Create the database and tables if they don't exist"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                api_key TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        conn.commit()
        conn.close()

    def generate_api_key(self, customer_id: str) -> str:
        """Generate a new API key for a customer"""
        # Generate a random 32-character API key
        alphabet = string.ascii_letters + string.digits
        api_key = ''.join(secrets.choice(alphabet) for _ in range(32))
        
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                'INSERT INTO api_keys (customer_id, api_key) VALUES (?, ?)',
                (customer_id, api_key)
            )
            conn.commit()
            return api_key
        except sqlite3.IntegrityError:
            # If there's a duplicate key, try again
            return self.generate_api_key(customer_id)
        finally:
            conn.close()

    def verify_api_key(self, api_key: str) -> bool:
        """Verify if an API key is valid"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT is_active FROM api_keys WHERE api_key = ?',
            (api_key,)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        return bool(result and result[0])

    def get_customer_id(self, api_key: str) -> str:
        """Get customer ID associated with an API key"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT customer_id FROM api_keys WHERE api_key = ? AND is_active = 1',
            (api_key,)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None 