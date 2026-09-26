export const EXTRACT_URL = 'http://127.0.0.1:8000/extract-and-match';

export async function extractAndMatch(files) {
  const body = new FormData();
  files.forEach((file, index) => {
    const extension = { 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp' }[file.type];
    body.append('files', file, `flyer-${index + 1}.${extension}`);
  });
  let response;
  try {
    // Let the browser supply the multipart boundary. Never retry paid work automatically.
    response = await fetch(EXTRACT_URL, { method: 'POST', body });
  } catch {
    throw new Error('Could not reach the recipe API. Check that Python is running on 127.0.0.1:8000.');
  }
  let data;
  try { data = await response.json(); } catch {
    throw new Error(`The recipe API returned an unreadable response (HTTP ${response.status}).`);
  }
  if (!response.ok) {
    const detail = typeof data?.detail === 'string' ? data.detail
      : Array.isArray(data?.detail) ? data.detail.map(item => item.msg).filter(Boolean).join('; ') : '';
    throw new Error(detail || `Recipe request failed (HTTP ${response.status}).`);
  }
  if (!Array.isArray(data?.items) || !Array.isArray(data?.matched_recipes)
      || data.matched_recipes.some(recipe => !recipe || typeof recipe.title !== 'string')) {
    throw new Error('The recipe API returned an unexpected result format.');
  }
  return data;
}

export function recipeUrl(link) {
  if (typeof link !== 'string' || !link.trim()) return null;
  const value = link.trim();
  try {
    const url = new URL(/^[a-z][a-z\d+.-]*:/i.test(value) ? value : `https://${value}`);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}
