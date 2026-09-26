# Gather frontend

Vite + React + Tailwind CSS. A beige flyer-to-recipe interface with clipboard paste, multi-image uploads, drag-and-drop, image previews, and recipe suggestions from the Python API. No sidebar or chat.

```sh
cd frontend
npm install
npm run dev
```

Production check: `npm run build`. Preview the build: `npm run preview`.

Add up to 10 JPG, PNG, or WebP images (10 MB each). Use the Paste images button, Ctrl+V / Command+V, drag-and-drop, or Choose images. Clipboard-button support depends on browser permissions; keyboard paste and file selection provide alternatives. Remove individual pages with their X buttons.

Clicking Find recipe suggestions sends one multipart POST to `http://127.0.0.1:8000/extract-and-match`, with each image under the `files` field. Start the Python API yourself before submitting. This runs the backend's extraction and reranking calls and can spend OpenRouter credits. There are no automatic retries. API errors appear on the page and selected images remain available.

The frontend displays `matched_recipes` from the API, including titles, recommendation reasons, ingredients, and original recipe links. Food illustrations are decorative, not actual recipe photos. No API keys belong in the frontend. Vite environment-file loading stays disabled.

Development uses port 5173; preview uses 4173. FastAPI allows these origins on localhost and 127.0.0.1. Restart Python to load the CORS change. Hosting elsewhere requires updating the API URL and allowed origins.

Offline API tests (all fetch calls mocked): `node --test src/api.test.js`.
