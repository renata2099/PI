from datetime import datetime
from functools import wraps
import smtplib
from email.mime.text import MIMEText

from flask import flash, redirect, url_for
from flask_login import current_user

from app.models import Chamado, Interacao, NotificacaoEmail, Usuario, UsuarioDepartamento, db


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash("Acesso restrito a administradores.", "danger")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)

    return decorated_function


def atendente_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_atendente():
            flash("Acesso restrito a atendentes.", "danger")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)

    return decorated_function


def atualizar_status_chamado(chamado_id, novo_status, usuario_id, mensagem=None):
    chamado = Chamado.query.get(chamado_id)

    if not chamado:
        return False

    status_anterior = chamado.status
    chamado.status = novo_status
    chamado.data_atualizacao = datetime.utcnow()

    if novo_status == "Encerrado" and status_anterior != "Encerrado":
        chamado.data_fechamento = datetime.utcnow()

    if not mensagem:
        mensagem = f'Status alterado de "{status_anterior}" para "{novo_status}"'

    interacao = Interacao(
        chamado_id=chamado_id,
        usuario_id=usuario_id,
        mensagem=mensagem,
        tipo="status",
    )

    db.session.add(interacao)
    db.session.commit()

    return True


def get_estatisticas(usuario=None):
    query = Chamado.query

    if usuario and not usuario.is_admin():
        if usuario.is_atendente():
            dept_ids = [
                d.departamento_id
                for d in UsuarioDepartamento.query.filter_by(usuario_id=usuario.id).all()
            ]

            query = query.filter(
                (Chamado.atendente_id == usuario.id)
                | (Chamado.responsavel_id == usuario.id)
                | (Chamado.departamento_id.in_(dept_ids))
            )
        else:
            query = query.filter_by(usuario_id=usuario.id)

    total = query.count()
    abertos = query.filter_by(status="Aberto").count()
    em_atendimento = query.filter_by(status="Em atendimento").count()
    resolvidos = query.filter(Chamado.status.in_(["Resolvido", "Encerrado"])).count()

    return {
        "total": total,
        "abertos": abertos,
        "em_atendimento": em_atendimento,
        "resolvidos": resolvidos,
    }


def enviar_email(destinatario, assunto, mensagem):
    try:
        from flask import current_app

        mail_user = current_app.config.get("MAIL_USERNAME")
        mail_pass = current_app.config.get("MAIL_PASSWORD")
        mail_server = current_app.config.get("MAIL_SERVER")
        mail_port = current_app.config.get("MAIL_PORT")
        mail_use_tls = current_app.config.get("MAIL_USE_TLS")
        mail_use_ssl = current_app.config.get("MAIL_USE_SSL")
        mail_timeout = current_app.config.get("MAIL_TIMEOUT", 20)
        mail_sender = current_app.config.get("MAIL_DEFAULT_SENDER") or mail_user

        if not all([mail_user, mail_pass, mail_server, mail_port]):
            print("Email nao configurado. Pulando envio.")
            return False, "Email nao configurado"

        msg = MIMEText(mensagem)
        msg["Subject"] = assunto
        msg["From"] = mail_sender
        msg["To"] = destinatario

        smtp_class = smtplib.SMTP_SSL if mail_use_ssl else smtplib.SMTP

        with smtp_class(mail_server, mail_port, timeout=mail_timeout) as server:
            if mail_use_tls and not mail_use_ssl:
                server.starttls()
            server.login(mail_user, mail_pass)
            server.send_message(msg)

        print(f"Email enviado para {destinatario}")
        return True, None

    except Exception as e:
        print("Erro ao enviar email:", e)
        return False, str(e)


def notificar_interacao_chamado(chamado, autor, assunto, mensagem):
    participantes = [chamado.solicitante, chamado.atendente, chamado.responsavel]
    destinatarios = []
    vistos = set()

    usuarios_departamento = []
    if chamado.departamento_id:
        usuarios_departamento = (
            db.session.query(UsuarioDepartamento)
            .filter_by(departamento_id=chamado.departamento_id)
            .all()
        )

    for vinculo in usuarios_departamento:
        usuario = db.session.get(Usuario, vinculo.usuario_id)
        if usuario:
            participantes.append(usuario)

    for usuario in participantes:
        if not usuario or not usuario.id or usuario.id == autor.id:
            continue
        if usuario.id in vistos:
            continue
        vistos.add(usuario.id)

        if not usuario.ativo or not usuario.receber_email or not usuario.email:
            continue

        destinatarios.append(usuario)

    for usuario in destinatarios:
        notificacao = NotificacaoEmail(
            chamado_id=chamado.id,
            destinatario=usuario.email,
            assunto=assunto,
            mensagem=mensagem,
        )
        db.session.add(notificacao)

        enviado, erro = enviar_email(usuario.email, assunto, mensagem)
        notificacao.enviado = enviado
        notificacao.enviado_em = datetime.utcnow() if enviado else None
        notificacao.erro = erro


def montar_email_interacao(chamado, autor, acao, mensagem):
    assunto = f"Chamado #{chamado.id}: {acao}"
    corpo = (
        f"Chamado #{chamado.id} - {chamado.titulo}\n\n"
        f"Usuario que realizou a interacao: {autor.nome}\n"
        f"Acao: {acao}\n"
        f"Status atual: {chamado.status}\n"
        f"Departamento: {chamado.departamento.nome if chamado.departamento else '-'}\n\n"
        f"Mensagem:\n{mensagem}\n"
    )
    return assunto, corpo
