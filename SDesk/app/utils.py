from functools import wraps
from flask import flash, redirect, url_for, current_app
from flask_login import current_user
from app.models import Chamado, Interacao, UsuarioDepartamento, db
from datetime import datetime
import smtplib
from email.mime.text import MIMEText


# =========================
# PERMISSÕES
# =========================
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Acesso restrito a administradores.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def atendente_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_atendente():
            flash('Acesso restrito a atendentes.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# =========================
# STATUS DO CHAMADO
# =========================
def atualizar_status_chamado(chamado_id, novo_status, usuario_id, mensagem=None):
    chamado = Chamado.query.get(chamado_id)

    if not chamado:
        return False

    status_anterior = chamado.status
    chamado.status = novo_status
    chamado.data_atualizacao = datetime.utcnow()

    if novo_status == 'Encerrado' and status_anterior != 'Encerrado':
        chamado.data_fechamento = datetime.utcnow()

    if not mensagem:
        mensagem = f'Status alterado de "{status_anterior}" para "{novo_status}"'

    interacao = Interacao(
        chamado_id=chamado_id,
        usuario_id=usuario_id,
        mensagem=mensagem,
        tipo='status'
    )

    db.session.add(interacao)
    db.session.commit()

    return True


# =========================
# ESTATÍSTICAS (CORRIGIDO MULTI-DEPARTAMENTO)
# =========================
def get_estatisticas(usuario=None):
    query = Chamado.query

    if usuario and not usuario.is_admin():

        if usuario.is_atendente():
            # 🔥 pega todos departamentos do usuário
            dept_ids = [d.departamento_id for d in UsuarioDepartamento.query.filter_by(
                usuario_id=usuario.id
            ).all()]

            query = query.filter(
                (Chamado.atendente_id == usuario.id) |
                (Chamado.responsavel_id == usuario.id) |
                (Chamado.departamento_id.in_(dept_ids))
            )

        else:
            query = query.filter_by(usuario_id=usuario.id)

    total = query.count()
    abertos = query.filter_by(status='Aberto').count()
    em_atendimento = query.filter_by(status='Em atendimento').count()
    resolvidos = query.filter(Chamado.status.in_(['Resolvido', 'Encerrado'])).count()

    return {
        'total': total,
        'abertos': abertos,
        'em_atendimento': em_atendimento,
        'resolvidos': resolvidos
    }


# =========================
# 🔥 ENVIO DE EMAIL
# =========================
def enviar_email(destinatario, assunto, mensagem):
    try:
        from flask import current_app

        mail_user = current_app.config.get('MAIL_USERNAME')
        mail_pass = current_app.config.get('MAIL_PASSWORD')
        mail_server = current_app.config.get('MAIL_SERVER')
        mail_port = current_app.config.get('MAIL_PORT')

        # 🔥 se não tiver config, simplesmente ignora (não quebra o sistema)
        if not all([mail_user, mail_pass, mail_server, mail_port]):
            print("Email não configurado. Pulando envio.")
            return

        msg = MIMEText(mensagem)
        msg['Subject'] = assunto
        msg['From'] = mail_user
        msg['To'] = destinatario

        with smtplib.SMTP(mail_server, mail_port) as server:
            server.starttls()
            server.login(mail_user, mail_pass)
            server.send_message(msg)

        print(f"Email enviado para {destinatario}")

    except Exception as e:
        print("Erro ao enviar email:", e)