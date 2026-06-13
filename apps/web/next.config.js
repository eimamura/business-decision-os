/** @type {import('next').Config} */
module.exports = {
  output: 'standalone',
  // Disable Next.js gzip compression so SSE text_delta chunks are forwarded
  // incrementally to the browser. Next dev applies gzip at the HTTP layer after
  // route handlers return a ReadableStream, which re-buffers the entire SSE
  // body into a single chunk — defeating the streaming route handler in
  // apps/web/app/api/v1/sessions/[sessionId]/stream/route.ts (T-604 fix).
  // Trade-off: static assets are no longer gzip-compressed by the Next dev
  // server; this is acceptable for the dev-only stack (nginx/CDN handles
  // compression in production; the standalone build uses `next start` which
  // does not apply this config option the same way).
  compress: false,
  async rewrites() {
    const apiUrl = process.env.API_URL ?? 'http://localhost:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};
