import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    const inference = process.env.INFERENCE_INTERNAL_URL;
    return inference ? [
      { source: "/health", destination: `${inference}/health` },
      { source: "/ws/measure", destination: `${inference}/ws/measure` },
    ] : [];
  },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "Permissions-Policy", value: "camera=(self), microphone=()" },
        { key: "Referrer-Policy", value: "no-referrer" },
        { key: "X-Content-Type-Options", value: "nosniff" },
      ],
    }];
  },
};
export default nextConfig;
