import os
import secrets
from flask import Blueprint, render_template, request, flash, redirect, url_for, session

auth_bp = Blueprint('auth', __name__)

USERNAME = os.environ.get('GELD_USERNAME')
PASSWORD = os.environ.get('GELD_PASSWORD')

if not USERNAME or not PASSWORD:
    raise RuntimeError("GELD_USERNAME e GELD_PASSWORD devem estar definidos nas variáveis de ambiente")

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario_ok = secrets.compare_digest(request.form.get('username', ''), USERNAME)
        senha_ok = secrets.compare_digest(request.form.get('password', ''), PASSWORD)
        if usuario_ok and senha_ok:
            session.clear()
            session['logged_in'] = True
            session.permanent = True
            return redirect(url_for('dashboard.cliente_dashboard'))
        else:
            flash('Usuário ou senha inválidos')
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('auth.login'))