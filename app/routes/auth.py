import os
import secrets
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from app.models.geld_models import create_session, Usuario
from app.services.global_services import login_required


auth_bp = Blueprint('auth', __name__)

USERNAME = os.environ.get('GELD_USERNAME', 'ulisses')
PASSWORD = os.environ.get('GELD_PASSWORD')

def conferir_login(usuario, senha):
    if PASSWORD and secrets.compare_digest(usuario.encode(), USERNAME.encode()) \
            and secrets.compare_digest(senha.encode(), PASSWORD.encode()):
        return True
    db = create_session()
    try:
        u = db.query(Usuario).filter_by(username=usuario).first()
        return u is not None and u.conferir_senha(senha)
    finally:
        db.close()

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('username', '')
        if conferir_login(usuario, request.form.get('password', '')):
            session.clear()
            session['logged_in'] = True
            session['usuario'] = usuario
            session.permanent = True
            return redirect(url_for('dashboard.cliente_dashboard'))
        else:
            flash('Usuário ou senha inválidos')
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/trocar-senha', methods=['GET', 'POST'])
@login_required
def trocar_senha():
    if request.method == 'POST':
        nova = request.form.get('nova', '')
        db = create_session()
        try:
            u = db.query(Usuario).filter_by(username=session.get('usuario')).first()
            if u is None:
                flash('Este usuário troca a senha no servidor.', 'error')
            elif not u.conferir_senha(request.form.get('atual', '')):
                flash('Senha atual incorreta.', 'error')
            elif len(nova) < 8:
                flash('A nova senha precisa ter pelo menos 8 caracteres.', 'error')
            elif nova != request.form.get('confirmar', ''):
                flash('As senhas novas não conferem.', 'error')
            else:
                u.definir_senha(nova)
                db.commit()
                flash('Senha alterada.', 'success')
                return redirect(url_for('dashboard.cliente_dashboard'))
        finally:
            db.close()
    return render_template('auth/trocar_senha.html')