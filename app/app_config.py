from flask import Flask, redirect, url_for, session
from datetime import timedelta
import os
from flask_cors import CORS

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__, template_folder='templates', static_folder='static')

CORS(app, resources={r"/api/*": {"origins": [
    "https://www.geldfp.com.br",
    "https://geldfp.com.br",
    "http://127.0.0.1:5500",
    "http://localhost:5500",
]}})

app.secret_key = os.environ.get('SECRET_KEY') or 'dev-local-secret-key'
app.config['DEBUG'] = os.environ.get('DEBUG', 'False').lower() == 'true'

app.config.update(
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=False,
)

@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

# Imports dos blueprints
from app.routes.auth import auth_bp
from app.routes.cliente import cliente_bp
from app.routes.objetivo import objetivo_bp
from app.routes.fundos import fundos_bp
from app.routes.posicao import posicao_bp
from app.routes.dashboard import dashboard_bp
from app.routes.balanco import balanco_bp

from app.routes.posicao_advisor import posicao_advisor_bp
from app.routes.pipelines import pipelines_bp

from app.routes.area_cliente import area_cliente_bp

# Registrar blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(cliente_bp)
app.register_blueprint(objetivo_bp)
app.register_blueprint(fundos_bp)
app.register_blueprint(posicao_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(balanco_bp)

app.register_blueprint(posicao_advisor_bp)
app.register_blueprint(pipelines_bp)

app.register_blueprint(area_cliente_bp)

@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard.cliente_dashboard'))
    return redirect(url_for('auth.login'))