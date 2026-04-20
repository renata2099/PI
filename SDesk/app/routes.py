from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from app.models import Chamado, Usuario, Departamento, Interacao, UsuarioDepartamento, db
from app.utils import admin_required, atendente_required, atualizar_status_chamado, get_estatisticas, enviar_email
from datetime import datetime
from sqlalchemy import func
import pandas as pd
from io import BytesIO
import random

main = Blueprint('main', __name__)

STATUS_VALIDOS = ['Aberto', 'Em atendimento', 'Aguardando usuario', 'Resolvido', 'Encerrado']


# =========================
# DASHBOARD
# =========================
@main.route('/dashboard')
@login_required
def dashboard():
    stats = get_estatisticas(current_user)

    if current_user.is_admin():
        chamados = Chamado.query.order_by(Chamado.data_atualizacao.desc()).limit(10).all()

    elif current_user.is_atendente():
        dept_ids = db.session.query(UsuarioDepartamento.departamento_id).filter_by(
            usuario_id=current_user.id
        )

        chamados = Chamado.query.filter(
            (Chamado.atendente_id == current_user.id) |
            (Chamado.responsavel_id == current_user.id) |
            (Chamado.departamento_id.in_(dept_ids))
        ).order_by(Chamado.data_atualizacao.desc()).limit(10).all()

    else:
        chamados = Chamado.query.filter_by(usuario_id=current_user.id)\
            .order_by(Chamado.data_atualizacao.desc()).limit(10).all()

    departamentos = Departamento.query.all()

    counts = db.session.query(
        Chamado.departamento_id,
        func.count(Chamado.id)
    ).group_by(Chamado.departamento_id).all()

    dept_stats = {d.nome: 0 for d in departamentos}

    for dept_id, total in counts:
        dept = next((d for d in departamentos if d.id == dept_id), None)
        if dept:
            dept_stats[dept.nome] = total

    return render_template('dashboard.html',
                           stats=stats,
                           chamados=chamados,
                           dept_stats=dept_stats)


# =========================
# NOVO CHAMADO
# =========================
@main.route('/chamado/novo', methods=['GET', 'POST'])
@login_required
def novo_chamado():
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        descricao = request.form.get('descricao')
        prioridade = request.form.get('prioridade')
        departamento_id = request.form.get('departamento_id')

        if not titulo or not descricao:
            flash('Preencha todos os campos.', 'danger')
            return redirect(url_for('main.novo_chamado'))

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

        # 🔥 RESPONSÁVEL AUTOMÁTICO
        atendentes = Usuario.query.join(UsuarioDepartamento).filter(
            UsuarioDepartamento.departamento_id == departamento_id,
            Usuario.tipo_usuario.in_(['atendente', 'admin']),
            Usuario.ativo == True
        ).all()

        if atendentes:
            escolhido = random.choice(atendentes)
            chamado.responsavel_id = escolhido.id

            # # 🔥 EMAIL
            # if escolhido.receber_email:
            #     enviar_email(
            #         escolhido.email,
            #         "Novo chamado atribuído",
            #         f"Você recebeu um chamado: {titulo}"
            #     )

        # INTERAÇÃO
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


# =========================
# 🔥 NOVO DEPARTAMENTO
# =========================
@main.route('/admin/departamento/novo', methods=['POST'])
@login_required
@admin_required
def novo_departamento():
    nome = request.form.get('nome')
    descricao = request.form.get('descricao')

    if Departamento.query.filter_by(nome=nome).first():
        flash('Departamento já existe.', 'danger')
        return redirect(url_for('main.admin_usuarios'))

    dept = Departamento(nome=nome, descricao=descricao)
    db.session.add(dept)
    db.session.commit()

    flash('Departamento criado!', 'success')
    return redirect(url_for('main.admin_usuarios'))


# =========================
# ADMIN USUARIOS
# =========================
@main.route('/admin/usuarios')
@login_required
@admin_required
def admin_usuarios():
    usuarios = Usuario.query.all()
    departamentos = Departamento.query.all()
    return render_template('admin_usuarios.html', usuarios=usuarios, departamentos=departamentos)


# =========================
# NOVO USUARIO
# =========================
@main.route('/admin/usuario/novo', methods=['POST'])
@login_required
@admin_required
def admin_novo_usuario():
    nome = request.form.get('nome')
    email = request.form.get('email')
    senha = request.form.get('senha')
    tipo = request.form.get('tipo_usuario')

    if Usuario.query.filter_by(email=email).first():
        flash('Email já existe.', 'danger')
        return redirect(url_for('main.admin_usuarios'))

    usuario = Usuario(nome=nome, email=email, tipo_usuario=tipo)
    usuario.set_password(senha)

    db.session.add(usuario)
    db.session.flush()

    # MULTI-DEPARTAMENTO
    departamentos_ids = request.form.getlist('departamentos')

    for dept_id in departamentos_ids:
        db.session.add(UsuarioDepartamento(
            usuario_id=usuario.id,
            departamento_id=dept_id
        ))

    db.session.commit()

    flash('Usuario criado!', 'success')
    return redirect(url_for('main.admin_usuarios'))


# =========================
# EDITAR USUARIO
# =========================
@main.route('/admin/usuario/<int:id>/editar', methods=['POST'])
@login_required
@admin_required
def admin_editar_usuario(id):
    usuario = Usuario.query.get_or_404(id)

    usuario.nome = request.form.get('nome')
    usuario.email = request.form.get('email')
    usuario.tipo_usuario = request.form.get('tipo_usuario')

    # limpa vínculos
    UsuarioDepartamento.query.filter_by(usuario_id=id).delete()

    departamentos_ids = request.form.getlist('departamentos')

    for dept_id in departamentos_ids:
        db.session.add(UsuarioDepartamento(
            usuario_id=id,
            departamento_id=dept_id
        ))

    db.session.commit()

    flash('Usuario atualizado!', 'success')
    return redirect(url_for('main.admin_usuarios'))