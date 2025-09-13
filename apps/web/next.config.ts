import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/_api/:path*", destination: "http://localhost:8000/:path*" }];
  },
};
export default nextConfig;