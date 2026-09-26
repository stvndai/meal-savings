"""
Recipe database + full-text search index, using a two-table SQLite
structure:
 
  - `recipes`: the source of truth, one row per recipe with everything
    you'll want to display later (title, ingredients, directions, link).
  - `recipes_fts`: an FTS5 virtual table that indexes only the cleaned
    ingredient text for searching. `content='recipes'` tells FTS5 not
    to duplicate that text -- it stores the search index but reads
    actual column values from `recipes` when needed, keyed by rowid.
    This avoids storing ingredient text twice, which matters at ~2M rows.
 
Also reads the CSV in chunks instead of loading all ~2M rows into
memory at once: pandas' `chunksize` returns an iterator of smaller
DataFrames, each inserted into SQLite and then discarded, so peak
memory stays roughly constant regardless of the full dataset size.
 
Requires: pip install pandas   (sqlite3 ships with Python's stdlib)
"""
 
import ast
import re
import sqlite3
from pathlib import Path
import os 
 
import pandas as pd
from dotenv import load_dotenv

load_dotenv() 

 
def parse_ner_column(raw_value) -> list[str]:
    if not isinstance(raw_value, str):
        return []
    try:
        parsed = ast.literal_eval(raw_value)
        return [str(item).strip().lower() for item in parsed if str(item).strip()]
    except (ValueError, SyntaxError):
        return []
 

 
def build_recipe_db(
    csv_path: str,
    db_path: str,
    chunk_size: int = 10_000,
    sample_size: int | None = None,
) -> None:
    """
    sample_size: cap total rows processed, for fast local iteration
    while testing. None processes the entire file.
    """
    if Path(db_path).exists():
        Path(db_path).unlink()  # rebuild fresh each time, so this is idempotent
 
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE recipes (
            id INTEGER PRIMARY KEY,
            title TEXT,
            link TEXT,
            ingredient_text TEXT
        )
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE recipes_fts USING fts5(
            ingredient_text,
            content='recipes',
            content_rowid='id'
        )
    """)
 
    total_inserted = 0
    total_dropped = 0
 
    for chunk in pd.read_csv(csv_path, chunksize=chunk_size):
        if sample_size is not None and total_inserted >= sample_size:
            break
 
        chunk["ingredient_text"] = (
            chunk["NER"].apply(parse_ner_column).apply(lambda items: ", ".join(items))
        )
        before = len(chunk)
        chunk = chunk[chunk["ingredient_text"].str.len() > 0]
        total_dropped += before - len(chunk)
 
        if sample_size is not None:
            chunk = chunk.iloc[: sample_size - total_inserted]
 
        rows = list(
            chunk[["title", "link", "ingredient_text"]]
            .itertuples(index=False, name=None)
        )
        conn.executemany(
            "INSERT INTO recipes (title, link, ingredient_text) VALUES (?, ?, ?)",
            rows,
        )
        total_inserted += len(rows)
 
    # Populate the FTS index from the recipes table in one pass, matching
    # rowids -- the standard pattern for bulk-loading an external-content
    # FTS5 table after the content table itself is already populated.
    conn.execute("""
        INSERT INTO recipes_fts (rowid, ingredient_text)
        SELECT id, ingredient_text FROM recipes
    """)
 
    conn.commit()
    conn.close()
 
    size_mb = Path(db_path).stat().st_size / 1e6
    print(f"Built {db_path}: {total_inserted} recipes inserted, "
          f"{total_dropped} dropped (empty NER), {size_mb:.2f} MB")
 
 
def build_match_query(flyer_item_names: list[str]) -> str:
    """
    Explicit OR is required: space-separated terms default to AND in
    FTS5, which would otherwise demand every single word appear in the
    same recipe.

    MATCH parameters are still parsed as FTS5 expressions. Extract words
    and quote each one so flyer punctuation and search operators cannot
    become query syntax. Keep the original extracted names unchanged.
    """
    words = set()
    for item in flyer_item_names:
        words.update(re.findall(r"[^\W_]+", item.lower()))
    return " OR ".join(f'"{word}"' for word in sorted(words))
 
 
def match_recipes_to_flyer_sql(
    flyer_item_names: list[str],
    db_path: str,
    top_k: int = 20,
) -> list[dict]:
    query = build_match_query(flyer_item_names)
    if not query:
        return []
 
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        """
        SELECT r.id, r.title, r.link, r.ingredient_text, bm25(recipes_fts) AS score
        FROM recipes_fts
        JOIN recipes r ON r.id = recipes_fts.rowid
        WHERE recipes_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, top_k),
    )
    results = [
        {"id": recipe_id, "title": t, "link": l, "ingredient_text": ingredients, "score": s}
        for recipe_id, t, l, ingredients, s in cursor.fetchall()
    ]
    conn.close()
    return results



if __name__ == "__main__":
    # --- Real usage: uncomment once you've got the dataset ---
    csv_path = os.environ.get("RECIPE_DB_PATH")
    db_path = "recipes.db"
    build_recipe_db(csv_path, db_path, sample_size=500_000)

    this_weeks_flyer = ["Bananas", "Chicken Breast, boneless", "Bread, whole wheat"]
    matches = match_recipes_to_flyer_sql(this_weeks_flyer, db_path, top_k=5)

    print("\nTop matches for this week's flyer:")
    for m in matches:
        print(f"  {m['title']}  (bm25 score: {m['score']:.3f})  {m['link']}")
