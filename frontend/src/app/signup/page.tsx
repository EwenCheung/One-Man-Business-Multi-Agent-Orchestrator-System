"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export default function SignupPage() {
  const supabase = createClient();
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSignup(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMessage(null);

    const { error } = await supabase.auth.signUp({
      email,
      password,
    });

    setLoading(false);

    if (error) {
      setError(error.message);
      return;
    }

    setMessage("Account created. Check your email if confirmation is enabled.");
    router.push("/login");
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-4">
      <form
        onSubmit={handleSignup}
        className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm space-y-4"
      >
        <div>
          <h1 className="text-2xl font-semibold text-zinc-900">Sign up</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Create your owner account to access the dashboard.
          </p>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-zinc-700">Email</label>
          <input
            type="email"
            className="w-full rounded-xl border border-zinc-300 px-3 py-2 outline-none focus:border-zinc-500"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-zinc-700">Password</label>
          <input
            type="password"
            className="w-full rounded-xl border border-zinc-300 px-3 py-2 outline-none focus:border-zinc-500"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {message && <p className="text-sm text-emerald-600">{message}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-xl bg-zinc-900 px-4 py-2 text-white hover:bg-zinc-800 disabled:opacity-50"
        >
          {loading ? "Creating account..." : "Create account"}
        </button>

        <p className="text-sm text-zinc-500">
          Already have an account?{" "}
          <Link href="/login" className="text-zinc-900 underline">
            Log in
          </Link>
        </p>
      </form>
    </div>
  );
}