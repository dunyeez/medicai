from flask import Flask
from .auth import auth_bp
from .routes import main_bp
from .speech import speech_bp
from .map import map_bp
from .therapist import therapist_bp


def create_app():
    app = Flask(__name__)
    app.secret_key = 'your_secret_key'  # (Make sure to change this to a real secret key in production!)

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(speech_bp)
    app.register_blueprint(map_bp)

    # Add the url_prefix right here:
    app.register_blueprint(therapist_bp, url_prefix='/therapist')

    return app