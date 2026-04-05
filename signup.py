import os
import requests
from dotenv import load_dotenv

load_dotenv(".env")
url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
key = os.environ.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY") or os.environ.get(
    "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY"
)

res = requests.post(
    f"{url}/auth/v1/signup",
    headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    json={
        "email": "test@gmail.com",
        "password": "Abcd@1234",
        "data": {"full_name": "Test User", "business_name": "Test Business"},
    },
)
print("Status:", res.status_code)
print("Response:", res.json())
