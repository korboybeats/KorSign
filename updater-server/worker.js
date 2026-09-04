export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === 'POST' && url.pathname === '/ryuksign/sign') {
      const length = Number(request.headers.get('content-length'));
      if (!Number.isSafeInteger(length) || length <= 0 || length > 2097152) {
        return new Response('Invalid upload size', { status: 413 });
      }
    } else if (!(['GET', 'HEAD'].includes(request.method) &&
      (url.pathname === '/health' || /^\/files\/[a-f0-9]{48}\/(app\.ipa|manifest\.plist)$/.test(url.pathname)))) {
      return new Response('Not found', { status: 404 });
    }
    const headers = new Headers(request.headers);
    headers.delete('cookie');
    headers.delete('authorization');
    headers.set('accept-encoding', 'identity');
    try {
      return await env.UPDATER.fetch('http://127.0.0.1:8080' + url.pathname, {
        method: request.method, headers, body: request.body, redirect: 'manual'
      });
    } catch {
      return Response.json({ error: 'unavailable' }, { status: 503 });
    }
  }
};
