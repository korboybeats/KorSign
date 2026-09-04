import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const source = await readFile(new URL('./worker.js', import.meta.url), 'utf8');
const { default: worker } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
let forwarded;
const env = { UPDATER: { async fetch(url, init) { forwarded = new Request(url, {...init, duplex:'half'}); return new Response('ok'); } } };
for (const path of ['/admin', '/files/../certificate.p12', '/ryuksign/sign']) {
  assert.equal((await worker.fetch(new Request('https://example.test' + path), env)).status, 404);
}
assert.equal((await worker.fetch(new Request('https://example.test/ryuksign/sign', {method:'POST', body:'x', headers:{'content-length':'2097153'}}), env)).status, 413);
assert.equal((await worker.fetch(new Request('https://example.test/health', {headers:{cookie:'secret', authorization:'secret'}}), env)).status, 200);
assert.equal(forwarded.url, 'http://127.0.0.1:8080/health');
assert.equal(forwarded.headers.get('cookie'), null);
assert.equal(forwarded.headers.get('authorization'), null);
assert.equal(forwarded.headers.get('accept-encoding'), 'identity');
assert.equal((await worker.fetch(new Request('https://example.test/ryuksign/sign', {method:'POST', body:'x', headers:{'content-length':'1'}}), env)).status, 200);
assert.equal(await forwarded.text(), 'x');
assert.equal((await worker.fetch(new Request('https://example.test/health'), {UPDATER:{fetch(){throw new Error('offline');}}})).status, 503);
console.log('PASS: Worker route/upload limits, private forwarding, stripped credentials');
