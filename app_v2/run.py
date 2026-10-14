import os
import sys

_parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from flask import Flask
from flask_wtf.csrf import CSRFProtect
from app_v2.config import Config
from app_v2.utils.crypto import loadOrCreateKeys
from app_v2.routes.auth import auth_bp
from app_v2.routes.admin import admin_bp
from app_v2.routes.patient import patient_bp
from app_v2.routes.doctor import doctor_bp
from app_v2.routes.main import main_bp

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.secret_key = Config.SECRET_KEY
    
    # Enable CSRF Protection globally
    csrf.init_app(app)
    
    # Load keys
    loadOrCreateKeys()
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(main_bp)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
