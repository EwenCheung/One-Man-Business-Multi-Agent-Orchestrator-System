from sqlalchemy import text

from backend.db.engine import engine
from backend.db.models import Base
from backend.db import models  # noqa: F401 — registers ORM models with Base.metadata


def init():
    # Enable vector db
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    print("Creating tables...")
    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        conn.execute(
            text("ALTER TABLE public.pending_approvals ADD COLUMN IF NOT EXISTS held_reply_id uuid")
        )
        conn.execute(
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
        conn.commit()

    print("Done.")


if __name__ == "__main__":
    init()
