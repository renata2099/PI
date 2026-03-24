from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from app import db


# =========================
# DEPARTAMENTO
# =========================
class Departamento(db.Model):
    __tablename__ = 'departamentos'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    descricao = db.Column(db.String(255))
    ativo = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    usuarios = db.relationship('Usuario', backref='departamento', lazy=True)
    chamados = db.relationship('Chamado', backref='departamento', lazy=True)


# =========================
# USUÁRIO
# =========================
class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    senha_hash = db.Column(db.String(255), nullable=False)

    # Departamento principal (compatibilidade)
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamentos.id'))

    tipo_usuario = db.Column(db.String(20), default='comum')  # comum, atendente, admin
    ativo = db.Column(db.Boolean, default=True)

    receber_email = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # RELACIONAMENTOS
    chamados_abertos = db.relationship(
        'Chamado',
        foreign_keys='Chamado.usuario_id',
        backref='solicitante',
        lazy=True
    )

    chamados_responsavel = db.relationship(
        'Chamado',
        foreign_keys='Chamado.responsavel_id',
        backref='responsavel',
        lazy=True
    )

    chamados_atendidos = db.relationship(
        'Chamado',
        foreign_keys='Chamado.atendente_id',
        backref='atendente',
        lazy=True
    )

    interacoes = db.relationship('Interacao', backref='usuario', lazy=True)

    # 🔥 MULTI-DEPARTAMENTO (via tabela N:N)
    departamentos_vinculados = db.relationship(
        'UsuarioDepartamento',
        backref='usuario_ref',
        lazy=True,
        cascade='all, delete-orphan'
    )

    # MÉTODOS
    def set_password(self, password):
        self.senha_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.senha_hash, password)

    def is_admin(self):
        return self.tipo_usuario == 'admin'

    def is_atendente(self):
        return self.tipo_usuario in ['atendente', 'admin']

    def get_departamentos_ids(self):
        return [v.departamento_id for v in self.departamentos_vinculados]


# =========================
# USUARIO x DEPARTAMENTO (N:N)
# =========================
class UsuarioDepartamento(db.Model):
    __tablename__ = 'usuarios_departamentos'

    id = db.Column(db.Integer, primary_key=True)

    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamentos.id'), nullable=False)

    usuario = db.relationship('Usuario', overlaps="departamentos_vinculados,usuario_ref")
    departamento = db.relationship('Departamento', backref='usuarios_vinculados')


# =========================
# CHAMADO
# =========================
class Chamado(db.Model):
    __tablename__ = 'chamados'

    id = db.Column(db.Integer, primary_key=True)

    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=False)

    status = db.Column(db.String(30), default='Aberto')
    prioridade = db.Column(db.String(20), default='Media')

    departamento_id = db.Column(
        db.Integer,
        db.ForeignKey('departamentos.id'),
        nullable=False
    )

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey('usuarios.id'),
        nullable=False
    )

    responsavel_id = db.Column(
        db.Integer,
        db.ForeignKey('usuarios.id'),
        nullable=True
    )

    atendente_id = db.Column(
        db.Integer,
        db.ForeignKey('usuarios.id'),
        nullable=True
    )

    data_abertura = db.Column(db.DateTime, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    data_fechamento = db.Column(db.DateTime, nullable=True)

    avaliacao = db.Column(db.Integer, nullable=True)

    tempo_resolucao_horas = db.Column(db.Float, nullable=True)

    interacoes = db.relationship(
        'Interacao',
        backref='chamado',
        lazy=True,
        cascade='all, delete-orphan'
    )

    anexos = db.relationship(
        'Anexo',
        backref='chamado',
        lazy=True,
        cascade='all, delete-orphan'
    )

    notificacoes = db.relationship(
        'NotificacaoEmail',
        backref='chamado',
        lazy=True,
        cascade='all, delete-orphan'
    )


# =========================
# INTERAÇÕES
# =========================
class Interacao(db.Model):
    __tablename__ = 'interacoes'

    id = db.Column(db.Integer, primary_key=True)

    chamado_id = db.Column(
        db.Integer,
        db.ForeignKey('chamados.id'),
        nullable=False
    )

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey('usuarios.id'),
        nullable=False
    )

    mensagem = db.Column(db.Text, nullable=False)

    tipo = db.Column(db.String(20), default='comentario')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# ANEXOS
# =========================
class Anexo(db.Model):
    __tablename__ = 'anexos'

    id = db.Column(db.Integer, primary_key=True)

    chamado_id = db.Column(
        db.Integer,
        db.ForeignKey('chamados.id'),
        nullable=False
    )

    nome_arquivo = db.Column(db.String(255), nullable=False)
    caminho_arquivo = db.Column(db.String(500), nullable=False)

    tamanho_kb = db.Column(db.Integer)

    uploaded_by = db.Column(
        db.Integer,
        db.ForeignKey('usuarios.id'),
        nullable=False
    )

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# NOTIFICAÇÃO DE EMAIL
# =========================
class NotificacaoEmail(db.Model):
    __tablename__ = 'notificacoes_email'

    id = db.Column(db.Integer, primary_key=True)

    chamado_id = db.Column(
        db.Integer,
        db.ForeignKey('chamados.id'),
        nullable=False
    )

    destinatario = db.Column(db.String(100), nullable=False)
    assunto = db.Column(db.String(200))
    mensagem = db.Column(db.Text)

    enviado = db.Column(db.Boolean, default=False)
    erro = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    enviado_em = db.Column(db.DateTime, nullable=True)