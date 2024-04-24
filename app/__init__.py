# __init__.py
from flask import Flask, session
from config import Config
from flask_login import LoginManager
from .models import User
from .services import get_supabase

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        # Assuming user details are stored in the session
        user_info = session.get('user_details')
        if user_info and user_info['id'] == user_id:
            return User(id=user_id, email=user_info['email'])
        return None

    # Import and register blueprints or route initializers here
    from .routes import init_routes
    init_routes(app)

    return app


