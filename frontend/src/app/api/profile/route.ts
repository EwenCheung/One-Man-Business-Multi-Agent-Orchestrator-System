import { getAuthenticatedClient, getOwnerProfile, upsertOwnerProfile } from "@/lib/api";
import { getBackendBaseUrl } from "@/lib/backend";
import type { OwnerProfileInput } from "@/lib/types";
import { NextResponse } from "next/server";

function getTelegramWebhookUrl() {
  const baseUrl = (process.env.BACKEND_PUBLIC_URL ?? getBackendBaseUrl()).trim().replace(/\/+$/, "");
  return `${baseUrl}/api/v1/telegram/webhook`;
}

async function validateTelegramWebhookTarget(secret: string) {
  const webhookUrl = getTelegramWebhookUrl();

  let response: Response;
  try {
    response = await fetch(webhookUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Telegram-Bot-Api-Secret-Token": secret,
      },
      body: JSON.stringify({ update_id: "healthcheck", message: { text: "" } }),
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
  } catch {
    throw new Error(
      `Backend public URL is not responding. Please start the backend and expose a working public URL before saving Telegram settings. (${webhookUrl})`
    );
  }

  if (![200, 403].includes(response.status)) {
    throw new Error(
      `Backend public URL is reachable but Telegram webhook endpoint is not working correctly (status ${response.status}). Please check ${webhookUrl}.`
    );
  }
}

async function registerTelegramWebhook(token: string, secret: string) {
  await validateTelegramWebhookTarget(secret);

  const response = await fetch(`https://api.telegram.org/bot${token}/setWebhook`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      url: getTelegramWebhookUrl(),
      secret_token: secret,
      allowed_updates: ["message"],
    }),
    cache: "no-store",
  });

  const payload = await response.json();
  if (!response.ok || payload?.ok === false) {
    throw new Error(payload?.description || "Failed to register Telegram webhook");
  }
}

export async function GET() {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const profile = await getOwnerProfile();
  return NextResponse.json(profile);
}

export async function PATCH(request: Request) {
  try {
    const auth = await getAuthenticatedClient({ redirectOnFail: false });

    if (!auth) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const payload = (await request.json()) as OwnerProfileInput;
    const touchedTelegramSettings =
      payload.telegram_bot_token !== undefined || payload.telegram_webhook_secret !== undefined;

    const profile = await upsertOwnerProfile(payload);
    const nextToken = profile.telegram_bot_token ?? null;
    const nextSecret = profile.telegram_webhook_secret ?? null;

    if (touchedTelegramSettings && nextToken && nextSecret) {
      try {
        await registerTelegramWebhook(nextToken, nextSecret);
      } catch (error) {
        console.error("Telegram webhook registration failed after profile save", error);
        return NextResponse.json({
          profile,
          warning: `Profile saved, but Telegram webhook registration failed: ${error instanceof Error ? error.message : "Unknown error"}`,
        });
      }
    }

    return NextResponse.json({ profile, warning: null });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to save profile." },
      { status: 500 }
    );
  }
}
