"""
MongoDB database connection using motor (async driver).
"""

import ssl
import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config import MONGODB_URI

# Global client and database instances
_client: AsyncIOMotorClient = None
_db: AsyncIOMotorDatabase = None


def get_database() -> AsyncIOMotorDatabase:
    """Get the database instance, creating connection if needed."""
    global _client, _db
    
    if _db is None:
        # Configure SSL/TLS for MongoDB Atlas
        # Use certifi's certificate bundle for proper SSL verification
        _client = AsyncIOMotorClient(
            MONGODB_URI,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=30000,
        )
        _db = _client.spinify
    
    return _db


# Convenience accessor
db = get_database()


async def init_indexes():
    """Create database indexes for optimal query performance."""
    database = get_database()
    
    # Users collection
    await database.users.create_index("user_id", unique=True)
    await database.users.create_index("referred_by")
    
    # Sessions collection
    await database.sessions.create_index("user_id", unique=True)
    await database.sessions.create_index("connected")
    
    # Config collection
    await database.config.create_index("user_id", unique=True)
    
    # Groups collection
    await database.groups.create_index([("user_id", 1), ("chat_id", 1)], unique=True)
    await database.groups.create_index("user_id")
    
    # Plans collection
    await database.plans.create_index("user_id", unique=True)
    await database.plans.create_index("expires_at")
    await database.plans.create_index("status")
    
    # Redeem codes collection
    await database.redeem_codes.create_index("code", unique=True)
    await database.redeem_codes.create_index("used_by")
    
    # Send logs collection
    await database.send_logs.create_index([("user_id", 1), ("sent_at", -1)])
    await database.send_logs.create_index("sent_at")
    
    print("✅ Database indexes created successfully!")


async def close_connection():
    """Close the database connection."""
    global _client, _db
    
    if _client:
        _client.close()
        _client = None
        _db = None
