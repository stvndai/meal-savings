"""
Baseline flyer extraction script — Claude API only.

Purpose: a minimal, single-file version of the extraction step so you can
measure cost/latency/accuracy against your full pipeline (FastAPI + Pydantic
+ normalization) and quantify what the extra engineering actually buys you.

Usage:
    export ANTHROPIC_API_KEY=sk-...
    python flyer_extract_baseline.py path/to/flyer.jpg
    python flyer_extract_baseline.py path/to/flyer.jpg --model haiku
"""

import argparse
import base64
import json
import mimetypes
import sys
import time
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from pydantic import BaseModel, ValidationError
import os
from dotenv import load_dotenv

load_dotenv()

MODEL_ALIASES = {
    "sonnet": "claude-sonnet-5",
    "haiku": "claude-haiku-4-5-20251001",
}

# Same rule you already discovered the hard way: the model must NOT compute
# per-unit price from multi-unit deals. That math happens in Python below.
SYSTEM_PROMPT = """You extract grocery flyer items from an image into structured data.

For each item, capture EXACTLY what is printed:
- name: the product name as shown
- quantity: the deal quantity as printed (e.g. "2", "1", "3"). If the flyer
  shows "2/$5", quantity is 2, NOT 1.
- sale_price: the TOTAL sale price for that quantity, as printed (e.g. if the
  flyer says "2/$5", sale_price is 5.00, not 2.50). Never divide this.
- original_price: the regular/was price if shown, per the same quantity basis
  as sale_price. Use null if not shown.
- unit: the unit of sale if specified (e.g. "lb", "kg", "each", "ea"). Use
  null if not specified.

Do NOT perform any division, unit-price math, or per-item price derivation.
Report numbers exactly as printed on the flyer. If a value is unclear or
missing, use null rather than guessing.

Return your answer ONLY via the extract_flyer_items tool call. Do not include
any other text.
"""

EXTRACT_TOOL = {
    "name": "extract_flyer_items",
    "description": "Return the structured list of items found on the flyer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "quantity": {"type": "number"},
                        "sale_price": {"type": "number"},
                        "original_price": {"type": ["number", "null"]},
                        "unit": {"type": ["string", "null"]},
                    },
                    "required": ["name", "quantity", "sale_price"],
                },
            }
        },
        "required": ["items"],
    },
}


class FlyerItem(BaseModel):
    name: str
    quantity: float
    sale_price: float
    original_price: Optional[float] = None
    unit: Optional[str] = None

    @property
    def unit_price(self) -> Optional[float]:
        """Derived in Python, never by the LLM."""
        if self.quantity and self.quantity > 0:
            return round(self.sale_price / self.quantity, 2)
        return None


class FlyerExtraction(BaseModel):
    items: list[FlyerItem]


def encode_image(path: Path) -> tuple[str, str]:
    media_type, _ = mimetypes.guess_type(path)
    if media_type is None:
        media_type = "image/jpeg"
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return data, media_type


def extract_flyer(image_path: Path, model: str) -> tuple[FlyerExtraction, dict]:
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    image_data, media_type = encode_image(image_path)

    start = time.monotonic()
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "tool", "name": "extract_flyer_items"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract every item on this flyer.",
                    },
                ],
            }
        ],
    )
    elapsed = time.monotonic() - start

    tool_use_block = next(
        (b for b in response.content if b.type == "tool_use"), None
    )
    if tool_use_block is None:
        raise RuntimeError("Model did not return a tool_use block.")

    try:
        extraction = FlyerExtraction.model_validate(tool_use_block.input)
    except ValidationError as e:
        raise RuntimeError(f"Schema validation failed: {e}") from e

    metrics = {
        "model": model,
        "elapsed_seconds": round(elapsed, 2),
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "item_count": len(extraction.items),
    }
    return extraction, metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Path to flyer image")
    parser.add_argument(
        "--model",
        default="sonnet",
        help="Model alias (sonnet, haiku) or a full model ID",
    )
    args = parser.parse_args()

    if not args.image.exists():
        print(f"File not found: {args.image}", file=sys.stderr)
        sys.exit(1)

    model = MODEL_ALIASES.get(args.model, args.model)

    try:
        extraction, metrics = extract_flyer(args.image, model)
    except Exception as e:
        print(f"Extraction failed: {e}", file=sys.stderr)
        sys.exit(1)

    for item in extraction.items:
        unit_price = item.unit_price
        unit_price_str = f"${unit_price:.2f}" if unit_price is not None else "n/a"
        print(
            f"{item.name} | qty: {item.quantity} | "
            f"sale: ${item.sale_price:.2f} | "
            f"orig: {'$' + format(item.original_price, '.2f') if item.original_price else 'n/a'} | "
            f"unit: {item.unit or 'n/a'} | "
            f"derived unit price: {unit_price_str}"
        )

    print("\n--- run metrics ---")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
