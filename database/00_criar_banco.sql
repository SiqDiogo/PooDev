-- Executar conectado ao banco administrativo "postgres", fora de transação.
-- Se o banco já existir, não execute novamente; conecte-se a ele.
CREATE DATABASE gestao_laboratorio WITH ENCODING = 'UTF8' TEMPLATE = template0;
