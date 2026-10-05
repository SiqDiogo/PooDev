# Banco de dados

Banco PostgreSQL do Sistema de Gestão de Laboratório de Pesquisa. Armazena usuários, recursos físicos, reservas, chaves, estoque, protocolos e histórico de operações.

| Configuração | Valor |
|---|---|
| PostgreSQL | 16 ou superior |
| Banco | `gestao_laboratorio` |
| Schema | `gestao_lab` |
| Extensão | `btree_gist` |
| Isolamento das operações de domínio | `READ COMMITTED` |
| Versão inicial do schema | 1 |

## Instalação

### pgAdmin

1. No Query Tool do banco `postgres`, execute [00_criar_banco.sql](00_criar_banco.sql) com autocommit habilitado.
2. Atualize a lista de bancos e abra o Query Tool em `gestao_laboratorio`.
3. Execute [BancoLaboratorioPostgreSQL.sql](BancoLaboratorioPostgreSQL.sql). O arquivo cria as tabelas, índices, funções, views e triggers.
4. Execute [08_verificar_instalacao.sql](08_verificar_instalacao.sql) para conferir a instalação.

O script de instalação deve ser executado uma vez em um banco sem o schema `gestao_lab`. Atualizações de uma instalação existente devem ser feitas por migração.

### Terminal

Na raiz do repositório:

```sh
createdb -h localhost -U postgres -E UTF8 -T template0 gestao_laboratorio
psql -h localhost -U postgres -d gestao_laboratorio -v ON_ERROR_STOP=1 -f database/BancoLaboratorioPostgreSQL.sql
psql -h localhost -U postgres -d gestao_laboratorio -v ON_ERROR_STOP=1 -f database/08_verificar_instalacao.sql
```

Use uma conta SQL com permissão para criar o banco, o schema e a extensão. A senha da conexão é informada localmente.

## Arquivos

| Arquivo ou pasta | Uso |
|---|---|
| `00_criar_banco.sql` | Criação do banco. |
| `BancoLaboratorioPostgreSQL.sql` | Definição completa do schema e das regras. |
| `03_dados_exemplo.sql` | Carga fictícia para desenvolvimento e testes. |
| `04_consultas_exemplo.sql` | Consultas de localização, reservas, chaves, estoque e histórico. |
| `05_testes_integridade.sql` | Verificações das regras e rejeição de operações inválidas. |
| `06_testar_concorrencia.py` | Testes com duas conexões PostgreSQL. |
| `07_validar_pglite.mjs` | Execução da suíte em PostgreSQL via WebAssembly. |
| `08_verificar_instalacao.sql` | Conferência da versão, tabelas, extensão e operações principais. |
| `docs/` | Modelo relacional, dicionário de dados e relatório de validação. |
| `migrations/` | Alterações incrementais do schema. |

## Organização dos dados

O schema possui 26 tabelas. `usuario` e `recurso` são as bases das hierarquias do domínio; as subclasses usam a mesma chave da base.

| Grupo | Tabelas principais |
|---|---|
| Usuários | `laboratorio`, `usuario`, `aluno`, `professor`, `chefe_laboratorio`, `sessao_usuario` |
| Recursos | `recurso`, `sala`, `bancada`, `equipamento` |
| Reservas | `reserva`, `reserva_recurso` |
| Chaves | `chave`, `emprestimo_chave`, `ocorrencia_chave` |
| Estoque | `item_estoque`, `movimentacao_estoque` |
| Protocolos | `protocolo`, `protocolo_equipamento` |
| Controle | `proibicao_aluno_equipamento`, `solicitacao_reativacao`, `ocorrencia` |
| Notificações | `notificacao`, `envio_email` |
| Auditoria e versão | `historico_uso`, `schema_versao` |

Os vínculos usam chaves estrangeiras compostas para manter usuários, responsáveis e recursos no mesmo laboratório. Cadastros de usuário e recurso precisam gravar a base e o subtipo na mesma transação. A criação inicial de laboratório e Chefe também deve ocorrer em uma única transação; as referências circulares são verificadas no COMMIT.

## Recursos e localização

Cada bancada pertence a uma sala. Um equipamento fica em uma bancada ou diretamente em uma sala, com uma única localização estrutural. `complemento_local` registra a posição dentro desse local, como armário, prateleira ou posição na bancada.

O patrimônio identifica uma unidade física e é único em todo o sistema. Unidades com o mesmo nome são permitidas.

```sql
SELECT recurso_nome, numero_patrimonio, laboratorio_nome,
       sala_identificacao, bancada_identificacao, complemento_local
FROM gestao_lab.vw_local_equipamento
ORDER BY laboratorio_id, sala_id, bancada_id, numero_patrimonio;
```

## Reservas

| Reserva solicitada | Recursos abrangidos |
|---|---|
| Equipamento | Apenas a unidade escolhida. |
| Bancada | Bancada e todos os seus equipamentos. |
| Sala | Sala, bancadas e todos os equipamentos da sala. |

`reserva_recurso` é preenchida automaticamente. A restrição de exclusão impede sobreposição do mesmo recurso nos intervalos confirmados. O período inclui o início e exclui o fim; reservas consecutivas podem terminar e começar no mesmo horário.

Equipamentos distintos da mesma bancada podem ser reservados individualmente. Uma unidade reservada impede reservar o conjunto da bancada ou da sala durante o mesmo período.

As funções verificam disponibilidade, proibições, duração máxima e quantidade simultânea por usuário. Os limites são configurados no laboratório; `NULL` significa limite ainda não definido. Uma reserva de conjunto conta como uma solicitação.

Com a carga de exemplo instalada:

```sql
SELECT gestao_lab.criar_reserva(
    3, 301,
    current_timestamp + interval '1 day',
    current_timestamp + interval '26 hours'
);
```

A função retorna o ID da reserva. Para cancelar, use `cancelar_reserva(ator, reserva, motivo)`. Recurso, usuário e período de uma reserva confirmada são imutáveis. Alterações exigem cancelamento e nova reserva.

Mudança de localização ou composição que afete reservas vigentes ou futuras é bloqueada até regularização. O local registrado na confirmação permanece no histórico.

## Chaves

Cada registro em `chave` representa uma cópia física, com código próprio e destino em sala ou bancada. O Chefe ou Professor responsável pode designar a cópia. `designada_para` preenchido restringe a cópia a um usuário; `NULL` permite compartilhamento entre usuários autorizados.

A reserva autoriza a retirada de uma cópia compatível e disponível. `retirar_chave` registra o portador, a reserva e o responsável pela entrega. Um índice parcial permite apenas um empréstimo aberto por cópia.

`devolver_chave` encerra a posse após a devolução física. Cancelar ou concluir a reserva mantém um empréstimo aberto. Extravio e indisponibilidade são registrados por `registrar_ocorrencia_chave`.

```sql
SELECT codigo_copia, estado, portador_usuario_id, retirada_em
FROM gestao_lab.vw_chave_estado
ORDER BY codigo_copia;
```

## Estoque, protocolos e notificações

`movimentar_estoque` altera o saldo e registra quantidade anterior, variação, quantidade posterior, motivo e ator. Saldo negativo é rejeitado. Itens podem ser separados por lote; quando o lote não é informado, usa-se `SEM_LOTE`.

`avaliar_alertas_estoque` identifica quantidade baixa e validade próxima ou vencida. A mesma condição contínua não gera alertas repetidos. A aplicação deve chamar essa função periodicamente e consumir a fila `envio_email` para envio e reenvio via SMTP.

Protocolos guardam os bytes originais do PDF, autor, assinatura e validação. O autor assina; o Chefe valida um documento assinado. Apenas protocolos validados podem ser vinculados a equipamentos. A importação na aplicação deve validar formato e tamanho do arquivo.

## Operações disponíveis

| Função | Finalidade |
|---|---|
| `criar_reserva` / `cancelar_reserva` | Confirmar e encerrar uma reserva. |
| `alterar_local_equipamento` | Alterar sala ou bancada com validação das reservas. |
| `definir_estado_recurso` | Alterar disponibilidade e cancelar reservas afetadas. |
| `retirar_chave` / `devolver_chave` | Registrar entrega e recebimento físico de uma cópia. |
| `registrar_ocorrencia_chave` | Registrar condição física da cópia. |
| `proibir_aluno` | Aplicar restrição e cancelar reservas afetadas. |
| `solicitar_reativacao` / `responder_reativacao` | Solicitar e decidir a remoção de uma proibição. |
| `movimentar_estoque` | Atualizar saldo com rastreabilidade. |
| `assinar_protocolo` / `validar_protocolo` | Registrar assinatura e validação. |
| `avaliar_alertas_estoque` | Criar alertas de quantidade e validade. |

Manutenção, dano e desativação cancelam reservas vigentes ou futuras afetadas, incluindo as que estão em andamento. As chaves já retiradas continuam registradas em posse do usuário. Não há substituição automática de equipamento.

## Integração com o backend

O backend autentica o usuário, resolve seu perfil e laboratório e passa o ID do ator às operações. As consultas devem respeitar o laboratório e o histórico permitido para o perfil. RLS não está habilitado nesta versão.

`senha_hash` recebe o hash produzido pela aplicação. A tabela de sessões armazena o resumo do token, validade e revogação. Os usuários da carga fictícia não possuem senha de login conhecida.

Para cadastros feitos por INSERT ou UPDATE, informe o contexto na mesma transação:

```sql
BEGIN;
SELECT gestao_lab.contexto_operacao(1, 'Cadastro de recurso');
-- Inserções ou alterações autorizadas pelo backend.
COMMIT;
```

As funções operacionais já registram o contexto. `historico_uso` conserva ator, data, ação, motivo e valores anteriores/posteriores, excluindo credenciais e conteúdo binário dos snapshots. O histórico não admite alteração ou exclusão pelas operações comuns.

Credenciais de conexão e backups ficam no ambiente local. O repositório contém os scripts de estrutura, a carga fictícia e os testes.

## Testes

### PostgreSQL local

Use um banco separado, `gestao_laboratorio_teste`, com o schema instalado e a carga [03_dados_exemplo.sql](03_dados_exemplo.sql). Execute [05_testes_integridade.sql](05_testes_integridade.sql) no Query Tool desse banco. A suíte possui 113 verificações e desfaz suas alterações ao final; sequências podem avançar.

O teste de concorrência precisa de Python e duas conexões independentes:

```sh
python -m pip install "psycopg[binary]>=3.2,<4"
# Defina DATABASE_URL no ambiente para gestao_laboratorio_teste.
python database/06_testar_concorrencia.py
```

O teste verifica conflito no mesmo equipamento, retirada da mesma cópia e limite simultâneo do usuário em recursos distintos. Ao final, devolve as chaves, cancela as reservas criadas e restaura os limites. Os registros de histórico permanecem no banco de teste.

### Validação isolada

Com Node.js e npm, na raiz do repositório:

```sh
cd database
npm install
npm test
```

O runner usa PostgreSQL em memória via PGlite. [O relatório de validação](docs/ResultadosTestesLaboratorio.json) registra 113 verificações aprovadas em PostgreSQL 18.3/PGlite 0.5.8. Esse ambiente tem um backend único; o teste com duas conexões deve ser executado no servidor PostgreSQL.

## Documentação e alterações

- [Modelo relacional](docs/ModeloRelacionalLaboratorio.md)
- [Dicionário de dados](docs/DicionarioDadosLaboratorio.md)
- [Relatório de validação](docs/ResultadosTestesLaboratorio.json)
- [Convenção de migrações](migrations/README.md)

O script principal representa a instalação inicial. Registre alterações posteriores em `migrations/`, com uma versão nova em `schema_versao`.

Permanecem em definição a janela de retirada de chave, penalidades por atraso e a política definitiva de designação. A implementação atual permite retirada antes do início de uma reserva confirmada cujo fim ainda não ocorreu. A persistência do agente especialista será definida quando seu contrato funcional estiver validado.
