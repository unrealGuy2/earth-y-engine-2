from supabase import create_client, Client
from app.core.config import settings

# We use the Service Role Key here so the backend has full administrative access
# to write to the database after it manually verifies the user's token.
supabase: Client = create_client(
    settings.SUPABASE_URL, 
    settings.SUPABASE_SERVICE_ROLE_KEY
)