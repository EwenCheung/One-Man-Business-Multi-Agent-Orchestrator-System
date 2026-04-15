"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { SignInWithPasswordCredentials } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase/client";
import Link from "next/link";

function normalizePhoneIdentifier(value: string) {
  const digits = value.replace(/\D/g, "");
  return digits ? `+${digits}` : "";
}

export default function LoginPage() {
  const router = useRouter();

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setErrorMessage("");

    const supabase = createClient();
    
    let credentials: SignInWithPasswordCredentials;
    const trimmedId = identifier.trim();
    const isPhone = /^\+?[0-9\s\-]+$/.test(trimmedId);

    if (isPhone) {
      credentials = { phone: normalizePhoneIdentifier(trimmedId), password };
    } else {
      const cleanId = trimmedId.startsWith('@') ? trimmedId.slice(1) : trimmedId;
      if (cleanId.includes('@')) {
        credentials = { email: trimmedId, password };
      } else {
        credentials = { email: `${cleanId}@telegram.local`, password };
      }
    }

    const { error } = await supabase.auth.signInWithPassword(credentials);

    if (error) {
      setErrorMessage(error.message);
      return;
    }

    const { data: sessionData } = await supabase.auth.getUser();
    const userId = sessionData.user?.id;
    if (!userId) {
      router.push("/dashboard");
      router.refresh();
      return;
    }

    const { data: ownerProfile } = await supabase
      .from("profiles")
      .select("id")
      .eq("id", userId)
      .maybeSingle();

    if (ownerProfile?.id) {
      router.push("/dashboard");
      router.refresh();
      return;
    }

    const { data: identity } = await supabase
      .from("external_identities")
      .select("entity_role")
      .contains("identity_metadata", { supabase_user_id: userId })
      .limit(1)
      .maybeSingle();

    const role = identity?.entity_role;
    if (role === "customer" || role === "supplier" || role === "partner" || role === "investor") {
      router.push(`/dashboards/${role}`);
    } else {
      router.push("/dashboard");
    }
    router.refresh();
  }

  return (
    <div className="mx-auto max-w-md space-y-6 py-12">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Login</h1>
        <p className="mt-2 text-zinc-500">
          Sign in to your dashboard.
        </p>
      </div>

      <form onSubmit={handleLogin} className="space-y-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
        <input
          className="w-full rounded-xl border border-zinc-300 px-4 py-3"
          type="text"
          placeholder="Email, Phone, or Username"
          value={identifier}
          onChange={(e) => setIdentifier(e.target.value)}
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
          Log in
        </button>
      </form>
      <p className="mt-4 text-sm text-zinc-500 text-center">
        Don't have an account?{" "}
        <Link
          href="/signup"
          className="font-medium text-zinc-900 hover:underline"
        >
          Sign up
        </Link>
      </p>
    </div>
  );
}
