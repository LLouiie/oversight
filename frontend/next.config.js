/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const rawTarget = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:5001';
    // Flask dev server binds on IPv4 by default. Normalize localhost to 127.0.0.1
    // so Next.js proxy does not resolve to ::1 and fail with ECONNREFUSED.
    const target = rawTarget.replace('://localhost', '://127.0.0.1');
    return [
      {
        source: '/api/:path*',
        destination: `${target}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
