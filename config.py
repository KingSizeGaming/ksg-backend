import os

class Config:
    # Ensures that a SECRET_KEY is set in the environment, otherwise throws an error.
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("No SECRET_KEY set for Flask application. Set it as an environment variable.")

    DROPBOX_OAUTH2_REFRESH_TOKEN = os.environ.get('DROPBOX_REFRESH_TOKEN')
    DROPBOX_APP_KEY = os.environ.get('DROPBOX_APP_KEY')
    DROPBOX_APP_SECRET = os.environ.get('DROPBOX_APP_SECRET')
    SUPABASE_URL = os.environ.get('SUPABASE_URL')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

# Export configuration class
config = Config()

