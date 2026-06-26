import sqlite3
import os
import json

db_path = "core/jobs.db"
if not os.path.exists(db_path):
    db_path = "../core/jobs.db"

print(f"Checking database at {db_path}...")
if not os.path.exists(db_path):
    print("Database file does not exist!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get list of tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [r[0] for r in cursor.fetchall()]
print(f"Tables: {tables}")

# Print schema of each table
for table in tables:
    print(f"\nSchema for table: {table}")
    cursor.execute(f"PRAGMA table_info({table});")
    for col in cursor.fetchall():
        print(f"  {col[1]} ({col[2]})")

# Query recent jobs
if 'jobs' in tables:
    print("\nRecent 5 Jobs:")
    cursor.execute("SELECT * FROM jobs ORDER BY rowid DESC LIMIT 5;")
    cols = [col[0] for col in cursor.description]
    for row in cursor.fetchall():
        print(dict(zip(cols, row)))

# Query recent comics
if 'comics' in tables:
    print("\nRecent 5 Comics:")
    cursor.execute("SELECT * FROM comics ORDER BY rowid DESC LIMIT 5;")
    cols = [col[0] for col in cursor.description]
    for row in cursor.fetchall():
        print(dict(zip(cols, row)))

conn.close()
