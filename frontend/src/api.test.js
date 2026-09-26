import test from 'node:test';
import assert from 'node:assert/strict';
import { EXTRACT_URL, extractAndMatch, recipeUrl } from './api.js';

test('posts every image as files and returns the API recipes', async t => {
  const result = { items: [{ product_name: 'Chicken' }], matched_recipes: [{ id: 42, title: 'Chicken soup' }] };
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, EXTRACT_URL);
    assert.equal(options.method, 'POST');
    assert.equal(options.headers, undefined);
    const uploads = options.body.getAll('files');
    assert.equal(uploads.length, 2);
    assert.equal(uploads[0].name, 'flyer-1.png');
    assert.equal(uploads[1].name, 'flyer-2.jpg');
    assert.equal(await uploads[0].text(), 'first');
    assert.equal(await uploads[1].text(), 'second');
    return Response.json(result);
  });
  assert.deepEqual(await extractAndMatch([
    new File(['first'], 'clipboard', { type: 'image/png' }),
    new File(['second'], 'page.jpeg', { type: 'image/jpeg' }),
  ]), result);
});

test('surfaces backend failures without retrying', async t => {
  const mock = t.mock.method(globalThis, 'fetch', async () => Response.json({ detail: 'Ranking failed' }, { status: 502 }));
  await assert.rejects(extractAndMatch([]), /Ranking failed/);
  assert.equal(mock.mock.callCount(), 1);
});

test('handles network errors and malformed success responses', async t => {
  const mock = t.mock.method(globalThis, 'fetch', async () => { throw new TypeError('Failed to fetch'); });
  await assert.rejects(extractAndMatch([]), /127.0.0.1:8000/);
  mock.mock.mockImplementation(async () => Response.json({ unexpected: true }));
  await assert.rejects(extractAndMatch([]), /unexpected result format/);
  mock.mock.mockImplementation(async () => Response.json({ items: [], matched_recipes: [] }));
  assert.deepEqual(await extractAndMatch([]), { items: [], matched_recipes: [] });
});

test('recipe links accept web URLs and reject executable schemes', () => {
  assert.equal(recipeUrl('example.com/recipe'), 'https://example.com/recipe');
  assert.equal(recipeUrl('https://example.com/recipe'), 'https://example.com/recipe');
  assert.equal(recipeUrl('javascript:alert(1)'), null);
  assert.equal(recipeUrl('data:text/html,test'), null);
  assert.equal(recipeUrl(null), null);
});
