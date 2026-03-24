from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import Usuario
from app import db, login_manager

auth = Blueprint('auth', __name__)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = bool(request.form.get('remember'))

        user = Usuario.query.filter_by(email=email, ativo=True).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash(f'Bem-vindo, {user.nome}!', 'success')
            return redirect(next_page if next_page else url_for('main.dashboard'))
        else:
            flash('Email ou senha incorretos.', 'danger')

    return render_template('login.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Voce saiu do sistema.', 'info')
    return redirect(url_for('auth.login'))

@auth.route('/trocar-senha', methods=['POST'])
@login_required
def trocar_senha():
    senha_atual = request.form.get('senha_atual')
    nova_senha = request.form.get('nova_senha')

    if not current_user.check_password(senha_atual):
        flash('Senha atual incorreta.', 'danger')
        return redirect(url_for('main.dashboard'))

    if len(nova_senha) < 6:
        flash('A nova senha deve ter pelo menos 6 caracteres.', 'warning')
        return redirect(url_for('main.dashboard'))

    current_user.set_password(nova_senha)
    db.session.commit()
    flash('Senha alterada com sucesso!', 'success')
    return redirect(url_for('main.dashboard'))