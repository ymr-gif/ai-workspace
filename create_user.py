import asyncio
from passlib.context import CryptContext
from db import AsyncSessionLocal, init_db
from models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def seed():
    await init_db()

    async with AsyncSessionLocal() as db:
        users = [
            User(
                username="admin",
                hashed_password=pwd_context.hash("admin-secret"),
                role="admin",
            ),
            User(
                username="user",
                hashed_password=pwd_context.hash("user-secret"),
                role="user",
            ),
        ]
        db.add_all(users)
        await db.commit()
        print("✓ Users seeded.")

asyncio.run(seed())