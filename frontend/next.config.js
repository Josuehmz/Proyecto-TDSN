/** @type {import('next').NextConfig} */
const backendBase =
  (process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8000").replace(
    /\/$/,
    "",
  );

const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async rewrites() {
    return [
      { source: "/auth/:path*", destination: `${backendBase}/auth/:path*` },
      { source: "/query", destination: `${backendBase}/query` },
    ];
  },
};

module.exports = nextConfig;
