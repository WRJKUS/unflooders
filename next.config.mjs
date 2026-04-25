/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    optimizePackageImports: ["@turf/turf"]
  }
}

export default nextConfig
