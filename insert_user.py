import os
import bcrypt
import psycopg2
from dotenv import load_dotenv

load_dotenv(".env")
db_url = os.environ.get("SUPABASE_DB_URL")

password = "Abcd@1234".encode("utf-8")
salt = bcrypt.gensalt()
hashed = bcrypt.hashpw(password, salt).decode("utf-8")

conn = psycopg2.connect(db_url)
cur = conn.cursor()

owner_id = "4c116430-f683-4a8a-91f7-546fa8bc5d76"

try:
    cur.execute(
        """
        INSERT INTO auth.users (id, instance_id, aud, role, email, encrypted_password, email_confirmed_at, raw_app_meta_data, raw_user_meta_data, created_at, updated_at)
        VALUES (%s, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'test@gmail.com', %s, now(), '{"provider":"email","providers":["email"]}', '{"full_name": "Test User", "business_name": "Test Business"}', now(), now())
        ON CONFLICT (id) DO UPDATE SET 
            encrypted_password = EXCLUDED.encrypted_password,
            email_confirmed_at = now();
    """,
        (owner_id, hashed),
    )
    conn.commit()
    print("Successfully inserted auth.users row!")

    cur.execute(
        """
        INSERT INTO public.profiles (id, full_name, business_name, notifications_email, created_at)
        VALUES (%s, 'Test User', 'Test Business', 'test@gmail.com', now())
        ON CONFLICT (id) DO NOTHING;
    """,
        (owner_id,),
    )
    conn.commit()
    print("Successfully inserted profile row!")

except Exception as e:
    conn.rollback()
    print("Error:", e)
finally:
    cur.close()
    conn.close()
