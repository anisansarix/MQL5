const nextConfig: import('next').NextConfig = {
  // @ts-ignore
  allowedDevOrigins: [
    '0292a87d99d7930e-115-96-46-169.serveousercontent.com',
    'localhost',
    '127.0.0.1'
  ],
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/api/:path*',
      },
    ]
  },
};

export default nextConfig;
