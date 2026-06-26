import sqlite3
import os

db_path = "core/jobs.db"
char_db_path = "core/character_memory.db"

with open("scratch/sqlite_schema.txt", "w", encoding="utf-8") as f:
    f.write("=== JOBS DATABASE SCHEMA ===\n")
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
        for table in cursor.fetchall():
            if table[0]:
                f.write(table[0] + ";\n\n")
        conn.close()
    else:
        f.write("jobs.db does not exist!\n")

    f.write("\n=== CHARACTER DATABASE SCHEMA ===\n")
    if os.path.exists(char_db_path):
        conn = sqlite3.connect(char_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
        for table in cursor.fetchall():
            if table[0]:
                f.write(table[0] + ";\n\n")
        conn.close()
    else:
        f.write("character_memory.db does not exist!\n")
