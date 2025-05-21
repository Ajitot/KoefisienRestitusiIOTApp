from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_CONFIG = {
    "url": os.getenv("SUPABASE_URL"),
    "secret_key": os.getenv("SUPABASE_SECRET_KEY"),
    "id": os.getenv("SUPABASE_ID")
}

TIMEZONE = os.getenv("TIMEZONE", "Asia/Jakarta")
TABLE_NAME = os.getenv("TABLE_NAME", "maintable")
