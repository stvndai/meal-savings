"""
Glue layer: takes the LLM's structured flyer extraction and feeds the
extracted item names into the SQLite FTS5 recipe matcher.
 
Swap the import below for whichever extraction module is your actual
production path (e.g. extract_openrouter_gemini.py) -- the only
requirement is that it returns something with a `.items` list where
each item has a `.name` attribute, matching the FlyerItem schema.
"""

from flyerextractor import FlyerItem, FlyerPage, MultiPageFlyerItem, MultiPageFlyerResult
from recipe_sqlite import match_recipes_to_flyer_sql
from recipe_reranker import rerank_recipe_candidates
import os
from dotenv import load_dotenv

load_dotenv()

def get_item_names(result: FlyerPage | MultiPageFlyerResult) -> list[str]:
    """
    Pulls just the product names out of the LLM's structured output --
    that's all match_recipes_to_flyer_sql needs. Prices/unit info aren't
    used for matching, only for the savings calculation later.
 
    extract_flyer_folder() already dedups by (normalized name, price)
    before returning, so for MultiPageFlyerResult this is mostly a
    formality -- but de-duping again here is cheap and protects this
    function if it's ever called with FlyerPage (single-page, no dedup
    pass applied) or a result built some other way.
    """
    
    names = [item.product_name for item in result.items]
    return list(dict.fromkeys(names))

def match_flyer_result(
    result: FlyerPage | MultiPageFlyerResult,
    db_path: str = os.environ.get("RECIPE_DB_PATH"),
    top_k: int = 50,
) -> dict:
    """
    Takes an already-produced extraction result (i.e. runs AFTER your
    extraction + cross-page merge/dedup step, not instead of it) and
    retrieves top_k SQLite candidates, then makes one OpenRouter call to
    select the best five (or all candidates if fewer than five are found).
    """
    item_names = get_item_names(result)
    candidates = match_recipes_to_flyer_sql(item_names, db_path, top_k=top_k)
    matches = rerank_recipe_candidates(candidates, item_names)
 
    return {
        "items": [item.model_dump() for item in result.items],
        "matched_recipes": matches,
    }
