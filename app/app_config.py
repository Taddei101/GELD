from flask import Flask, redirect, url_for, session
import os

app = Flask(__name__, template_folder='templates', static_folder='static')

# Usar configuração mais segura
app.secret_key = os.environ.get('SECRET_KEY', 'lkj12tu6')
app.config['DEBUG'] = os.environ.get('DEBUG', 'False').lower() == 'true'

# Imports dos blueprints
from app.routes.auth import auth_bp
from app.routes.cliente import cliente_bp
from app.routes.objetivo import objetivo_bp
from app.routes.fundos import fundos_bp
from app.routes.posicao import posicao_bp
from app.routes.dashboard import dashboard_bp
from app.routes.balanco import balanco_bp
from app.routes.distribuicao import distribuicao_bp
from app.routes.posicao_advisor import posicao_advisor_bp

# Registrar blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(cliente_bp)
app.register_blueprint(objetivo_bp)
app.register_blueprint(fundos_bp)
app.register_blueprint(posicao_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(balanco_bp)
app.register_blueprint(distribuicao_bp)
app.register_blueprint(posicao_advisor_bp)

@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard.cliente_dashboard'))
    return redirect(url_for('auth.login'))