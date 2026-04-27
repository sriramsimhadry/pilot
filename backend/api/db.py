import aiosqlite
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "aeroo.db")

async def init_db():
    """Initialize the SQLite database and create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                query TEXT,
                origin_display TEXT,
                destination_display TEXT,
                travel_date TEXT,
                is_round_trip BOOLEAN,
                return_date TEXT,
                top3_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def insert_search_record(workflow_id: str, plan: dict, summary: dict):
    """Insert a completed search with its top 3 flights into the database."""
    if not plan or not plan.get("parsed"):
        return
        
    parsed = plan["parsed"]
    query = parsed.get("raw_query", "")
    origin = parsed.get("origin", {}).get("display", "")
    dest = parsed.get("destination", {}).get("display", "")
    date = parsed.get("date", "")
    is_round_trip = parsed.get("is_round_trip", False)
    return_date = parsed.get("return_date", "")
    
    # Store only the top3 array from the summary
    top3_data = summary.get("top3", []) if summary else []
    top3_json = json.dumps(top3_data)
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO search_history 
            (workflow_id, query, origin_display, destination_display, travel_date, is_round_trip, return_date, top3_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (workflow_id, query, origin, dest, date, is_round_trip, return_date, top3_json))
        await db.commit()

async def get_search_history() -> list:
    """Retrieve all past searches, ordered by newest first."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM search_history 
            ORDER BY created_at DESC 
            LIMIT 50
        """) as cursor:
            rows = await cursor.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    "id": row["id"],
                    "workflow_id": row["workflow_id"],
                    "query": row["query"],
                    "origin": row["origin_display"],
                    "destination": row["destination_display"],
                    "date": row["travel_date"],
                    "is_round_trip": bool(row["is_round_trip"]),
                    "return_date": row["return_date"],
                    "top3": json.loads(row["top3_json"]) if row["top3_json"] else [],
                    "created_at": row["created_at"]
                })
            return results
