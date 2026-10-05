-- OPCIONAL. Apenas em banco de demonstração vazio, depois de instalar o esquema.
-- Nomes, e-mails e patrimônios são fictícios. Nenhuma senha de login foi distribuída.
BEGIN;
SET LOCAL search_path = gestao_lab, public;
SET LOCAL TIME ZONE 'America/Sao_Paulo';

INSERT INTO laboratorio(id,nome,localizacao,chefe_usuario_id) VALUES
 (1,'Laboratório de Biologia','Bloco A',1),
 (2,'Laboratório de Química','Bloco B',10);
INSERT INTO usuario(id,laboratorio_id,nome,email,senha_hash) VALUES
 (1,1,'Chefe de demonstração A','chefe.a@example.org','pbkdf2_sha256$600000$e058831324eb90b6d0623d280f06ed9d$fvDd2Spe5RO7Fu32tAzL3PDx3X6+nrfss7ej81QEw6k='),
 (2,1,'Professora responsável A','professora.a@example.org','pbkdf2_sha256$600000$e058831324eb90b6d0623d280f06ed9d$fvDd2Spe5RO7Fu32tAzL3PDx3X6+nrfss7ej81QEw6k='),
 (3,1,'Aluno de demonstração A','aluno.a@example.org','pbkdf2_sha256$600000$e058831324eb90b6d0623d280f06ed9d$fvDd2Spe5RO7Fu32tAzL3PDx3X6+nrfss7ej81QEw6k='),
 (4,1,'Aluna de demonstração B','aluna.b@example.org','pbkdf2_sha256$600000$e058831324eb90b6d0623d280f06ed9d$fvDd2Spe5RO7Fu32tAzL3PDx3X6+nrfss7ej81QEw6k='),
 (10,2,'Chefe de demonstração B','chefe.b@example.org','pbkdf2_sha256$600000$e058831324eb90b6d0623d280f06ed9d$fvDd2Spe5RO7Fu32tAzL3PDx3X6+nrfss7ej81QEw6k='),
 (11,2,'Aluno de demonstração C','aluno.c@example.org','pbkdf2_sha256$600000$e058831324eb90b6d0623d280f06ed9d$fvDd2Spe5RO7Fu32tAzL3PDx3X6+nrfss7ej81QEw6k=');
INSERT INTO professor(usuario_id,laboratorio_id,programa_pos,ramal) VALUES
 (1,1,'Biologia','100'),(2,1,'Biologia','101'),(10,2,'Química','200');
INSERT INTO chefe_laboratorio(usuario_id,laboratorio_id) VALUES(1,1),(10,2);
INSERT INTO aluno(usuario_id,laboratorio_id,matricula,tipo,orientador_usuario_id) VALUES
 (3,1,'DEMO-001','GRADUACAO',2),(4,1,'DEMO-002','MESTRADO',2),(11,2,'DEMO-003','GRADUACAO',10);

SELECT contexto_operacao(1,'Cadastro inicial de demonstração');
INSERT INTO recurso(id,laboratorio_id,tipo,nome,responsavel_usuario_id) VALUES
 (101,1,'SALA','Sala de microscopia',2),(102,1,'SALA','Sala de preparo',1),
 (201,1,'BANCADA','Bancada B01',2),(202,1,'BANCADA','Bancada B02',1),
 (301,1,'EQUIPAMENTO','Microscópio',2),(302,1,'EQUIPAMENTO','Microscópio',2),
 (303,1,'EQUIPAMENTO','Geladeira',1),(304,1,'EQUIPAMENTO','Centrífuga',1),
 (305,1,'EQUIPAMENTO','Balança',1);
INSERT INTO sala(recurso_id,laboratorio_id,identificacao,localizacao,capacidade) VALUES
 (101,1,'201','Bloco A, segundo andar',12),(102,1,'202','Bloco A, segundo andar',8);
INSERT INTO bancada(recurso_id,laboratorio_id,sala_id,numero_identificacao) VALUES
 (201,1,101,'B01'),(202,1,101,'B02');
INSERT INTO equipamento(recurso_id,laboratorio_id,numero_patrimonio,bancada_id,sala_direta_id,complemento_local) VALUES
 (301,1,'PAT-001',201,NULL,'Posição 1'),(302,1,'PAT-002',201,NULL,'Posição 2'),
 (303,1,'PAT-003',NULL,101,'Parede norte'),(304,1,'PAT-004',202,NULL,'Posição central'),
 (305,1,'PAT-005',NULL,102,'Armário 1, prateleira 2');
INSERT INTO chave(id,laboratorio_id,codigo_copia,sala_id,bancada_id,designada_por,designada_para) VALUES
 (1,1,'S201-C1',101,NULL,2,NULL),(2,1,'S201-C2',101,NULL,2,NULL),
 (3,1,'B01-C1',NULL,201,2,NULL),(4,1,'S202-C1',102,NULL,1,NULL),
 (5,1,'S201-C3',101,NULL,2,4),(6,1,'S201-C4',101,NULL,2,NULL);
INSERT INTO item_estoque(id,laboratorio_id,nome,lote,unidade,quantidade,limite_estoque_baixo,validade) VALUES
 (1,1,'Reagente de demonstração','LOTE-001','mL',100,10,current_date+90),
 (2,1,'Material de demonstração','LOTE-002','unidade',0,5,current_date+90);

SELECT contexto_operacao(10,'Cadastro inicial de demonstração');
INSERT INTO recurso(id,laboratorio_id,tipo,nome,responsavel_usuario_id) VALUES
 (1101,2,'SALA','Sala de química',10),(1301,2,'EQUIPAMENTO','Balança',10);
INSERT INTO sala(recurso_id,laboratorio_id,identificacao,localizacao,capacidade) VALUES(1101,2,'101','Bloco B, térreo',10);
INSERT INTO equipamento(recurso_id,laboratorio_id,numero_patrimonio,sala_direta_id,complemento_local) VALUES(1301,2,'PAT-101',1101,'Bancada fixa da parede leste');

-- IDs explícitos acima não avançam sequências de IDENTITY automaticamente.
SELECT setval(pg_get_serial_sequence('laboratorio','id'),(SELECT max(id) FROM laboratorio));
SELECT setval(pg_get_serial_sequence('usuario','id'),(SELECT max(id) FROM usuario));
SELECT setval(pg_get_serial_sequence('recurso','id'),(SELECT max(id) FROM recurso));
SELECT setval(pg_get_serial_sequence('chave','id'),(SELECT max(id) FROM chave));
SELECT setval(pg_get_serial_sequence('item_estoque','id'),(SELECT max(id) FROM item_estoque));
COMMIT;
