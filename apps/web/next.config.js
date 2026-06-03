/** @type {import('next').Config} */
module.exports = {
  output: 'standalone',
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
