# website/__init__.py

from flask import Flask
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate  # Add this import
from flask_wtf.csrf import CSRFProtect
from flask_wtf import FlaskForm
from os import path
import os

db = SQLAlchemy()
migrate = Migrate()  # Add this line
login_manager = LoginManager()
DB_NAME = 'database.db'

def create_app():
    app = Flask(__name__)

    load_dotenv()
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    []
    db.init_app(app)
    migrate.init_app(app, db)  # Add this line
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from .views import views
    from .auth import auth
    from .models import User  # ✅ moved inside to avoid circular import

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    
    # Keep the create_database function but only run it if the database doesn't exist
    create_database(app)
    
    return app

def create_database(app):
    if not path.exists('website/' + DB_NAME):
        with app.app_context():
            db.create_all()
        print('Created Database!')