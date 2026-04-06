import Link from "next/link";

export default function VerifyEmailPage() {
  return (
    <div className="mx-auto max-w-md space-y-6 py-12">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Verify your email</h1>
        <p className="mt-2 text-zinc-500">
          We've sent a verification link to your email address. Please open that email and click the link to confirm your account.
        </p>
      </div>

      <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
        <p className="text-sm text-zinc-700">
          Once you've verified your email, return here or sign in from the login page. If you don't see the message, check your spam folder.
        </p>

        <div className="mt-4 flex items-center justify-between">
          <Link href="/login" className="text-sm font-medium text-zinc-900 hover:underline">
            Back to login
          </Link>
          <Link href="/" className="text-sm text-zinc-500 hover:underline">
            Return home
          </Link>
        </div>
      </div>
    </div>
  );
}