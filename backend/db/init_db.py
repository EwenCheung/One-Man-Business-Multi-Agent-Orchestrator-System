from sqlalchemy import text
from sqlalchemy.engine import Engine
from typing import cast

from backend.db.engine import engine
from backend.db.models import Base
from backend.db import models  # noqa: F401 — registers ORM models with Base.metadata


def init():
    db_engine = cast(Engine, engine)

    # Enable vector db
    with db_engine.connect() as conn:
        _ = conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    print("Creating tables...")
    Base.metadata.create_all(db_engine)

    with db_engine.connect() as conn:
        _ = conn.execute(
            text("ALTER TABLE public.pending_approvals ADD COLUMN IF NOT EXISTS held_reply_id uuid")
        )
        _ = conn.execute(
            text("ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS telegram_bot_token text")
        )
        _ = conn.execute(
            text(
                "ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS telegram_webhook_secret text"
            )
        )
        _ = conn.execute(
            text("ALTER TABLE public.customers ADD COLUMN IF NOT EXISTS telegram_user_id text")
        )
        _ = conn.execute(
            text("ALTER TABLE public.customers ADD COLUMN IF NOT EXISTS telegram_username text")
        )
        _ = conn.execute(
            text("ALTER TABLE public.customers ADD COLUMN IF NOT EXISTS telegram_chat_id text")
        )
        _ = conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_customers_owner_telegram_user_id ON public.customers (owner_id, telegram_user_id) WHERE telegram_user_id IS NOT NULL"
            )
        )
        _ = conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'pending_approvals_held_reply_id_fkey'
                    ) THEN
                        ALTER TABLE public.pending_approvals
                        ADD CONSTRAINT pending_approvals_held_reply_id_fkey
                        FOREIGN KEY (held_reply_id)
                        REFERENCES public.held_replies(id);
                    END IF;
                END
                $$;
                """
            )
        )
        _ = conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE n.nspname = 'public' AND c.relname = 'investor_product_metrics'
                    ) THEN
                        EXECUTE 'ALTER TABLE public.investor_product_metrics ENABLE ROW LEVEL SECURITY';
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_policies
                            WHERE schemaname = 'public'
                              AND tablename = 'investor_product_metrics'
                              AND policyname = 'owner_access_investor_product_metrics'
                        ) THEN
                            EXECUTE 'CREATE POLICY owner_access_investor_product_metrics ON public.investor_product_metrics USING (owner_id = auth.uid())';
                        END IF;
                    END IF;
                END
                $$;
                """
            )
        )
        conn.commit()

    print("Done.")


if __name__ == "__main__":
    init()
