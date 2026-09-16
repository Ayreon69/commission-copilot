import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Image Docker minimale : serveur autonome sans node_modules complet.
  output: "standalone",
};

export default nextConfig;
