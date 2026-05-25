/** @type {import('next').NextConfig} */
const BACKEND = process.env.BACKEND_URL || "http://localhost:18000";

const nextConfig = {
  async rewrites() {
    return [
      { source: "/api/backend/:path*", destination: `${BACKEND}/api/:path*` },
      { source: "/sse/:path*", destination: `${BACKEND}/sse/:path*` },
    ];
  },
};

module.exports = nextConfig;
