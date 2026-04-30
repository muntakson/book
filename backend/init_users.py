#!/usr/bin/env python3
"""
Initialize database with default users.

Reads ADMIN_PASSWORD from environment (backend/.env). Falls back to a random
generated value printed on first run if not set.
"""
import os
import secrets
from dotenv import load_dotenv
from models import User, SessionLocal, init_db
from auth import get_password_hash

load_dotenv()

def create_default_users():
    """Create admin and bob users"""
    init_db()

    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_password:
        admin_password = secrets.token_urlsafe(12)
        print(f"⚠️  ADMIN_PASSWORD not set in env; generated: {admin_password}")
        print("   Save this and add ADMIN_PASSWORD=... to backend/.env")

    db = SessionLocal()

    try:
        existing_admin = db.query(User).filter(User.username == "admin").first()
        existing_bob = db.query(User).filter(User.username == "bob").first()

        if not existing_admin:
            admin = User(
                username="admin",
                password_hash=get_password_hash(admin_password)
            )
            db.add(admin)
            print("✅ Created user: admin (password from $ADMIN_PASSWORD)")
        else:
            print("ℹ️  User 'admin' already exists")

        if not existing_bob:
            bob = User(
                username="bob",
                password_hash=get_password_hash("q1")
            )
            db.add(bob)
            print("✅ Created user: bob (password: q1)")
        else:
            print("ℹ️  User 'bob' already exists")

        db.commit()
        print("\n✅ Database initialized successfully!")

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_default_users()
