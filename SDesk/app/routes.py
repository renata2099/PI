from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from app.models import Chamado, Usuario, Departamento, Interacao, db
from app.utils import admin_required, atendente_required, atualizar_status_chamado, get_estatisticas
from datetime import datetime
import pandas as pd
from io import BytesIO

main = Blueprint('main', __name__)

@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@main.route('/dashboard')
@login_required
def dashboard():
    stats = get_estatisticas(current_user)

    if current_user.is_admin():
        chamados_recentes = Chamado.query.order_by(Chamado.data_atualizacao.desc()).limit(10).all()
    elif current_user.is_atendente():
        chamados_recentes = Chamado.query.filter(
            (Chamado.atendente_id == current_user.id) | 
            (Chamado.departamento_id == current_user.departamento_id) |
            (Chamado.status == 'Aberto')
        ).order_by(Chamado.data_atualizacao.desc()).limit(10).all()
    else:
        chamados_recentes = Chamado.query.filter_by(usuario_id=current_user.id).order_by(Chamado.data_atualizacao.desc()).limit(10).all()

    departamentos = Departamento.query.all()
    dept_stats = {}
    for dept in departamentos:
        dept_stats[dept.nome] = Chamado.query.filter_by(departamento_id=dept.id).count()

    return render_template('dashboard.html', 
                         stats=stats, 
                         chamados=chamados_recentes,
                         dept_stats=dept_stats)

@main.route('/chamado/novo', methods=['GET', 'POST'])
@login_required
def novo_chamado():
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        descricao = request.form.get('descricao')
        prioridade = request.form.get('prioridade')
        departamento_id = request.form.get('departamento_id')

        chamado = Chamado(
            titulo=titulo,
            descricao=descricao,
            prioridade=prioridade,
            departamento_id=departamento_id,
            usuario_id=current_user.id,
            status='Aberto'
        )

        db.session.add(chamado)
        db.session.flush()

        interacao = Interacao(
            chamado_id=chamado.id,
            usuario_id=current_user.id,
            mensagem=f'Chamado aberto: {titulo}',
            tipo='sistema'
        )
        db.session.add(interacao)
        db.session.commit()

        flash('Chamado aberto com sucesso!', 'success')
        return redirect(url_for('main.ver_chamado', id=chamado.id))

    departamentos = Departamento.query.all()
    return render_template('novo_chamado.html', departamentos=departamentos)

@main.route('/chamado/<int:id>')
@login_required
def ver_chamado(id):
    chamado = Chamado.query.get_or_404(id)

    if not (current_user.is_admin() or 
            current_user.id == chamado.usuario_id or 
            current_user.id == chamado.atendente_id or
            (current_user.is_atendente() and current_user.departamento_id == chamado.departamento_id)):
        flash('Voce nao tem permissao para ver este chamado.', 'danger')
        return redirect(url_for('main.dashboard'))

    interacoes = Interacao.query.filter_by(chamado_id=id).order_by(Interacao.created_at.asc()).all()
    atendentes = Usuario.query.filter_by(departamento_id=chamado.departamento_id, tipo_usuario='atendente').all() if current_user.is_atendente() else []

    return render_template('ver_chamado.html', 
                         chamado=chamado, 
                         interacoes=interacoes,
                         atendentes=atendentes)

@main.route('/chamado/<int:id>/comentar', methods=['POST'])
@login_required
def comentar(id):
    chamado = Chamado.query.get_or_404(id)
    mensagem = request.form.get('mensagem')

    if not mensagem:
        flash('Mensagem nao pode estar vazia.', 'warning')
        return redirect(url_for('main.ver_chamado', id=id))

    interacao = Interacao(
        chamado_id=id,
        usuario_id=current_user.id,
        mensagem=mensagem,
        tipo='comentario'
    )

    chamado.data_atualizacao = datetime.utcnow()
    db.session.add(interacao)
    db.session.commit()

    flash('Comentario adicionado!', 'success')
    return redirect(url_for('main.ver_chamado', id=id))

@main.route('/chamado/<int:id>/atender', methods=['POST'])
@login_required
@atendente_required
def atender_chamado(id):
    chamado = Chamado.query.get_or_404(id)

    if chamado.status != 'Aberto':
        flash('Este chamado ja esta sendo atendido.', 'warning')
        return redirect(url_for('main.ver_chamado', id=id))

    chamado.atendente_id = current_user.id
    atualizar_status_chamado(id, 'Em atendimento', current_user.id, f'{current_user.nome} iniciou o atendimento')

    flash('Voce assumiu este chamado.', 'success')
    return redirect(url_for('main.ver_chamado', id=id))

@main.route('/chamado/<int:id>/status', methods=['POST'])
@login_required
@atendente_required
def alterar_status(id):
    chamado = Chamado.query.get_or_404(id)
    novo_status = request.form.get('status')
    mensagem = request.form.get('mensagem', '')

    if novo_status not in ['Aberto', 'Em atendimento', 'Aguardando usuario', 'Resolvido', 'Encerrado']:
        flash('Status invalido.', 'danger')
        return redirect(url_for('main.ver_chamado', id=id))

    atualizar_status_chamado(id, novo_status, current_user.id, mensagem if mensagem else None)

    if novo_status == 'Resolvido':
        flash('Chamado marcado como resolvido. Aguardando confirmacao do usuario.', 'success')
    else:
        flash(f'Status atualizado para {novo_status}.', 'success')

    return redirect(url_for('main.ver_chamado', id=id))

@main.route('/chamado/<int:id>/avaliar', methods=['POST'])
@login_required
def avaliar_chamado(id):
    chamado = Chamado.query.get_or_404(id)

    if chamado.usuario_id != current_user.id:
        flash('Apenas o solicitante pode avaliar.', 'danger')
        return redirect(url_for('main.ver_chamado', id=id))

    if chamado.status != 'Resolvido':
        flash('O chamado precisa estar resolvido para ser avaliado.', 'warning')
        return redirect(url_for('main.ver_chamado', id=id))

    avaliacao = request.form.get('avaliacao', type=int)
    if avaliacao and 1 <= avaliacao <= 5:
        chamado.avaliacao = avaliacao
        chamado.status = 'Encerrado'
        chamado.data_fechamento = datetime.utcnow()
        db.session.commit()
        flash('Obrigado pela avaliacao! Chamado encerrado.', 'success')
    else:
        flash('Avaliacao invalida.', 'warning')

    return redirect(url_for('main.ver_chamado', id=id))

@main.route('/relatorios')
@login_required
@atendente_required
def relatorios():
    dept_id = request.args.get('departamento', type=int)
    status = request.args.get('status')
    prioridade = request.args.get('prioridade')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    query = Chamado.query

    if dept_id:
        query = query.filter_by(departamento_id=dept_id)
    if status:
        query = query.filter_by(status=status)
    if prioridade:
        query = query.filter_by(prioridade=prioridade)
    if data_inicio:
        query = query.filter(Chamado.data_abertura >= datetime.strptime(data_inicio, '%Y-%m-%d'))
    if data_fim:
        query = query.filter(Chamado.data_abertura <= datetime.strptime(data_fim, '%Y-%m-%d'))

    chamados = query.order_by(Chamado.data_abertura.desc()).all()
    departamentos = Departamento.query.all()

    stats = {
        'total': len(chamados),
        'por_status': {},
        'por_prioridade': {},
        'por_departamento': {}
    }

    for c in chamados:
        stats['por_status'][c.status] = stats['por_status'].get(c.status, 0) + 1
        stats['por_prioridade'][c.prioridade] = stats['por_prioridade'].get(c.prioridade, 0) + 1
        dept_nome = c.departamento.nome if c.departamento else 'N/A'
        stats['por_departamento'][dept_nome] = stats['por_departamento'].get(dept_nome, 0) + 1

    return render_template('relatorios.html', 
                         chamados=chamados, 
                         departamentos=departamentos,
                         stats=stats,
                         filtros=request.args)

@main.route('/relatorios/exportar/<formato>')
@login_required
@atendente_required
def exportar_relatorio(formato):
    query = Chamado.query

    dept_id = request.args.get('departamento', type=int)
    status = request.args.get('status')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    if dept_id:
        query = query.filter_by(departamento_id=dept_id)
    if status:
        query = query.filter_by(status=status)
    if data_inicio:
        query = query.filter(Chamado.data_abertura >= datetime.strptime(data_inicio, '%Y-%m-%d'))
    if data_fim:
        query = query.filter(Chamado.data_abertura <= datetime.strptime(data_fim, '%Y-%m-%d'))

    chamados = query.all()

    data = []
    for c in chamados:
        data.append({
            'ID': c.id,
            'Titulo': c.titulo,
            'Status': c.status,
            'Prioridade': c.prioridade,
            'Departamento': c.departamento.nome if c.departamento else 'N/A',
            'Solicitante': c.solicitante.nome if c.solicitante else 'N/A',
            'Atendente': c.atendente.nome if c.atendente else 'N/A',
            'Data Abertura': c.data_abertura.strftime('%d/%m/%Y %H:%M'),
            'Data Fechamento': c.data_fechamento.strftime('%d/%m/%Y %H:%M') if c.data_fechamento else 'N/A',
            'Avaliacao': c.avaliacao if c.avaliacao else 'N/A'
        })

    df = pd.DataFrame(data)

    if formato == 'excel':
        output = BytesIO()
        df.to_excel(output, index=False, sheet_name='Chamados')
        output.seek(0)
        return 
    
    if formato == 'excel':
        output = BytesIO()
        df.to_excel(output, index=False, sheet_name='Chamados')
        output.seek(0)
        return Response(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': 'attachment; filename=relatorio_chamados.xlsx'}
        )

    elif formato == 'csv':
        output = BytesIO()
        df.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)
        return Response(
            output,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=relatorio_chamados.csv'}
        )

    else:
        flash('Formato nao suportado.', 'danger')
        return redirect(url_for('main.relatorios'))

@main.route('/admin/usuarios')
@login_required
@admin_required
def admin_usuarios():
    usuarios = Usuario.query.all()
    departamentos = Departamento.query.all()
    return render_template('admin_usuarios.html', usuarios=usuarios, departamentos=departamentos)

@main.route('/admin/usuario/novo', methods=['POST'])
@login_required
@admin_required
def admin_novo_usuario():
    nome = request.form.get('nome')
    email = request.form.get('email')
    senha = request.form.get('senha')
    departamento_id = request.form.get('departamento_id')
    tipo = request.form.get('tipo_usuario')

    if Usuario.query.filter_by(email=email).first():
        flash('Email ja cadastrado.', 'danger')
        return redirect(url_for('main.admin_usuarios'))

    usuario = Usuario(
        nome=nome,
        email=email,
        departamento_id=departamento_id,
        tipo_usuario=tipo
    )
    usuario.set_password(senha)

    db.session.add(usuario)
    db.session.commit()

    flash('Usuario criado com sucesso!', 'success')
    return redirect(url_for('main.admin_usuarios'))

@main.route('/admin/usuario/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def admin_toggle_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    if usuario.id == current_user.id:
        flash('Voce nao pode desativar sua propria conta.', 'danger')
        return redirect(url_for('main.admin_usuarios'))

    usuario.ativo = not usuario.ativo
    db.session.commit()
    status = 'ativado' if usuario.ativo else 'desativado'
    flash(f'Usuario {status} com sucesso!', 'success')
    return redirect(url_for('main.admin_usuarios'))