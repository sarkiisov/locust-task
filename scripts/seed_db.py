import sqlite3
import random
import string
from pathlib import Path
import argparse
import sys

def random_word(n=8):
    return "".join(random.choices(string.ascii_lowercase, k=n))

def main():
    parser = argparse.ArgumentParser(description="Seed terms into existing SQLite database.")
    parser.add_argument("--db", required=True, help="Path to the existing SQLite database file")
    parser.add_argument("--count", type=int, default=10000, help="Number of terms to insert (default: 10000)")
    args = parser.parse_args()

    db_path = Path(args.db)
    terms_count = args.count

    if not db_path.exists():
        print(f"[ERROR] Database file '{db_path}' not found. Make sure the application has created it.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='terms';")
    if cursor.fetchone() is None:
        print(f"[ERROR] Table 'terms' not found in the database '{db_path}'. Ensure the application created it.", file=sys.stderr)
        conn.close()
        sys.exit(1)

    cursor.execute("DELETE FROM terms;")
    conn.commit()
    print(f"[INFO] Table 'terms' cleared.")

    data = [(f"{i}", f"description {i}") for i in range(terms_count)]
    cursor.executemany("INSERT INTO terms (keyword, description) VALUES (?, ?);", data)
    conn.commit()
    conn.close()

    print(f"[INFO] Inserted {terms_count} terms into the table 'terms' in database '{db_path}'.")


if __name__ == "__main__":
    main()
