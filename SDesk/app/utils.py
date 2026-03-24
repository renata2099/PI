from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user
from app.models import Chamado, Interacao, db
from datetime import datetime

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

def get_estatisticas(usuario=None):
    from app.models import Chamado, Departamento

    query = Chamado.query
    if usuario and not usuario.is_admin():
        if usuario.is_atendente():
            query = query.filter(
                (Chamado.atendente_id == usuario.id) | 
                (Chamado.departamento_id == usuario.departamento_id)
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