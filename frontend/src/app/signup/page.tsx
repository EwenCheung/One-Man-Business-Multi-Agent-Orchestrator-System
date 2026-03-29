"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export default function SignupPage() {
  const supabase = createClient();
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  async function handleSignup(e: React.FormEvent) {
    e.preventDefault();
    setErrorMessage("");

    const { data, error } = await supabase.auth.signUp({
      email,
      password,
    });

    if (error) {
      setErrorMessage(error.message);
      return;
    }

    if (data.user) {
      await supabase.from("profiles").upsert({
        id: data.user.id,
        full_name: fullName,
        business_name: businessName,
      });
    }

    router.push("/dashboard");
    router.refresh();
  }

  return (
    <div className="mx-auto max-w-md space-y-6 py-12">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Sign up</h1>
        <p className="mt-2 text-zinc-500">
          Create your owner account.
        </p>
      </div>

      <form onSubmit={handleSignup} className="space-y-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
        <input
          className="w-full rounded-xl border border-zinc-300 px-4 py-3"
          placeholder="Full name"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
        />
        <input
          className="w-full rounded-xl border border-zinc-300 px-4 py-3"
          placeholder="Business name"
          value={businessName}
          onChange={(e) => setBusinessName(e.target.value)}
        />
        <input
          className="w-full rounded-xl border border-zinc-300 px-4 py-3"
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          className="w-full rounded-xl border border-zinc-300 px-4 py-3"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {errorMessage ? (
          <p className="text-sm text-red-600">{errorMessage}</p>
        ) : null}
        <button
          className="w-full rounded-xl bg-zinc-900 px-4 py-3 text-white"
          type="submit"
        >
          Sign up
        </button>
      </form>
    </div>
  );
}