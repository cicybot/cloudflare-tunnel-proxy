// src/worker.js
var worker_default = {
  async fetch(request, env, ctx) {
    const { PROXY_URL } = env;
    if (!PROXY_URL) {
      return new Response("PROXY_URL is not configured", { status: 500 });
    }
    const url = new URL(request.url);
    const target = new URL(PROXY_URL);
    target.pathname = url.pathname;
    target.search = url.search;
    const proxyRequest = new Request(target.toString(), {
      method: request.method,
      headers: request.headers,
      body: request.body,
      redirect: "manual"
      // do not auto-follow; preserve behavior
    });
    const response = await fetch(proxyRequest);
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers
    });
  }
};
export {
  worker_default as default
};
//# sourceMappingURL=worker.js.map
