-- Dados simulados padrão (seed) para o banco relacional de votação
-- Inserções nas tabelas criadas em schema.sql

-- 1. Domínio Centro Acadêmico (CA)
INSERT OR REPLACE INTO discentes (ra, nome, curso, matricula_ativa, formando_proximo_semestre, suspenso) VALUES
('247314', 'Lucas Bussinger', 'Engenharia de Software', 1, 0, 0),
('242352', 'Gabriel Montagna', 'Engenharia de Software', 1, 0, 0),
('281199', 'Gabriel Antunes', 'Engenharia de Software', 1, 0, 0),
('254467', 'Lucas Lembo', 'Engenharia de Software', 1, 0, 0),
('205237', 'Rafael Dosso', 'Engenharia de Software', 1, 0, 0),
('111222', 'Mariana Veterana', 'Engenharia de Software', 1, 1, 0),
('333444', 'Carlos Trancado', 'Engenharia de Software', 0, 0, 0),
('555666', 'Juliana Suspensa', 'Engenharia de Software', 1, 0, 1);

INSERT OR REPLACE INTO chapas (nome, plano_gestao, ativa) VALUES
('Chapa Renova', 'Integração universidade-empresa e melhorias laboratoriais.', 1),
('Chapa Futuro', 'Acessibilidade, transparência e acolhimento estudantil.', 1),
('Chapa Invalida', 'Gestão de transição rápida.', 1),
('Chapa Desistente', 'Desistência formal antes do pleito.', 0);

INSERT OR REPLACE INTO chapa_integrantes (chapa_nome, discente_ra) VALUES
('Chapa Renova', '247314'),
('Chapa Renova', '242352'),
('Chapa Renova', '281199'),
('Chapa Futuro', '254467'),
('Chapa Futuro', '205237'),
('Chapa Invalida', '111222'),
('Chapa Desistente', '247314');

-- 2. Domínio Assembleia de Acionistas
INSERT OR REPLACE INTO acionistas (id, nome, acoes_ordinarias, acoes_preferenciais, bloqueado, ativo) VALUES
('AC-001', 'Holding Alpha Participações S.A.', 500000, 100000, 0, 1),
('AC-002', 'Fundo Beta Capital', 300000, 50000, 0, 1),
('AC-003', 'Investidor Individual Silva', 150000, 0, 0, 1),
('AC-004', 'Investidor Sem Direito a Voto', 0, 80000, 0, 1),
('AC-005', 'Acionista Bloqueado Judicial', 100000, 0, 1, 1),
('AC-006', 'Acionista Desativado', 50000, 0, 0, 0);

INSERT OR REPLACE INTO procuracoes (outorgante_id, procurador_id, data_expiracao, ativa) VALUES
('AC-001', 'PROC-101', '2030-12-31T23:59:59Z', 1),
('AC-002', 'PROC-102', '2020-01-01T00:00:00Z', 1),
('AC-003', 'PROC-103', '2030-12-31T23:59:59Z', 0);

INSERT OR REPLACE INTO candidatos_conselho (id, nome, titular_acoes, conflito_interesse, ativo) VALUES
('CONS-01', 'Dr. Roberto Conselheiro', 1, 0, 1),
('CONS-02', 'Concorrente Direto Impedido', 1, 1, 1);

-- 3. Domínio Congresso Nacional
INSERT OR REPLACE INTO parlamentares (id, nome, casa, partido, uf, em_exercicio, licenciado, suspenso) VALUES
('DEP-001', 'Deputada Maria Silva', 'CAMARA', 'PUNI', 'SP', 1, 0, 0),
('DEP-002', 'Deputado João Santos', 'CAMARA', 'PENG', 'RJ', 1, 0, 0),
('DEP-003', 'Deputado Licenciado (Ministro)', 'CAMARA', 'PUNI', 'MG', 0, 1, 0),
('DEP-004', 'Deputado Suspenso', 'CAMARA', 'PENG', 'RS', 0, 0, 1),
('SEN-001', 'Senadora Ana Oliveira', 'SENADO', 'PUNI', 'SP', 1, 0, 0),
('SEN-002', 'Senador Marcos Souza', 'SENADO', 'PENG', 'BA', 1, 0, 0),
('SEN-003', 'Senador Licenciado', 'SENADO', 'PUNI', 'PR', 0, 1, 0);

INSERT OR REPLACE INTO materias_legislativas (id, tipo, casa_atual, titulo, ativa) VALUES
('PL-101/2026', 'LEI_ORDINARIA', 'CAMARA', 'Incentivo a laboratórios de software aberto.', 1),
('PLP-202/2026', 'LEI_COMPLEMENTAR', 'CAMARA', 'Normas complementares para votação eletrônica auditável.', 1),
('PEC-50/2026', 'PEC', 'SENADO', 'Emenda Constitucional de Modernização da Cidadania Digital.', 1),
('PL-ARQUIVADO', 'LEI_ORDINARIA', 'CAMARA', 'Projeto retirado de pauta.', 0);
