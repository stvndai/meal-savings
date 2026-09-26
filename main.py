"""
FastAPI wrapper around: image uploads -> extract_flyer_folder() -> SQLite
recipe matching.
 
Run with:
    pip install fastapi uvicorn python-multipart
    uvicorn main:app --reload
 
Then POST one or more image files to /extract-and-match (multipart form,
field name "files"). Order matters for page numbering -- files are written
out and re-sorted by filename inside extract_flyer_folder, same as its
existing folder-based usage, so name/order your uploads accordingly.
 
This is a stand-in for your planned multi-page session architecture
(create session / upload pages / trigger processing / poll). Since flyer
extraction can take a few seconds per page even with concurrent workers,
you'll likely want to move this to the async job + polling pattern once
you're testing with real multi-page flyers rather than a quick local check.
"""
 
import shutil
import tempfile
from pathlib import Path
import os
 
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
 
from flyerextractor import IMAGE_EXTENSIONS, extract_flyer_folder
from pipeline import match_flyer_result
from recipe_reranker import RecipeRerankError

from dotenv import load_dotenv

load_dotenv()
 
app = FastAPI(title="Flyer Deal Matcher")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173", "http://localhost:5173",
        "http://127.0.0.1:4173", "http://localhost:4173",
    ],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)
 
DB_PATH = "recipes.db"  # move to an env var / config before deploying
TOP_K = 50  # SQLite candidate pool; OpenRouter selects the best five.
 
 
@app.post("/extract-and-match")
async def extract_and_match_endpoint(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
 
    with tempfile.TemporaryDirectory() as tmp_dir:
        for i, upload in enumerate(files, start=1):
            suffix = Path(upload.filename or "").suffix.lower()
            if suffix not in IMAGE_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {upload.filename}",
                )
            # Zero-padded prefix keeps upload order intact regardless of
            # original filenames -- extract_flyer_folder sorts by filename.
            dest = Path(tmp_dir) / f"page_{i:02d}{suffix}"
            with open(dest, "wb") as f:
                shutil.copyfileobj(upload.file, f)
 
        try:
            result = extract_flyer_folder(tmp_dir)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
 
    try:
        return match_flyer_result(result, DB_PATH, top_k=TOP_K)
    except RecipeRerankError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
 
 
@app.get("/health")
async def health():
    return {"status": "ok"}
