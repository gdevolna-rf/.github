import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  // Медиа отдаёт nginx из MinIO; WebP-миниатюры генерирует backend (UX-16).
  images: { unoptimized: true },
};

export default nextConfig;
