module.exports = {
  apps: [
    {
      name: "family-companion-api",
      cwd: __dirname,
      script: "python3",
      args: "-m uvicorn api.main:app --host 127.0.0.1 --port 8000",
      env: {
        PYTHONUNBUFFERED: "1",
      },
      max_memory_restart: "512M",
    },
    {
      name: "family-companion-web",
      cwd: `${__dirname}/web`,
      // web/package.json start script runs: next start
      script: "npm",
      args: "run start -- --hostname 127.0.0.1 --port 3000",
      env: {
        NODE_ENV: "production",
        NEXT_PUBLIC_COMPANION_API_URL: "/api",
      },
      max_memory_restart: "768M",
    },
  ],
};
