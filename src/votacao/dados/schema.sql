-- Esquema relacional de banco de dados mockado para o sistema de votação
-- Abrange os três domínios: Centro Acadêmico, Assembleia de Acionistas e Congresso Nacional

-- 1. Domínio Centro Acadêmico (CA)
CREATE TABLE IF NOT EXISTS discentes (
    ra TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    curso TEXT NOT NULL,
    matricula_ativa INTEGER NOT NULL DEFAULT 1,
    formando_proximo_semestre INTEGER NOT NULL DEFAULT 0,
    suspenso INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chapas (
    nome TEXT PRIMARY KEY,
    plano_gestao TEXT DEFAULT '',
    ativa INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS chapa_integrantes (
    chapa_nome TEXT NOT NULL,
    discente_ra TEXT NOT NULL,
    PRIMARY KEY (chapa_nome, discente_ra),
    FOREIGN KEY (chapa_nome) REFERENCES chapas(nome) ON DELETE CASCADE,
    FOREIGN KEY (discente_ra) REFERENCES discentes(ra) ON DELETE RESTRICT
);

-- 2. Domínio Assembleia de Acionistas
CREATE TABLE IF NOT EXISTS acionistas (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    acoes_ordinarias INTEGER NOT NULL DEFAULT 0 CHECK (acoes_ordinarias >= 0),
    acoes_preferenciais INTEGER NOT NULL DEFAULT 0 CHECK (acoes_preferenciais >= 0),
    bloqueado INTEGER NOT NULL DEFAULT 0,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS procuracoes (
    outorgante_id TEXT NOT NULL,
    procurador_id TEXT NOT NULL,
    data_expiracao TEXT,
    ativa INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (outorgante_id, procurador_id),
    FOREIGN KEY (outorgante_id) REFERENCES acionistas(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS candidatos_conselho (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    titular_acoes INTEGER NOT NULL DEFAULT 1,
    conflito_interesse INTEGER NOT NULL DEFAULT 0,
    ativo INTEGER NOT NULL DEFAULT 1
);

-- 3. Domínio Congresso Nacional
CREATE TABLE IF NOT EXISTS parlamentares (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    casa TEXT NOT NULL CHECK (casa IN ('CAMARA', 'SENADO')),
    partido TEXT NOT NULL,
    uf TEXT NOT NULL,
    em_exercicio INTEGER NOT NULL DEFAULT 1,
    licenciado INTEGER NOT NULL DEFAULT 0,
    suspenso INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS materias_legislativas (
    id TEXT PRIMARY KEY,
    tipo TEXT NOT NULL CHECK (tipo IN ('LEI_ORDINARIA', 'LEI_COMPLEMENTAR', 'PEC')),
    casa_atual TEXT NOT NULL CHECK (casa_atual IN ('CAMARA', 'SENADO')),
    titulo TEXT DEFAULT '',
    ativa INTEGER NOT NULL DEFAULT 1
);
