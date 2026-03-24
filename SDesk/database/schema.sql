-- Sistema de Gerenciamento de Chamados - SQL Server
-- Criacao do Banco de Dados

IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'SistemaChamados')
BEGIN
    CREATE DATABASE SistemaChamados;
END
GO

USE SistemaChamados;
GO

-- Tabela de Departamentos
IF OBJECT_ID('departamentos', 'U') IS NOT NULL DROP TABLE departamentos;
CREATE TABLE departamentos (
    id INT IDENTITY(1,1) PRIMARY KEY,
    nome VARCHAR(100) NOT NULL UNIQUE,
    descricao VARCHAR(255),
    created_at DATETIME DEFAULT GETDATE(),
    updated_at DATETIME DEFAULT GETDATE()
);

-- Tabela de Usuarios
IF OBJECT_ID('usuarios', 'U') IS NOT NULL DROP TABLE usuarios;
CREATE TABLE usuarios (
    id INT IDENTITY(1,1) PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    senha_hash VARCHAR(255) NOT NULL,
    departamento_id INT,
    tipo_usuario VARCHAR(20) DEFAULT 'comum' CHECK (tipo_usuario IN ('comum', 'atendente', 'admin')),
    ativo BIT DEFAULT 1,
    created_at DATETIME DEFAULT GETDATE(),
    updated_at DATETIME DEFAULT GETDATE(),
    FOREIGN KEY (departamento_id) REFERENCES departamentos(id)
);

-- Tabela de Chamados
IF OBJECT_ID('chamados', 'U') IS NOT NULL DROP TABLE chamados;
CREATE TABLE chamados (
    id INT IDENTITY(1,1) PRIMARY KEY,
    titulo VARCHAR(200) NOT NULL,
    descricao TEXT NOT NULL,
    status VARCHAR(30) DEFAULT 'Aberto' CHECK (status IN ('Aberto', 'Em atendimento', 'Aguardando usuario', 'Resolvido', 'Encerrado')),
    prioridade VARCHAR(20) DEFAULT 'Media' CHECK (prioridade IN ('Baixa', 'Media', 'Alta', 'Critica')),
    departamento_id INT NOT NULL,
    usuario_id INT NOT NULL,
    atendente_id INT NULL,
    data_abertura DATETIME DEFAULT GETDATE(),
    data_atualizacao DATETIME DEFAULT GETDATE(),
    data_fechamento DATETIME NULL,
    avaliacao INT NULL CHECK (avaliacao BETWEEN 1 AND 5),
    FOREIGN KEY (departamento_id) REFERENCES departamentos(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY (atendente_id) REFERENCES usuarios(id)
);

-- Tabela de Interacoes (Chat/Historico)
IF OBJECT_ID('interacoes', 'U') IS NOT NULL DROP TABLE interacoes;
CREATE TABLE interacoes (
    id INT IDENTITY(1,1) PRIMARY KEY,
    chamado_id INT NOT NULL,
    usuario_id INT NOT NULL,
    mensagem TEXT NOT NULL,
    tipo VARCHAR(20) DEFAULT 'comentario' CHECK (tipo IN ('comentario', 'status', 'sistema')),
    created_at DATETIME DEFAULT GETDATE(),
    FOREIGN KEY (chamado_id) REFERENCES chamados(id) ON DELETE CASCADE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

-- Tabela de Anexos (para futura implementacao)
IF OBJECT_ID('anexos', 'U') IS NOT NULL DROP TABLE anexos;
CREATE TABLE anexos (
    id INT IDENTITY(1,1) PRIMARY KEY,
    chamado_id INT NOT NULL,
    nome_arquivo VARCHAR(255) NOT NULL,
    caminho_arquivo VARCHAR(500) NOT NULL,
    tamanho_kb INT,
    uploaded_by INT NOT NULL,
    uploaded_at DATETIME DEFAULT GETDATE(),
    FOREIGN KEY (chamado_id) REFERENCES chamados(id) ON DELETE CASCADE,
    FOREIGN KEY (uploaded_by) REFERENCES usuarios(id)
);

-- Indices para performance
CREATE INDEX idx_chamados_status ON chamados(status);
CREATE INDEX idx_chamados_departamento ON chamados(departamento_id);
CREATE INDEX idx_chamados_usuario ON chamados(usuario_id);
CREATE INDEX idx_chamados_atendente ON chamados(atendente_id);
CREATE INDEX idx_interacoes_chamado ON interacoes(chamado_id);
CREATE INDEX idx_usuarios_email ON usuarios(email);
GO

-- Dados Iniciais
INSERT INTO departamentos (nome, descricao) VALUES 
    ('TI', 'Tecnologia da Informacao'),
    ('RH', 'Recursos Humanos'),
    ('Financeiro', 'Departamento Financeiro'),
    ('Comercial', 'Vendas e Marketing'),
    ('Administrativo', 'Administracao Geral'),
    ('Suporte Tecnico', 'Suporte Interno');

-- Usuarios de teste (senha: 'senha123' hasheada com bcrypt)
INSERT INTO usuarios (nome, email, senha_hash, departamento_id, tipo_usuario) VALUES 
    ('Administrador', 'admin@sistema.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiAYMyzJ/Ihq', 1, 'admin'),
    ('Tecnico TI', 'ti@sistema.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiAYMyzJ/Ihq', 1, 'atendente'),
    ('Analista RH', 'rh@sistema.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiAYMyzJ/Ihq', 2, 'atendente'),
    ('Usuario Comum', 'usuario@sistema.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiAYMyzJ/Ihq', 3, 'comum');

-- Chamados de exemplo
INSERT INTO chamados (titulo, descricao, status, prioridade, departamento_id, usuario_id, atendente_id) VALUES 
    ('Computador nao liga', 'O computador da estacao 5 nao esta ligando desde ontem', 'Em atendimento', 'Alta', 1, 4, 2),
    ('Solicitacao de ferias', 'Preciso agendar ferias para dezembro', 'Aberto', 'Media', 2, 4, NULL),
    ('Erro no sistema ERP', 'Nao consigo emitir nota fiscal', 'Resolvido', 'Critica', 1, 4, 2);

-- Interacoes de exemplo
INSERT INTO interacoes (chamado_id, usuario_id, mensagem, tipo) VALUES 
    (1, 2, 'Estou verificando o problema do computador', 'comentario'),
    (1, 2, 'Status alterado para Em atendimento', 'status'),
    (3, 2, 'Problema resolvido, sistema reiniciado', 'comentario'),
    (3, 2, 'Status alterado para Resolvido', 'status');

PRINT 'Banco de dados criado com sucesso!';
PRINT 'Usuarios de teste:';
PRINT '- admin@sistema.com / senha123 (Admin)';
PRINT '- ti@sistema.com / senha123 (Atendente TI)';
PRINT '- rh@sistema.com / senha123 (Atendente RH)';
PRINT '- usuario@sistema.com / senha123 (Usuario)';
GO