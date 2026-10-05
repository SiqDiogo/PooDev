# Migrações

`BancoLaboratorioPostgreSQL.sql` instala a versão 1 do schema. Alterações de uma instalação existente devem ser registradas nesta pasta.

Use nomes sequenciais, por exemplo `002_adicionar_campo.sql`, `003_ajustar_indice.sql`. Uma migração já aplicada não deve ser editada; corrija com outra versão.

Cada migração deve documentar a alteração, executar as operações em transação e registrar sua versão em `gestao_lab.schema_versao`. Antes de aplicar, consulte a última versão e execute as pendentes em ordem.

Exemplo de estrutura para a versão 2:

```sql
BEGIN;
-- ALTER TABLE, CREATE INDEX ou outras alterações necessárias.
INSERT INTO gestao_lab.schema_versao(versao, descricao)
VALUES (2, 'Descrição da alteração');
COMMIT;
```

O exemplo define a convenção; não representa uma migração a ser executada. Ainda não há alterações posteriores à versão 1. Valide cada migração em banco de teste e mantenha um backup local antes de atualizar dados existentes.
