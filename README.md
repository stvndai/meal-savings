# Meal Savings

Meal Savings turns grocery flyer images into recipe recommendations. It uses AI
to extract food products and prices from one or more flyer pages, searches a
local SQLite recipe database for relevant meals, and uses a second AI pass to
select and explain the five best matches.

The project includes a FastAPI backend and a React frontend.

## How it works

```text
Flyer images
    ↓
Gemini extraction through OpenRouter
    ↓
Validated and deduplicated sale items
    ↓
SQLite FTS5 recipe search (top 50 candidates)
    ↓
DeepSeek reranking through OpenRouter
    ↓
Up to five recipe recommendations
```

1. The frontend uploads flyer pages to `POST /extract-and-match` in their
   selected order.
2. FastAPI stores the uploads in a temporary directory for the duration of the
   request.
3. `flyerextractor.py` resizes and converts each image to JPEG, then sends pages
   concurrently to `google/gemini-2.5-flash-lite` through OpenRouter.
4. Pydantic validates the extracted product name, price, unit information, and
   original price. Duplicate products with the same normalized name and price
   are removed across pages.
5. `recipe_sqlite.py` uses SQLite FTS5 and BM25 ranking to retrieve 50 recipe
   candidates containing the extracted ingredients.
6. `recipe_reranker.py` sends those candidates to
   `deepseek/deepseek-v4.1-flash`, which chooses up to five recipes and provides
   a short reason for each choice.
7. The API returns both the extracted flyer items and the ranked recipes to the
   frontend.

## Project structure

```text
meal-savings/
├── main.py                 # FastAPI application and upload endpoint
├── flyerextractor.py       # Image preparation and flyer item extraction
├── pipeline.py             # Connects extraction, search, and reranking
├── recipe_sqlite.py        # Recipe database builder and FTS5 search
├── recipe_reranker.py      # AI recipe selection and explanations
├── frontend/               # React, Vite, and Tailwind web interface
├── docs/prompts/            # Markdown copies of flyer extraction prompts
├── scripts/                # Development experiments and manual utilities
├── flyers/                 # Local sample flyer images (Git-ignored)
└── jsons/                  # Local JSON data (Git-ignored)
```

Local `.env` files, CSV datasets, SQLite databases, flyer images, generated
frontend files, and Python caches are excluded by `.gitignore`.

## Requirements

- Python 3.10 or newer
- Node.js and npm
- An OpenRouter API key
- A local SQLite recipe database named `recipes.db` in the project root

The app is tested using a database created from the following dataset https://www.kaggle.com/datasets/wilmerarltstrmberg/recipe-dataset-over-2m?resource=download

The Python backend uses FastAPI, Uvicorn, Requests, Pillow, Pydantic,
python-dotenv, python-multipart, and pandas (for building the recipe database).

## Backend setup

From the repository root, create and activate a virtual environment, then
install the backend packages:

```sh
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install fastapi uvicorn python-multipart requests pillow pydantic python-dotenv pandas
```

Provide the following environment variable through your local environment or
an untracked `.env` file:

```text
OPENROUTER_API_KEY=your_openrouter_key
```

Place the recipe database at `recipes.db`, then start the API from the project
root:

```sh
uvicorn main:app --reload
```

The backend runs at `http://127.0.0.1:8000` by default.

### API endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/health` | Returns the server status |
| `POST` | `/extract-and-match` | Accepts one or more flyer images in multipart field `files` |
| `GET` | `/docs` | FastAPI's interactive API documentation |

Supported upload extensions are JPG, JPEG, PNG, WebP, and GIF. The order of
the uploaded files determines their page numbers.

Example response shape:

```json
{
  "items": [
    {
      "product_name": "Chicken breast",
      "price": 3.98,
      "unit_size": null,
      "unit_type": null,
      "original_price": null,
      "page_number": 1
    }
  ],
  "matched_recipes": [
    {
      "id": 123,
      "title": "Chicken dinner",
      "link": "https://example.com/recipe",
      "ingredient_text": "chicken, potatoes, carrots",
      "score": -2.5,
      "rank": 1,
      "reason": "Chicken is on sale and forms the main part of this meal."
    }
  ]
}
```

## Frontend setup

Start the backend first. In a second terminal:

```sh
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. You can select, paste, or drag and drop up to ten
flyer images, preview their page order, and request recipe suggestions.

To create a production frontend build:

```sh
npm run build
```

The frontend currently sends requests to `http://127.0.0.1:8000`. Update
`frontend/src/api.js` and the CORS origins in `main.py` if the frontend or API
is hosted elsewhere.

## Recipe database

`recipe_sqlite.py` builds a database from a recipe CSV containing `title`,
`link`, and `NER` columns. It converts the `NER` ingredient data into searchable
text and creates an external-content SQLite FTS5 index.

The running API currently reads `recipes.db` from the repository root. CSV and
database files are intentionally not committed because they may be large.

## Prompt documentation

Reference copies of the flyer extraction prompts are stored in:

- [`docs/prompts/flyerextractor-system-prompt.md`](docs/prompts/flyerextractor-system-prompt.md)
- [`docs/prompts/flyerextractor-multi-page-system-prompt.md`](docs/prompts/flyerextractor-multi-page-system-prompt.md)

The prompts actually used at runtime are the constants in `flyerextractor.py`.
Keep the source and Markdown copies synchronized when editing them.

## Development scripts

The `scripts/` directory contains experiments and manual utilities:

- `claudetest.py` — Claude flyer extraction experiment
- `googleflyertest.py` — Gemini flyer extraction experiment
- `csv_format.py` — local recipe CSV conversion
- `test_request.py` — manual request using sample flyers

Run these from the repository root because some use root-relative file paths.

## Current limitations

- Extraction and reranking happen synchronously during one HTTP request and may
  take several seconds.
- Each uploaded flyer page makes an extraction request, and reranking makes one
  additional OpenRouter request. These calls can consume paid credits.
- Failed OpenRouter reranking requests return an API error; there is no retry or
  automatic BM25-only fallback.
- The recipe database must already exist locally before starting the API.
