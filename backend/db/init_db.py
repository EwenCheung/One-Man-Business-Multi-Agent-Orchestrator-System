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
                CREATE OR REPLACE FUNCTION public.purchase_product_atomic(
                    p_owner_id uuid,
                    p_customer_id uuid,
                    p_product_id uuid,
                    p_quantity integer,
                    p_order_id uuid,
                    p_order_date date,
                    p_channel text DEFAULT 'website'
                )
                RETURNS jsonb
                LANGUAGE plpgsql
                SECURITY DEFINER
                SET search_path = public
                AS $$
                DECLARE
                    v_selling_price numeric;
                    v_remaining_stock integer;
                    v_total_price numeric;
                BEGIN
                    IF p_quantity IS NULL OR p_quantity < 1 THEN
                        RAISE EXCEPTION 'INVALID_QUANTITY';
                    END IF;

                    PERFORM 1
                    FROM public.customers
                    WHERE id = p_customer_id AND owner_id = p_owner_id;

                    IF NOT FOUND THEN
                        RAISE EXCEPTION 'CUSTOMER_NOT_FOUND';
                    END IF;

                    UPDATE public.products
                    SET stock_number = stock_number - p_quantity,
                        updated_at = now()
                    WHERE id = p_product_id
                      AND owner_id = p_owner_id
                      AND COALESCE(stock_number, 0) >= p_quantity
                    RETURNING selling_price, stock_number
                    INTO v_selling_price, v_remaining_stock;

                    IF NOT FOUND THEN
                        RAISE EXCEPTION 'OUT_OF_STOCK_OR_PRODUCT_NOT_FOUND';
                    END IF;

                    v_total_price = COALESCE(v_selling_price, 0) * p_quantity;

                    INSERT INTO public.orders (
                        id,
                        owner_id,
                        customer_id,
                        product_id,
                        quantity,
                        total_price,
                        order_date,
                        status,
                        channel
                    )
                    VALUES (
                        p_order_id,
                        p_owner_id,
                        p_customer_id,
                        p_product_id,
                        p_quantity,
                        v_total_price,
                        p_order_date,
                        'paid',
                        p_channel
                    );

                    RETURN jsonb_build_object(
                        'order_id', p_order_id,
                        'total_price', v_total_price,
                        'remaining_stock', v_remaining_stock
                    );
                END;
                $$;
                """
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
