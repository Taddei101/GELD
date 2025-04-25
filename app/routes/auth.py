from flask import Blueprint, render_template, request, flash, redirect, url_for, session

auth_bp = Blueprint('auth', __name__)

USERNAME = "claudio"
PASSWORD = "1234"

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == USERNAME and request.form['password'] == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard.cliente_dashboard'))
        else:
            flash('Invalid credentials')
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('auth.login'))