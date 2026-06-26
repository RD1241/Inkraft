import sqlite3
import os

db_path = "core/character_memory.db"
if not os.path.exists(db_path):
    db_path = "../core/character_memory.db"

print(f"Checking character database at {db_path}...")
if not os.path.exists(db_path):
    print("Database file does not exist!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [r[0] for r in cursor.fetchall()]
print(f"Tables: {tables}")

# Print character_profiles
if 'character_profiles' in tables:
    print("\nProfiles inside character_profiles:")
    cursor.execute("SELECT * FROM character_profiles;")
    cols = [col[0] for col in cursor.description]
    for row in cursor.fetchall():
        print(dict(zip(cols, row)))

# Print character_design_sheets
if 'character_design_sheets' in tables:
    print("\nSheets inside character_design_sheets:")
    cursor.execute("SELECT * FROM character_design_sheets;")
    cols = [col[0] for col in cursor.description]
    for row in cursor.fetchall():
        print(dict(zip(cols, row)))

conn.close()
