import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { runInNewContext } from 'node:vm';

const source = await readFile(new URL('../public/sw.js', import.meta.url), 'utf8');

for (const path of ['data/tauron.json', 'assets/index-test.js']) {
  test(`service worker caches ${path} even when the response is consumed before cache opens`, async () => {
    const handlers = {};
    const pending = [];
    let respond, openCache, saved;
    const opened = new Promise(resolve => { openCache = resolve; });
    const body = path.endsWith('.json') ? '{"matches":[]}' : 'console.log("app");';
    runInNewContext(source, {
      self: {
        location: new URL('https://example.com/kiedysiatka/sw.js'),
        addEventListener: (name, handler) => { handlers[name] = handler; }
      },
      URL, Response,
      fetch: async () => new Response(body),
      caches: { match: async () => undefined, open: () => opened }
    });
    const request = { method: 'GET', url: 'https://example.com/kiedysiatka/' + path, mode: 'cors' };
    handlers.fetch({
      request,
      respondWith: promise => { respond = promise; },
      waitUntil: promise => { pending.push(promise); }
    });
    const response = await respond;
    assert.equal(await response.text(), body);
    openCache({ put: async (key, copy) => { saved = await copy.text(); } });
    await Promise.all(pending);
    // Also flush the old fire-and-forget implementation when checking regressions.
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(saved, body);
    assert.equal(pending.length, 1, 'cache write extends the fetch event lifetime');
  });
}
