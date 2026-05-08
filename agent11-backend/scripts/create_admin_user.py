"""Create admin user script"""
import asyncio
import uuid
import bcrypt

from app.db.postgres import Database
from app.config import get_settings


async def create_admin_user():
    settings = get_settings()

    # Connect to database
    await Database.connect()

    # Create users table if not exists
    await Database.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id VARCHAR PRIMARY KEY,
            user_name VARCHAR NOT NULL,
            email VARCHAR UNIQUE NOT NULL,
            password_hash VARCHAR NOT NULL,
            profile_picture VARCHAR,
            is_active BOOLEAN DEFAULT TRUE,
            is_admin BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Check if admin already exists
    existing = await Database.fetchrow(
        "SELECT * FROM users WHERE email = $1",
        "admin@agent11.local"
    )

    if existing:
        print("Admin user already exists!")
        print(f"Email: admin@agent11.local")
        print(f"User ID: {existing['user_id']}")
    else:
        # Create admin user
        admin_id = str(uuid.uuid4())
        password = "admin123".encode('utf-8')
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password, salt).decode('utf-8')

        await Database.execute("""
            INSERT INTO users (user_id, user_name, email, password_hash, is_admin)
            VALUES ($1, $2, $3, $4, $5)
        """, admin_id, "Administrator", "admin@agent11.local", password_hash, True)

        print("Admin user created successfully!")
        print(f"Email: admin@agent11.local")
        print(f"Password: admin123")
        print(f"User ID: {admin_id}")

    await Database.disconnect()


if __name__ == "__main__":
    asyncio.run(create_admin_user())
