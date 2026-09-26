"""
Flyer extraction via OpenRouter -> Gemini 2.5 Flash.

Mirrors the shape of extract_starter.py / flyer_extract_baseline.py so this
can be dropped in as another --model option in the benchmark harness.

Usage:
    export OPENROUTER_API_KEY=sk-or-...
    python extract_openrouter_gemini.py path/to/flyer_page.jpg
"""

import base64
import io
import json
import mimetypes
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
 
import requests
from PIL import Image
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.5-flash-lite"  # check openrouter.ai/models for the current slug


# Longest edge to resize to before sending. Flyers are dense but not
# fine-print-dense - 1568px is comfortably above what's needed to read
# product names, prices, and unit sizes, and is roughly the point past which
# vision models tile/tokenize more expensively without extra useful signal.
# Tune this down (e.g. 1024) if quality holds up in your benchmark and you
# want to cut cost further.
MAX_IMAGE_EDGE = 1568
JPEG_QUALITY = 85  # re-encoding as JPEG also shrinks payload vs. source PNGs
 
# How many pages to process concurrently. Bounded mainly by OpenRouter/Gemini
# rate limits rather than anything on your end - 4-6 is a safe starting point.
MAX_WORKERS = 5
 

class FlyerItem(BaseModel):
    product_name: str
    price: float
    unit_size: Optional[str] = None  # e.g. "500g", "12x355ml"
    unit_type: Optional[str] = None  # e.g. "g", "ml", "each"
    original_price: Optional[float] = None
 
    @property
    def unit_price(self) -> Optional[float]:
        """Deterministic in code, never trust the LLM's arithmetic."""
        if not self.unit_size or not self.unit_type:
            return None
        try:
            qty = float("".join(c for c in self.unit_size if c.isdigit() or c == "."))
            return round(self.price / qty, 4) if qty else None
        except ValueError:
            return None
 
 
class FlyerPage(BaseModel):
    items: list[FlyerItem] = Field(default_factory=list)
 
 
SYSTEM_PROMPT = """You extract structured data from a grocery store flyer image.
 
Return ONLY valid JSON matching this schema, no markdown fences, no commentary:
{
  "items": [
    {
      "product_name": string,
      "price": number,
      "unit_size": string or null,   // e.g. "500g", "1L", "12x355ml"
      "unit_type": string or null,   // e.g. "g", "ml", "each"
      "original_price": number or null,  // pre-discount price if shown
    }
  ]
}
Simplfy the prodcut to what it is rather than the product name.
Do not compute unit prices or discounts yourself - just extract the raw
values printed on the flyer. If a field isn't present, use null.
Skip items that are not food ingredients."""
 
 
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
 
# Multi-page flyers can push a single request past provider image-count or
# payload-size limits. Gemini via OpenRouter comfortably handles a typical
# flyer's page count (a handful to a couple dozen), but if you hit errors on
# very large flyers, chunk pages and merge/dedup results across chunks
# instead (see the session-based design in your multi-page architecture).
MULTI_PAGE_SYSTEM_PROMPT = """You extract structured data from a multi-page grocery
store flyer. You will be shown several page images, in order, that together
make up one flyer.
 
Return ONLY valid JSON matching this schema, no markdown fences, no commentary:
{
  "items": [
    {
      "product_name": string,
      "brand": string or null,
      "price": number,
      "unit_size": string or null,   // e.g. "500g", "1L", "12x355ml"
      "unit_type": string or null,   // e.g. "g", "ml", "each"
      "original_price": number or null,  // pre-discount price if shown
      "valid_dates": string or null,
      "page_number": integer         // 1-indexed, which page this item appeared on
    }
  ]
}
 
Treat the same product repeated across pages (e.g. a front-page teaser and a
full listing inside) as SEPARATE items - do not attempt to deduplicate
yourself. Deduplication is handled downstream in code.

Simplfy the prodcut to what it is rather than the product name.
Do not compute unit prices or discounts yourself - just extract the raw
values printed on the flyer. If a field isn't present, use null.
Skip items that are not food ingredients."""
 
 
class MultiPageFlyerItem(FlyerItem):
    page_number: int
 
 
class MultiPageFlyerResult(BaseModel):
    items: list[MultiPageFlyerItem] = Field(default_factory=list)
 
 
def encode_image(path: str) -> tuple[str, str]:
    """
    Downscale the image before base64-encoding it. This is the single
    biggest lever on both cost and latency for vision API calls - a
    4000px-wide phone photo of a flyer carries far more tokens than a
    1568px version, with no gain in extraction accuracy for printed text.
    """
    img = Image.open(path)
    img = img.convert("RGB")  # drops alpha channel, needed for JPEG re-encode
 
    longest_edge = max(img.size)
    if longest_edge > MAX_IMAGE_EDGE:
        scale = MAX_IMAGE_EDGE / longest_edge
        new_size = (int(img.width * scale), int(img.height * scale))
        img = img.resize(new_size, Image.LANCZOS)
 
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return b64, "image/jpeg"
 
 
def _call_openrouter(system_prompt: str, user_content: list[dict]) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENROUTER_API_KEY in your environment")
 
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0,
        # Gemini via OpenRouter supports this for stricter JSON adherence
        "response_format": {"type": "json_object"},
    }
 
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # Optional but recommended by OpenRouter for their leaderboard/analytics:
        "HTTP-Referer": "https://your-project-url.example",
        "X-Title": "flyer-extraction-benchmark",
    }
 
    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    raw_content = data["choices"][0]["message"]["content"]
 
    # Defensive cleanup in case the model wraps JSON in fences despite instructions
    return raw_content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
 
 
def extract_flyer(image_path: str) -> FlyerPage:
    """Single-page extraction (original behavior)."""
    b64_image, mime_type = encode_image(image_path)
 
    user_content = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{b64_image}"},
        },
        {
            "type": "text",
            "text": """Extract every food ingredient product/price listing from this flyer page skip any non food ingredient.
            simplify the product name to what it is """,
        },
    ]
 
    cleaned = _call_openrouter(SYSTEM_PROMPT, user_content)
    try:
        parsed = json.loads(cleaned)
        return FlyerPage.model_validate(parsed)
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(f"Model returned unparseable output: {e}\nRaw content:\n{cleaned}")
 
 
def _extract_single_page(args: tuple[int, str]) -> tuple[int, list[MultiPageFlyerItem]]:
    """Worker for one page. Reuses the single-page prompt/schema, then
    stamps on the page number in code rather than asking the model for it -
    one less thing it can get wrong."""
    page_number, full_path = args
    page = extract_flyer(full_path)
    items = [
        MultiPageFlyerItem(**item.model_dump(), page_number=page_number)
        for item in page.items
    ]
    return page_number, items
 
 
def _normalize_name(name: str) -> str:
    return " ".join(name.lower().split())
 
 
def _dedup_items(items: list[MultiPageFlyerItem]) -> list[MultiPageFlyerItem]:
    """
    Cheap first pass at cross-page dedup: collapse items with the same
    normalized name + price, keeping the earliest page seen. This is
    intentionally simple - swap in your fuzzy-match logic (e.g. from your
    recipe matching's TF-IDF approach, or rapidfuzz) if flyers have enough
    near-duplicate naming to need it.
    """
    seen: dict[tuple[str, float], MultiPageFlyerItem] = {}
    for item in items:
        key = (_normalize_name(item.product_name), item.price)
        if key not in seen:
            seen[key] = item
    return list(seen.values())
 
 
def extract_flyer_folder(folder_path: str) -> MultiPageFlyerResult:
    """
    Process every image in a folder as SEPARATE requests, run concurrently,
    then merge + dedup the results in code.
 
    This is cheaper and faster than one big multi-image request: each call
    is small (one page's worth of image tokens, one small JSON response), so
    total latency is roughly max(page_time) instead of sum(page_time), and
    you avoid the token overhead of holding N full-size images in a single
    context. The tradeoff is the model can't directly cross-reference pages
    mid-extraction (e.g. "this is the same deal teased on page 1") - that's
    handled by the dedup pass below instead, matching the session-based
    merge design in the broader multi-page architecture.
 
    Pages are ordered by filename, so name files so they sort correctly
    (page_01.jpg, page_02.jpg, ... rather than page_1.jpg, page_2.jpg,
    page_10.jpg which would sort wrong).
    """
    filenames = sorted(
        p
        for p in os.listdir(folder_path)
        if os.path.splitext(p)[1].lower() in IMAGE_EXTENSIONS
    )
    if not filenames:
        raise ValueError(f"No images found in {folder_path}")
 
    tasks = [
        (i, os.path.join(folder_path, filename))
        for i, filename in enumerate(filenames, start=1)
    ]
 
    all_items: list[MultiPageFlyerItem] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(_extract_single_page, task): task for task in tasks}
        for future in as_completed(futures):
            page_number, full_path = futures[future]
            try:
                _, items = future.result()
                all_items.extend(items)
            except Exception as e:
                filename = os.path.basename(full_path)
                print(f"  [page {page_number} / {filename}] failed: {e}", file=sys.stderr)
 
    deduped = _dedup_items(all_items)
    return MultiPageFlyerResult(items=deduped)
 
 
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python extract_openrouter_gemini.py <image_path_or_folder>")
        sys.exit(1)
 
    target = sys.argv[1]
 
    if os.path.isdir(target):
        result = extract_flyer_folder(target)
        for item in result.items:
            print(
                f"[p{item.page_number}] {item.product_name:<30} "
                f"${item.price:<8} unit_price={item.unit_price}"
            )
        print(f"\nTotal items extracted: {len(result.items)}")
    else:
        page = extract_flyer(target)
        for item in page.items:
            print(f"{item.product_name:<30} ${item.price:<8} unit_price={item.unit_price}")
        print(f"\nTotal items extracted: {len(page.items)}")
