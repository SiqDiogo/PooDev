-- Conferência de leitura: pode executar no banco instalado pelo pgAdmin.
-- Esperado: banco escolhido, PostgreSQL >=16, isolamento read committed,
-- 26 tabelas, versão 1 (ou a última migração), extensão e operações presentes.
SELECT current_database() AS banco,
       current_setting('server_version') AS versao_postgresql,
       current_setting('server_version_num')::integer >= 160000 AS versao_suportada,
       current_setting('default_transaction_isolation') AS isolamento_padrao;

SELECT count(*) AS tabelas, count(*) = 26 AS estrutura_inicial_completa
FROM information_schema.tables
WHERE table_schema = 'gestao_lab' AND table_type = 'BASE TABLE';

SELECT versao, descricao, aplicada_em
FROM gestao_lab.schema_versao ORDER BY versao DESC;

SELECT extname, extversion FROM pg_extension WHERE extname = 'btree_gist';

SELECT to_regprocedure('gestao_lab.criar_reserva(bigint,bigint,timestamptz,timestamptz)') IS NOT NULL AS criar_reserva,
       to_regprocedure('gestao_lab.cancelar_reserva(bigint,bigint,text)') IS NOT NULL AS cancelar_reserva,
       to_regprocedure('gestao_lab.retirar_chave(bigint,bigint,bigint,bigint)') IS NOT NULL AS retirar_chave,
       to_regprocedure('gestao_lab.devolver_chave(bigint,bigint)') IS NOT NULL AS devolver_chave;

SELECT EXISTS (
    SELECT 1 FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'gestao_lab' AND t.relname = 'reserva_recurso'
      AND c.conname = 'reserva_recurso_sem_sobreposicao' AND c.contype = 'x'
) AS exclusao_de_sobreposicao_instalada;
