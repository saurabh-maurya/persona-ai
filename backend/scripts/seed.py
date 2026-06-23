"""
Seed script — creates a sample character and session for testing.
Run: python scripts/seed.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "persona_ai_studio")


async def seed():
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[MONGODB_DB]

    # Clear existing seed data
    await db.characters.delete_many({"name": "Riva Mehra"})

    character = {
        "_id": ObjectId(),
        "name": "Riva Mehra",
        "age": "24 years old / adult 18+",
        "gender": "Female, feminine, soft-glam, luxury lifestyle creator",
        "persona": "Confident, playful, slightly mysterious, classy, emotionally engaging, flirty in a safe way, ambitious",
        "appearance": "Tall, slim, South Asian features, long dark hair, warm skin tone, expressive eyes",
        "fashionStyle": "Soft-glam luxury — beige, black, ivory, champagne, gold, satin, linen, fitted dresses, oversized shirts, activewear, blazers, heels, gold accessories",
        "audience": "Men aged 21-38 who enjoy attractive lifestyle creators, fashion, beauty, fitness, and premium content",
        "niche": "Luxury lifestyle, soft-glam fashion, nightlife, fitness, travel, beauty, emotional storytelling",
        "city": "Mumbai",
        "country": "India",
        "masterPrompt": "",
        "status": "active",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    await db.characters.insert_one(character)
    char_id = str(character["_id"])
    print(f"Created character: Riva Mehra ({char_id})")

    session = {
        "_id": ObjectId(),
        "characterId": char_id,
        "sessionName": "Riva_Mehra_2026_06_10_001",
        "startDate": "2026-06-10",
        "endDate": "2026-06-12",
        "contentStructure": {"sections": {"Morning": 3, "Evening": 5, "Night": 10}},
        "status": "CREATED",
        "totalDays": 3,
        "totalImages": 54,
        "generatedImages": 0,
        "failedImages": 0,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    await db.sessions.insert_one(session)
    session_id = str(session["_id"])
    print(f"Created session: Riva_Mehra_2026_06_10_001 ({session_id})")
    print("\nSeed complete!")
    print(f"\nTo generate content plan, POST to:")
    print(f"  POST /api/plans/generate  body: {{\"sessionId\": \"{session_id}\"}}")

    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
