This frontend is part of the monorepo app and expects shared environment values from the repo-root `.env` during normal local development.

## Getting Started

From the repo root, run:

```bash
npm run dev
```

If you want to run commands directly inside `frontend/`, create `frontend/.env.local` first and then use the local package scripts.

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy / Production

This frontend is configured for standalone production output and Docker/Compose deployment. Public `NEXT_PUBLIC_*` values must be present at build time.

Check out the root project README for the full local and Docker workflow.
