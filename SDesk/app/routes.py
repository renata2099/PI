from datetime import datetime, time
from io import BytesIO, StringIO
import csv
import random

import pandas as pd
from flask import Blueprint, Response, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app import db
from app.models import Chamado, Departamento, Interacao, Usuario, UsuarioDepartamento
from app.utils import (
    admin_required,
    atendente_required,
    atualizar_status_chamado,
    get_estatisticas,
    montar_email_interacao,
    notificar_interacao_chamado,
)

main = Blueprint("main", __name__)

STATUS_VALIDOS = ["Aberto", "Em atendimento", "Aguardando usuario", "Resolvido", "Encerrado"]


def _parse_date(value, end_of_day=False):
    if not value:
        return None

    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None

    if end_of_day:
        return datetime.combine(parsed.date(), time.max)

    return datetime.combine(parsed.date(), time.min)


def _base_chamados_query(usuario=None):
    query = Chamado.query.options(
        joinedload(Chamado.departamento),
        joinedload(Chamado.solicitante),
        joinedload(Chamado.atendente),
        joinedload(Chamado.responsavel),
    )

    if usuario and not usuario.is_admin():
        if usuario.is_atendente():
            dept_ids = db.session.query(UsuarioDepartamento.departamento_id).filter_by(
                usuario_id=usuario.id
            )
            query = query.filter(
                (Chamado.atendente_id == usuario.id)
                | (Chamado.responsavel_id == usuario.id)
                | (Chamado.departamento_id.in_(dept_ids))
            )
        else:
            query = query.filter_by(usuario_id=usuario.id)

    return query


def _apply_relatorio_filters(query):
    departamento = request.args.get("departamento", type=int)
    status = request.args.get("status")
    prioridade = request.args.get("prioridade")
    data_inicio = _parse_date(request.args.get("data_inicio"))
    data_fim = _parse_date(request.args.get("data_fim"), end_of_day=True)

    if departamento:
        query = query.filter(Chamado.departamento_id == departamento)
    if status:
        query = query.filter(Chamado.status == status)
    if prioridade:
        query = query.filter(Chamado.prioridade == prioridade)
    if data_inicio:
        query = query.filter(Chamado.data_abertura >= data_inicio)
    if data_fim:
        query = query.filter(Chamado.data_abertura <= data_fim)

    return query


def _build_relatorio_stats(chamados):
    por_status = {}
    por_prioridade = {}
    por_departamento = {}

    for chamado in chamados:
        por_status[chamado.status] = por_status.get(chamado.status, 0) + 1
        por_prioridade[chamado.prioridade] = por_prioridade.get(chamado.prioridade, 0) + 1

        nome_departamento = (
            chamado.departamento.nome if chamado.departamento else "Sem departamento"
        )
        por_departamento[nome_departamento] = por_departamento.get(nome_departamento, 0) + 1

    return {
        "total": len(chamados),
        "por_status": por_status,
        "por_prioridade": por_prioridade,
        "por_departamento": por_departamento,
    }


def _chamado_acessivel(chamado, usuario):
    if usuario.is_admin():
        return True

    if chamado.usuario_id == usuario.id:
        return True

    if usuario.is_atendente():
        dept_ids = set(usuario.get_departamentos_ids())
        return (
            chamado.atendente_id == usuario.id
            or chamado.responsavel_id == usuario.id
            or chamado.departamento_id in dept_ids
        )

    return False


@main.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@main.route("/dashboard")
@login_required
def dashboard():
    stats = get_estatisticas(current_user)

    chamados = (
        _base_chamados_query(current_user)
        .order_by(Chamado.data_atualizacao.desc())
        .limit(10)
        .all()
    )

    departamentos = Departamento.query.order_by(Departamento.nome.asc()).all()

    counts = (
        db.session.query(Chamado.departamento_id, func.count(Chamado.id))
        .group_by(Chamado.departamento_id)
        .all()
    )

    dept_stats = {d.nome: 0 for d in departamentos}

    for dept_id, total in counts:
        dept = next((d for d in departamentos if d.id == dept_id), None)
        if dept:
            dept_stats[dept.nome] = total

    return render_template(
        "dashboard.html",
        stats=stats,
        chamados=chamados,
        dept_stats=dept_stats,
    )


@main.route("/chamado/novo", methods=["GET", "POST"])
@login_required
def novo_chamado():
    if request.method == "POST":
        titulo = request.form.get("titulo")
        descricao = request.form.get("descricao")
        prioridade = request.form.get("prioridade")
        departamento_id = request.form.get("departamento_id", type=int)

        if not titulo or not descricao or not departamento_id:
            flash("Preencha todos os campos obrigatorios.", "danger")
            return redirect(url_for("main.novo_chamado"))

        chamado = Chamado(
            titulo=titulo,
            descricao=descricao,
            prioridade=prioridade,
            departamento_id=departamento_id,
            usuario_id=current_user.id,
            status="Aberto",
        )

        db.session.add(chamado)
        db.session.flush()

        atendentes = (
            Usuario.query.join(UsuarioDepartamento)
            .filter(
                UsuarioDepartamento.departamento_id == departamento_id,
                Usuario.tipo_usuario.in_(["atendente", "admin"]),
                Usuario.ativo == True,
            )
            .all()
        )

        if atendentes:
            escolhido = random.choice(atendentes)
            chamado.responsavel_id = escolhido.id

        assunto, corpo = montar_email_interacao(
            chamado,
            current_user,
            "Chamado aberto",
            descricao,
        )
        notificar_interacao_chamado(chamado, current_user, assunto, corpo)

        interacao = Interacao(
            chamado_id=chamado.id,
            usuario_id=current_user.id,
            mensagem=f"Chamado aberto: {titulo}",
            tipo="sistema",
        )

        db.session.add(interacao)
        db.session.commit()

        flash("Chamado aberto com sucesso!", "success")
        return redirect(url_for("main.ver_chamado", id=chamado.id))

    departamentos = Departamento.query.order_by(Departamento.nome.asc()).all()
    return render_template("novo_chamado.html", departamentos=departamentos)


@main.route("/chamado/<int:id>")
@login_required
def ver_chamado(id):
    chamado = (
        Chamado.query.options(
            joinedload(Chamado.departamento),
            joinedload(Chamado.solicitante),
            joinedload(Chamado.atendente),
            joinedload(Chamado.responsavel),
            joinedload(Chamado.interacoes).joinedload(Interacao.usuario),
        )
        .filter_by(id=id)
        .first_or_404()
    )

    if not _chamado_acessivel(chamado, current_user):
        flash("Voce nao tem permissao para visualizar este chamado.", "danger")
        return redirect(url_for("main.dashboard"))

    interacoes = sorted(chamado.interacoes, key=lambda item: item.created_at or datetime.min)
    return render_template("ver_chamado.html", chamado=chamado, interacoes=interacoes)


@main.route("/chamado/<int:id>/atender", methods=["POST"])
@login_required
@atendente_required
def atender_chamado(id):
    chamado = Chamado.query.get_or_404(id)

    if not _chamado_acessivel(chamado, current_user):
        flash("Voce nao pode assumir este chamado.", "danger")
        return redirect(url_for("main.dashboard"))

    chamado.atendente_id = current_user.id
    chamado.responsavel_id = current_user.id
    chamado.status = "Em atendimento"
    chamado.data_atualizacao = datetime.utcnow()

    db.session.add(
        Interacao(
            chamado_id=chamado.id,
            usuario_id=current_user.id,
            mensagem="Chamado assumido para atendimento.",
            tipo="status",
        )
    )
    assunto, corpo = montar_email_interacao(
        chamado,
        current_user,
        "Chamado assumido",
        "Chamado assumido para atendimento.",
    )
    notificar_interacao_chamado(chamado, current_user, assunto, corpo)
    db.session.commit()

    flash("Chamado assumido com sucesso!", "success")
    return redirect(url_for("main.ver_chamado", id=chamado.id))


@main.route("/chamado/<int:id>/status", methods=["POST"])
@login_required
@atendente_required
def alterar_status(id):
    chamado = Chamado.query.get_or_404(id)
    novo_status = request.form.get("status")
    mensagem = request.form.get("mensagem")

    if novo_status not in STATUS_VALIDOS:
        flash("Status invalido.", "danger")
        return redirect(url_for("main.ver_chamado", id=id))

    if not _chamado_acessivel(chamado, current_user):
        flash("Voce nao pode alterar este chamado.", "danger")
        return redirect(url_for("main.dashboard"))

    atualizar_status_chamado(id, novo_status, current_user.id, mensagem=mensagem or None)
    chamado = (
        Chamado.query.options(
            joinedload(Chamado.departamento),
            joinedload(Chamado.solicitante),
            joinedload(Chamado.atendente),
            joinedload(Chamado.responsavel),
        )
        .filter_by(id=id)
        .first()
    )
    assunto, corpo = montar_email_interacao(
        chamado,
        current_user,
        f"Status atualizado para {novo_status}",
        mensagem or f'Status alterado para "{novo_status}".',
    )
    notificar_interacao_chamado(chamado, current_user, assunto, corpo)
    db.session.commit()
    flash("Status atualizado com sucesso!", "success")
    return redirect(url_for("main.ver_chamado", id=id))


@main.route("/chamado/<int:id>/comentar", methods=["POST"])
@login_required
def comentar(id):
    chamado = Chamado.query.get_or_404(id)
    mensagem = request.form.get("mensagem", "").strip()

    if not _chamado_acessivel(chamado, current_user):
        flash("Voce nao pode comentar neste chamado.", "danger")
        return redirect(url_for("main.dashboard"))

    if not mensagem:
        flash("Digite uma mensagem para comentar.", "warning")
        return redirect(url_for("main.ver_chamado", id=id))

    db.session.add(
        Interacao(
            chamado_id=id,
            usuario_id=current_user.id,
            mensagem=mensagem,
            tipo="comentario",
        )
    )
    chamado.data_atualizacao = datetime.utcnow()
    assunto, corpo = montar_email_interacao(
        chamado,
        current_user,
        "Nova interacao",
        mensagem,
    )
    notificar_interacao_chamado(chamado, current_user, assunto, corpo)
    db.session.commit()

    flash("Comentario enviado!", "success")
    return redirect(url_for("main.ver_chamado", id=id))


@main.route("/chamado/<int:id>/avaliar", methods=["POST"])
@login_required
def avaliar_chamado(id):
    chamado = Chamado.query.get_or_404(id)
    avaliacao = request.form.get("avaliacao", type=int)

    if chamado.usuario_id != current_user.id:
        flash("Somente o solicitante pode avaliar este chamado.", "danger")
        return redirect(url_for("main.dashboard"))

    if chamado.status != "Resolvido":
        flash("Apenas chamados resolvidos podem ser avaliados.", "warning")
        return redirect(url_for("main.ver_chamado", id=id))

    if avaliacao not in [1, 2, 3, 4, 5]:
        flash("Selecione uma avaliacao valida.", "danger")
        return redirect(url_for("main.ver_chamado", id=id))

    chamado.avaliacao = avaliacao
    atualizar_status_chamado(
        chamado.id,
        "Encerrado",
        current_user.id,
        mensagem=f"Chamado encerrado com avaliacao {avaliacao}/5.",
    )
    chamado = (
        Chamado.query.options(
            joinedload(Chamado.departamento),
            joinedload(Chamado.solicitante),
            joinedload(Chamado.atendente),
            joinedload(Chamado.responsavel),
        )
        .filter_by(id=id)
        .first()
    )
    assunto, corpo = montar_email_interacao(
        chamado,
        current_user,
        "Chamado encerrado",
        f"Chamado encerrado com avaliacao {avaliacao}/5.",
    )
    notificar_interacao_chamado(chamado, current_user, assunto, corpo)
    db.session.commit()
    flash("Chamado avaliado e encerrado com sucesso!", "success")
    return redirect(url_for("main.ver_chamado", id=id))


@main.route("/relatorios")
@login_required
@atendente_required
def relatorios():
    query = _apply_relatorio_filters(_base_chamados_query(current_user))
    chamados = query.order_by(Chamado.data_abertura.desc()).all()
    departamentos = Departamento.query.order_by(Departamento.nome.asc()).all()
    stats = _build_relatorio_stats(chamados)

    return render_template(
        "relatorios.html",
        chamados=chamados,
        departamentos=departamentos,
        stats=stats,
    )


@main.route("/relatorios/exportar/<string:formato>")
@login_required
@atendente_required
def exportar_relatorio(formato):
    query = _apply_relatorio_filters(_base_chamados_query(current_user))
    chamados = query.order_by(Chamado.data_abertura.desc()).all()

    rows = []
    for chamado in chamados:
        rows.append(
            {
                "ID": chamado.id,
                "Titulo": chamado.titulo,
                "Status": chamado.status,
                "Prioridade": chamado.prioridade,
                "Departamento": chamado.departamento.nome if chamado.departamento else "",
                "Solicitante": chamado.solicitante.nome if chamado.solicitante else "",
                "Atendente": chamado.atendente.nome if chamado.atendente else "",
                "Data Abertura": chamado.data_abertura.strftime("%d/%m/%Y %H:%M")
                if chamado.data_abertura
                else "",
            }
        )

    if formato == "csv":
        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()) if rows else ["ID"])
        writer.writeheader()
        if rows:
            writer.writerows(rows)

        return Response(
            buffer.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=relatorio_chamados.csv"},
        )

    if formato == "excel":
        dataframe = pd.DataFrame(rows or [{"ID": ""}])
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            dataframe.to_excel(writer, index=False, sheet_name="Chamados")
        output.seek(0)

        return Response(
            output.getvalue(),
            mimetype=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            headers={"Content-Disposition": "attachment; filename=relatorio_chamados.xlsx"},
        )

    flash("Formato de exportacao invalido.", "danger")
    return redirect(url_for("main.relatorios"))


@main.route("/admin/departamento/novo", methods=["POST"])
@login_required
@admin_required
def novo_departamento():
    nome = request.form.get("nome")
    descricao = request.form.get("descricao")

    if not nome:
        flash("Informe o nome do departamento.", "danger")
        return redirect(url_for("main.admin_usuarios"))

    if Departamento.query.filter_by(nome=nome).first():
        flash("Departamento ja existe.", "danger")
        return redirect(url_for("main.admin_usuarios"))

    dept = Departamento(nome=nome, descricao=descricao)
    db.session.add(dept)
    db.session.commit()

    flash("Departamento criado!", "success")
    return redirect(url_for("main.admin_usuarios"))


@main.route("/admin/departamento/<int:id>/editar", methods=["POST"])
@login_required
@admin_required
def editar_departamento(id):
    departamento = Departamento.query.get_or_404(id)
    nome = request.form.get("nome", "").strip()
    descricao = request.form.get("descricao", "").strip()

    if not nome:
        flash("Informe o nome do departamento.", "danger")
        return redirect(url_for("main.admin_usuarios"))

    existente = Departamento.query.filter(Departamento.nome == nome, Departamento.id != id).first()
    if existente:
        flash("Ja existe outro departamento com esse nome.", "danger")
        return redirect(url_for("main.admin_usuarios"))

    departamento.nome = nome
    departamento.descricao = descricao or None
    db.session.commit()

    flash("Departamento atualizado com sucesso!", "success")
    return redirect(url_for("main.admin_usuarios"))


@main.route("/admin/usuarios")
@login_required
@admin_required
def admin_usuarios():
    usuarios = Usuario.query.order_by(Usuario.nome.asc()).all()
    departamentos = Departamento.query.order_by(Departamento.nome.asc()).all()
    return render_template(
        "admin_usuarios.html", usuarios=usuarios, departamentos=departamentos
    )


@main.route("/admin/usuario/novo", methods=["POST"])
@login_required
@admin_required
def admin_novo_usuario():
    nome = request.form.get("nome")
    email = request.form.get("email")
    senha = request.form.get("senha")
    tipo = request.form.get("tipo_usuario")

    if Usuario.query.filter_by(email=email).first():
        flash("Email ja existe.", "danger")
        return redirect(url_for("main.admin_usuarios"))

    usuario = Usuario(nome=nome, email=email, tipo_usuario=tipo)
    usuario.set_password(senha)

    db.session.add(usuario)
    db.session.flush()

    departamento_unico = request.form.get("departamento_id")
    departamentos_ids = request.form.getlist("departamentos")
    if departamento_unico and departamento_unico not in departamentos_ids:
        departamentos_ids.append(departamento_unico)

    if departamentos_ids:
        usuario.departamento_id = int(departamentos_ids[0])

    for dept_id in departamentos_ids:
        db.session.add(
            UsuarioDepartamento(
                usuario_id=usuario.id,
                departamento_id=int(dept_id),
            )
        )

    db.session.commit()

    flash("Usuario criado!", "success")
    return redirect(url_for("main.admin_usuarios"))


@main.route("/admin/usuario/<int:id>/editar", methods=["POST"])
@login_required
@admin_required
def admin_editar_usuario(id):
    usuario = Usuario.query.get_or_404(id)

    usuario.nome = request.form.get("nome")
    usuario.email = request.form.get("email")
    usuario.tipo_usuario = request.form.get("tipo_usuario")

    UsuarioDepartamento.query.filter_by(usuario_id=id).delete()

    departamentos_ids = request.form.getlist("departamentos")
    departamento_unico = request.form.get("departamento_id")
    if departamento_unico and departamento_unico not in departamentos_ids:
        departamentos_ids.append(departamento_unico)

    if departamentos_ids:
        usuario.departamento_id = int(departamentos_ids[0])
    else:
        usuario.departamento_id = None

    for dept_id in departamentos_ids:
        db.session.add(
            UsuarioDepartamento(
                usuario_id=id,
                departamento_id=int(dept_id),
            )
        )

    db.session.commit()

    flash("Usuario atualizado!", "success")
    return redirect(url_for("main.admin_usuarios"))


@main.route("/admin/usuario/<int:id>/toggle", methods=["POST"])
@login_required
@admin_required
def admin_toggle_usuario(id):
    usuario = Usuario.query.get_or_404(id)

    if usuario.id == current_user.id:
        flash("Voce nao pode desativar seu proprio usuario.", "warning")
        return redirect(url_for("main.admin_usuarios"))

    usuario.ativo = not usuario.ativo
    db.session.commit()

    flash(
        "Usuario ativado com sucesso!" if usuario.ativo else "Usuario desativado com sucesso!",
        "success",
    )
    return redirect(url_for("main.admin_usuarios"))
