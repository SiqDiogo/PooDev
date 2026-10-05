# Dicionário de dados — Laboratório

Extraído do catálogo PostgreSQL após executar o SQL entregue. Esquema `gestao_lab`; revisão de 04/10/2026. As regras complementares estão em `02_regras.sql`.

## Tipos enumerados

| Tipo | Valores |
|---|---|
| `condicao_chave` | OPERACIONAL, EXTRAVIADA, INDISPONIVEL |
| `estado_envio` | PENDENTE, ENVIADO, FALHOU |
| `estado_protocolo` | NAO_VALIDADO, VALIDADO |
| `estado_recurso` | DISPONIVEL, MANUTENCAO, DANIFICADO, DESATIVADO |
| `estado_reserva` | CONFIRMADA, CANCELADA, CONCLUIDA |
| `estado_solicitacao` | PENDENTE, APROVADA, NEGADA |
| `tipo_aluno` | GRADUACAO, MESTRADO, DOUTORADO, POS |
| `tipo_recurso` | SALA, BANCADA, EQUIPAMENTO |

## aluno

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `usuario_id` | `bigint` | Sim | — |
| `laboratorio_id` | `bigint` | Sim | — |
| `matricula` | `text` | Sim | — |
| `tipo` | `tipo_aluno` | Sim | — |
| `orientador_usuario_id` | `bigint` | Sim | — |

Restrições declarativas:

- `aluno_matricula_check`: `CHECK ((btrim(matricula) <> ''::text))`
- `aluno_orientador_usuario_id_laboratorio_id_fkey`: `FOREIGN KEY (orientador_usuario_id, laboratorio_id) REFERENCES professor(usuario_id, laboratorio_id) DEFERRABLE INITIALLY DEFERRED`
- `aluno_usuario_id_laboratorio_id_fkey`: `FOREIGN KEY (usuario_id, laboratorio_id) REFERENCES usuario(id, laboratorio_id) DEFERRABLE INITIALLY DEFERRED`
- `aluno_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `aluno_matricula_not_null`: `NOT NULL matricula`
- `aluno_orientador_usuario_id_not_null`: `NOT NULL orientador_usuario_id`
- `aluno_tipo_not_null`: `NOT NULL tipo`
- `aluno_usuario_id_not_null`: `NOT NULL usuario_id`
- `aluno_pkey`: `PRIMARY KEY (usuario_id)`
- `aluno_subtipo`: `TRIGGER DEFERRABLE INITIALLY DEFERRED`
- `aluno_matricula_key`: `UNIQUE (matricula)`
- `aluno_usuario_id_laboratorio_id_key`: `UNIQUE (usuario_id, laboratorio_id)`

Índices:

- `aluno_matricula_key`: `CREATE UNIQUE INDEX aluno_matricula_key ON gestao_lab.aluno USING btree (matricula)`
- `aluno_orientador_idx`: `CREATE INDEX aluno_orientador_idx ON gestao_lab.aluno USING btree (orientador_usuario_id)`
- `aluno_pkey`: `CREATE UNIQUE INDEX aluno_pkey ON gestao_lab.aluno USING btree (usuario_id)`
- `aluno_usuario_id_laboratorio_id_key`: `CREATE UNIQUE INDEX aluno_usuario_id_laboratorio_id_key ON gestao_lab.aluno USING btree (usuario_id, laboratorio_id)`

## bancada

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `recurso_id` | `bigint` | Sim | — |
| `laboratorio_id` | `bigint` | Sim | — |
| `tipo` | `tipo_recurso` | Não | GERADA: 'BANCADA'::tipo_recurso |
| `sala_id` | `bigint` | Sim | — |
| `numero_identificacao` | `text` | Sim | — |

Restrições declarativas:

- `bancada_numero_identificacao_check`: `CHECK ((btrim(numero_identificacao) <> ''::text))`
- `bancada_recurso_id_laboratorio_id_fkey`: `FOREIGN KEY (recurso_id, laboratorio_id) REFERENCES recurso(id, laboratorio_id)`
- `bancada_recurso_id_tipo_fkey`: `FOREIGN KEY (recurso_id, tipo) REFERENCES recurso(id, tipo)`
- `bancada_sala_id_laboratorio_id_fkey`: `FOREIGN KEY (sala_id, laboratorio_id) REFERENCES sala(recurso_id, laboratorio_id)`
- `bancada_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `bancada_numero_identificacao_not_null`: `NOT NULL numero_identificacao`
- `bancada_recurso_id_not_null`: `NOT NULL recurso_id`
- `bancada_sala_id_not_null`: `NOT NULL sala_id`
- `bancada_pkey`: `PRIMARY KEY (recurso_id)`
- `bancada_subtipo`: `TRIGGER DEFERRABLE INITIALLY DEFERRED`
- `bancada_recurso_id_laboratorio_id_key`: `UNIQUE (recurso_id, laboratorio_id)`
- `bancada_sala_id_numero_identificacao_key`: `UNIQUE (sala_id, numero_identificacao)`

Índices:

- `bancada_identificacao_normalizada`: `CREATE UNIQUE INDEX bancada_identificacao_normalizada ON gestao_lab.bancada USING btree (sala_id, upper(btrim(numero_identificacao)))`
- `bancada_pkey`: `CREATE UNIQUE INDEX bancada_pkey ON gestao_lab.bancada USING btree (recurso_id)`
- `bancada_recurso_id_laboratorio_id_key`: `CREATE UNIQUE INDEX bancada_recurso_id_laboratorio_id_key ON gestao_lab.bancada USING btree (recurso_id, laboratorio_id)`
- `bancada_sala_id_numero_identificacao_key`: `CREATE UNIQUE INDEX bancada_sala_id_numero_identificacao_key ON gestao_lab.bancada USING btree (sala_id, numero_identificacao)`
- `bancada_sala_idx`: `CREATE INDEX bancada_sala_idx ON gestao_lab.bancada USING btree (sala_id)`

## chave

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `id` | `bigint` | Sim | IDENTITY (BY DEFAULT) |
| `laboratorio_id` | `bigint` | Sim | — |
| `codigo_copia` | `text` | Sim | — |
| `sala_id` | `bigint` | Não | — |
| `bancada_id` | `bigint` | Não | — |
| `condicao` | `condicao_chave` | Sim | 'OPERACIONAL'::condicao_chave |
| `designada_por` | `bigint` | Sim | — |
| `designada_para` | `bigint` | Não | — |
| `criado_em` | `timestamp with time zone` | Sim | clock_timestamp() |

Restrições declarativas:

- `chave_check`: `CHECK ((num_nonnulls(sala_id, bancada_id) = 1))`
- `chave_codigo_copia_check`: `CHECK ((btrim(codigo_copia) <> ''::text))`
- `chave_bancada_id_laboratorio_id_fkey`: `FOREIGN KEY (bancada_id, laboratorio_id) REFERENCES bancada(recurso_id, laboratorio_id)`
- `chave_designada_para_laboratorio_id_fkey`: `FOREIGN KEY (designada_para, laboratorio_id) REFERENCES usuario(id, laboratorio_id)`
- `chave_designada_por_laboratorio_id_fkey`: `FOREIGN KEY (designada_por, laboratorio_id) REFERENCES professor(usuario_id, laboratorio_id)`
- `chave_laboratorio_id_fkey`: `FOREIGN KEY (laboratorio_id) REFERENCES laboratorio(id)`
- `chave_sala_id_laboratorio_id_fkey`: `FOREIGN KEY (sala_id, laboratorio_id) REFERENCES sala(recurso_id, laboratorio_id)`
- `chave_codigo_copia_not_null`: `NOT NULL codigo_copia`
- `chave_condicao_not_null`: `NOT NULL condicao`
- `chave_criado_em_not_null`: `NOT NULL criado_em`
- `chave_designada_por_not_null`: `NOT NULL designada_por`
- `chave_id_not_null`: `NOT NULL id`
- `chave_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `chave_pkey`: `PRIMARY KEY (id)`
- `chave_codigo_copia_key`: `UNIQUE (codigo_copia)`
- `chave_id_laboratorio_id_key`: `UNIQUE (id, laboratorio_id)`

Índices:

- `chave_bancada_idx`: `CREATE INDEX chave_bancada_idx ON gestao_lab.chave USING btree (bancada_id)`
- `chave_codigo_copia_key`: `CREATE UNIQUE INDEX chave_codigo_copia_key ON gestao_lab.chave USING btree (codigo_copia)`
- `chave_codigo_normalizado`: `CREATE UNIQUE INDEX chave_codigo_normalizado ON gestao_lab.chave USING btree (upper(btrim(codigo_copia)))`
- `chave_id_laboratorio_id_key`: `CREATE UNIQUE INDEX chave_id_laboratorio_id_key ON gestao_lab.chave USING btree (id, laboratorio_id)`
- `chave_pkey`: `CREATE UNIQUE INDEX chave_pkey ON gestao_lab.chave USING btree (id)`
- `chave_sala_idx`: `CREATE INDEX chave_sala_idx ON gestao_lab.chave USING btree (sala_id)`

## chefe_laboratorio

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `usuario_id` | `bigint` | Sim | — |
| `laboratorio_id` | `bigint` | Sim | — |

Restrições declarativas:

- `chefe_laboratorio_usuario_id_laboratorio_id_fkey`: `FOREIGN KEY (usuario_id, laboratorio_id) REFERENCES professor(usuario_id, laboratorio_id) DEFERRABLE INITIALLY DEFERRED`
- `chefe_laboratorio_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `chefe_laboratorio_usuario_id_not_null`: `NOT NULL usuario_id`
- `chefe_laboratorio_pkey`: `PRIMARY KEY (usuario_id)`
- `chefe_laboratorio_laboratorio_id_key`: `UNIQUE (laboratorio_id)`
- `chefe_laboratorio_usuario_id_laboratorio_id_key`: `UNIQUE (usuario_id, laboratorio_id)`

Índices:

- `chefe_laboratorio_laboratorio_id_key`: `CREATE UNIQUE INDEX chefe_laboratorio_laboratorio_id_key ON gestao_lab.chefe_laboratorio USING btree (laboratorio_id)`
- `chefe_laboratorio_pkey`: `CREATE UNIQUE INDEX chefe_laboratorio_pkey ON gestao_lab.chefe_laboratorio USING btree (usuario_id)`
- `chefe_laboratorio_usuario_id_laboratorio_id_key`: `CREATE UNIQUE INDEX chefe_laboratorio_usuario_id_laboratorio_id_key ON gestao_lab.chefe_laboratorio USING btree (usuario_id, laboratorio_id)`

## emprestimo_chave

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `id` | `bigint` | Sim | IDENTITY (BY DEFAULT) |
| `laboratorio_id` | `bigint` | Sim | — |
| `chave_id` | `bigint` | Sim | — |
| `usuario_id` | `bigint` | Sim | — |
| `reserva_id` | `bigint` | Sim | — |
| `retirada_em` | `timestamp with time zone` | Sim | clock_timestamp() |
| `entregue_por` | `bigint` | Sim | — |
| `devolucao_em` | `timestamp with time zone` | Não | — |
| `recebido_por` | `bigint` | Não | — |

Restrições declarativas:

- `emprestimo_chave_check`: `CHECK (((devolucao_em IS NULL) = (recebido_por IS NULL)))`
- `emprestimo_chave_check1`: `CHECK (((devolucao_em IS NULL) OR (devolucao_em >= retirada_em)))`
- `emprestimo_chave_chave_id_laboratorio_id_fkey`: `FOREIGN KEY (chave_id, laboratorio_id) REFERENCES chave(id, laboratorio_id)`
- `emprestimo_chave_entregue_por_laboratorio_id_fkey`: `FOREIGN KEY (entregue_por, laboratorio_id) REFERENCES professor(usuario_id, laboratorio_id)`
- `emprestimo_chave_laboratorio_id_fkey`: `FOREIGN KEY (laboratorio_id) REFERENCES laboratorio(id)`
- `emprestimo_chave_recebido_por_laboratorio_id_fkey`: `FOREIGN KEY (recebido_por, laboratorio_id) REFERENCES professor(usuario_id, laboratorio_id)`
- `emprestimo_chave_reserva_id_laboratorio_id_fkey`: `FOREIGN KEY (reserva_id, laboratorio_id) REFERENCES reserva(id, laboratorio_id)`
- `emprestimo_chave_usuario_id_laboratorio_id_fkey`: `FOREIGN KEY (usuario_id, laboratorio_id) REFERENCES usuario(id, laboratorio_id)`
- `emprestimo_chave_chave_id_not_null`: `NOT NULL chave_id`
- `emprestimo_chave_entregue_por_not_null`: `NOT NULL entregue_por`
- `emprestimo_chave_id_not_null`: `NOT NULL id`
- `emprestimo_chave_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `emprestimo_chave_reserva_id_not_null`: `NOT NULL reserva_id`
- `emprestimo_chave_retirada_em_not_null`: `NOT NULL retirada_em`
- `emprestimo_chave_usuario_id_not_null`: `NOT NULL usuario_id`
- `emprestimo_chave_pkey`: `PRIMARY KEY (id)`
- `emprestimo_chave_id_laboratorio_id_key`: `UNIQUE (id, laboratorio_id)`

Índices:

- `emprestimo_chave_id_laboratorio_id_key`: `CREATE UNIQUE INDEX emprestimo_chave_id_laboratorio_id_key ON gestao_lab.emprestimo_chave USING btree (id, laboratorio_id)`
- `emprestimo_chave_pkey`: `CREATE UNIQUE INDEX emprestimo_chave_pkey ON gestao_lab.emprestimo_chave USING btree (id)`
- `emprestimo_chave_uma_posse_aberta`: `CREATE UNIQUE INDEX emprestimo_chave_uma_posse_aberta ON gestao_lab.emprestimo_chave USING btree (chave_id) WHERE (devolucao_em IS NULL)`
- `emprestimo_reserva_idx`: `CREATE INDEX emprestimo_reserva_idx ON gestao_lab.emprestimo_chave USING btree (reserva_id)`
- `emprestimo_usuario_idx`: `CREATE INDEX emprestimo_usuario_idx ON gestao_lab.emprestimo_chave USING btree (usuario_id)`

## envio_email

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `id` | `bigint` | Sim | IDENTITY (BY DEFAULT) |
| `notificacao_id` | `bigint` | Sim | — |
| `estado` | `estado_envio` | Sim | 'PENDENTE'::estado_envio |
| `tentativas` | `integer` | Sim | 0 |
| `proxima_tentativa_em` | `timestamp with time zone` | Sim | clock_timestamp() |
| `enviado_em` | `timestamp with time zone` | Não | — |
| `ultimo_erro` | `text` | Não | — |

Restrições declarativas:

- `envio_email_check`: `CHECK (((estado = 'ENVIADO'::estado_envio) = (enviado_em IS NOT NULL)))`
- `envio_email_tentativas_check`: `CHECK ((tentativas >= 0))`
- `envio_email_notificacao_id_fkey`: `FOREIGN KEY (notificacao_id) REFERENCES notificacao(id)`
- `envio_email_estado_not_null`: `NOT NULL estado`
- `envio_email_id_not_null`: `NOT NULL id`
- `envio_email_notificacao_id_not_null`: `NOT NULL notificacao_id`
- `envio_email_proxima_tentativa_em_not_null`: `NOT NULL proxima_tentativa_em`
- `envio_email_tentativas_not_null`: `NOT NULL tentativas`
- `envio_email_pkey`: `PRIMARY KEY (id)`
- `envio_email_notificacao_id_key`: `UNIQUE (notificacao_id)`

Índices:

- `envio_email_notificacao_id_key`: `CREATE UNIQUE INDEX envio_email_notificacao_id_key ON gestao_lab.envio_email USING btree (notificacao_id)`
- `envio_email_pendente_idx`: `CREATE INDEX envio_email_pendente_idx ON gestao_lab.envio_email USING btree (proxima_tentativa_em) WHERE (estado <> 'ENVIADO'::estado_envio)`
- `envio_email_pkey`: `CREATE UNIQUE INDEX envio_email_pkey ON gestao_lab.envio_email USING btree (id)`

## equipamento

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `recurso_id` | `bigint` | Sim | — |
| `laboratorio_id` | `bigint` | Sim | — |
| `tipo` | `tipo_recurso` | Não | GERADA: 'EQUIPAMENTO'::tipo_recurso |
| `numero_patrimonio` | `text` | Sim | — |
| `bancada_id` | `bigint` | Não | — |
| `sala_direta_id` | `bigint` | Não | — |
| `complemento_local` | `text` | Sim | — |
| `foto_uri` | `text` | Não | — |

Restrições declarativas:

- `equipamento_check`: `CHECK ((num_nonnulls(bancada_id, sala_direta_id) = 1))`
- `equipamento_complemento_local_check`: `CHECK ((btrim(complemento_local) <> ''::text))`
- `equipamento_numero_patrimonio_check`: `CHECK ((btrim(numero_patrimonio) <> ''::text))`
- `equipamento_bancada_id_laboratorio_id_fkey`: `FOREIGN KEY (bancada_id, laboratorio_id) REFERENCES bancada(recurso_id, laboratorio_id)`
- `equipamento_recurso_id_laboratorio_id_fkey`: `FOREIGN KEY (recurso_id, laboratorio_id) REFERENCES recurso(id, laboratorio_id)`
- `equipamento_recurso_id_tipo_fkey`: `FOREIGN KEY (recurso_id, tipo) REFERENCES recurso(id, tipo)`
- `equipamento_sala_direta_id_laboratorio_id_fkey`: `FOREIGN KEY (sala_direta_id, laboratorio_id) REFERENCES sala(recurso_id, laboratorio_id)`
- `equipamento_complemento_local_not_null`: `NOT NULL complemento_local`
- `equipamento_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `equipamento_numero_patrimonio_not_null`: `NOT NULL numero_patrimonio`
- `equipamento_recurso_id_not_null`: `NOT NULL recurso_id`
- `equipamento_pkey`: `PRIMARY KEY (recurso_id)`
- `equipamento_subtipo`: `TRIGGER DEFERRABLE INITIALLY DEFERRED`
- `equipamento_numero_patrimonio_key`: `UNIQUE (numero_patrimonio)`
- `equipamento_recurso_id_laboratorio_id_key`: `UNIQUE (recurso_id, laboratorio_id)`

Índices:

- `equipamento_bancada_idx`: `CREATE INDEX equipamento_bancada_idx ON gestao_lab.equipamento USING btree (bancada_id)`
- `equipamento_numero_patrimonio_key`: `CREATE UNIQUE INDEX equipamento_numero_patrimonio_key ON gestao_lab.equipamento USING btree (numero_patrimonio)`
- `equipamento_patrimonio_normalizado`: `CREATE UNIQUE INDEX equipamento_patrimonio_normalizado ON gestao_lab.equipamento USING btree (upper(btrim(numero_patrimonio)))`
- `equipamento_pkey`: `CREATE UNIQUE INDEX equipamento_pkey ON gestao_lab.equipamento USING btree (recurso_id)`
- `equipamento_recurso_id_laboratorio_id_key`: `CREATE UNIQUE INDEX equipamento_recurso_id_laboratorio_id_key ON gestao_lab.equipamento USING btree (recurso_id, laboratorio_id)`
- `equipamento_sala_idx`: `CREATE INDEX equipamento_sala_idx ON gestao_lab.equipamento USING btree (sala_direta_id)`

## historico_uso

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `id` | `bigint` | Sim | IDENTITY (BY DEFAULT) |
| `laboratorio_id` | `bigint` | Sim | — |
| `ator_id` | `bigint` | Não | — |
| `tabela` | `text` | Sim | — |
| `registro_id` | `text` | Sim | — |
| `acao` | `text` | Sim | — |
| `motivo` | `text` | Não | — |
| `antes` | `jsonb` | Não | — |
| `depois` | `jsonb` | Não | — |
| `registrado_em` | `timestamp with time zone` | Sim | clock_timestamp() |
| `transacao_id` | `bigint` | Sim | txid_current() |

Restrições declarativas:

- `historico_uso_acao_check`: `CHECK ((acao = ANY (ARRAY['INSERT'::text, 'UPDATE'::text, 'DELETE'::text])))`
- `historico_uso_ator_id_laboratorio_id_fkey`: `FOREIGN KEY (ator_id, laboratorio_id) REFERENCES usuario(id, laboratorio_id)`
- `historico_uso_laboratorio_id_fkey`: `FOREIGN KEY (laboratorio_id) REFERENCES laboratorio(id)`
- `historico_uso_acao_not_null`: `NOT NULL acao`
- `historico_uso_id_not_null`: `NOT NULL id`
- `historico_uso_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `historico_uso_registrado_em_not_null`: `NOT NULL registrado_em`
- `historico_uso_registro_id_not_null`: `NOT NULL registro_id`
- `historico_uso_tabela_not_null`: `NOT NULL tabela`
- `historico_uso_transacao_id_not_null`: `NOT NULL transacao_id`
- `historico_uso_pkey`: `PRIMARY KEY (id)`

Índices:

- `historico_ator_data_idx`: `CREATE INDEX historico_ator_data_idx ON gestao_lab.historico_uso USING btree (ator_id, registrado_em DESC)`
- `historico_laboratorio_data_idx`: `CREATE INDEX historico_laboratorio_data_idx ON gestao_lab.historico_uso USING btree (laboratorio_id, registrado_em DESC)`
- `historico_uso_pkey`: `CREATE UNIQUE INDEX historico_uso_pkey ON gestao_lab.historico_uso USING btree (id)`

## item_estoque

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `id` | `bigint` | Sim | IDENTITY (BY DEFAULT) |
| `laboratorio_id` | `bigint` | Sim | — |
| `nome` | `text` | Sim | — |
| `lote` | `text` | Sim | 'SEM_LOTE'::text |
| `unidade` | `text` | Sim | — |
| `quantidade` | `numeric(14,4)` | Sim | 0 |
| `limite_estoque_baixo` | `numeric(14,4)` | Sim | 0 |
| `validade` | `date` | Não | — |
| `ativo` | `boolean` | Sim | true |

Restrições declarativas:

- `item_estoque_limite_estoque_baixo_check`: `CHECK (((limite_estoque_baixo >= (0)::numeric) AND (limite_estoque_baixo <> 'NaN'::numeric)))`
- `item_estoque_lote_check`: `CHECK ((btrim(lote) <> ''::text))`
- `item_estoque_nome_check`: `CHECK ((btrim(nome) <> ''::text))`
- `item_estoque_quantidade_check`: `CHECK (((quantidade >= (0)::numeric) AND (quantidade <> 'NaN'::numeric)))`
- `item_estoque_unidade_check`: `CHECK ((btrim(unidade) <> ''::text))`
- `item_estoque_laboratorio_id_fkey`: `FOREIGN KEY (laboratorio_id) REFERENCES laboratorio(id)`
- `item_estoque_ativo_not_null`: `NOT NULL ativo`
- `item_estoque_id_not_null`: `NOT NULL id`
- `item_estoque_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `item_estoque_limite_estoque_baixo_not_null`: `NOT NULL limite_estoque_baixo`
- `item_estoque_lote_not_null`: `NOT NULL lote`
- `item_estoque_nome_not_null`: `NOT NULL nome`
- `item_estoque_quantidade_not_null`: `NOT NULL quantidade`
- `item_estoque_unidade_not_null`: `NOT NULL unidade`
- `item_estoque_pkey`: `PRIMARY KEY (id)`
- `item_estoque_id_laboratorio_id_key`: `UNIQUE (id, laboratorio_id)`
- `item_estoque_laboratorio_id_nome_lote_key`: `UNIQUE (laboratorio_id, nome, lote)`

Índices:

- `item_estoque_id_laboratorio_id_key`: `CREATE UNIQUE INDEX item_estoque_id_laboratorio_id_key ON gestao_lab.item_estoque USING btree (id, laboratorio_id)`
- `item_estoque_lab_idx`: `CREATE INDEX item_estoque_lab_idx ON gestao_lab.item_estoque USING btree (laboratorio_id)`
- `item_estoque_laboratorio_id_nome_lote_key`: `CREATE UNIQUE INDEX item_estoque_laboratorio_id_nome_lote_key ON gestao_lab.item_estoque USING btree (laboratorio_id, nome, lote)`
- `item_estoque_pkey`: `CREATE UNIQUE INDEX item_estoque_pkey ON gestao_lab.item_estoque USING btree (id)`

## laboratorio

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `id` | `bigint` | Sim | IDENTITY (BY DEFAULT) |
| `nome` | `text` | Sim | — |
| `localizacao` | `text` | Sim | — |
| `chefe_usuario_id` | `bigint` | Sim | — |
| `duracao_maxima_reserva` | `interval` | Não | — |
| `max_reservas_simultaneas` | `integer` | Não | — |
| `dias_alerta_validade` | `integer` | Sim | 30 |
| `ativo` | `boolean` | Sim | true |
| `criado_em` | `timestamp with time zone` | Sim | clock_timestamp() |

Restrições declarativas:

- `laboratorio_dias_alerta_validade_check`: `CHECK ((dias_alerta_validade >= 0))`
- `laboratorio_duracao_maxima_reserva_check`: `CHECK (((duracao_maxima_reserva > '00:00:00'::interval) AND isfinite(duracao_maxima_reserva)))`
- `laboratorio_localizacao_check`: `CHECK ((btrim(localizacao) <> ''::text))`
- `laboratorio_max_reservas_simultaneas_check`: `CHECK ((max_reservas_simultaneas > 0))`
- `laboratorio_nome_check`: `CHECK ((btrim(nome) <> ''::text))`
- `laboratorio_chefe_fk`: `FOREIGN KEY (chefe_usuario_id, id) REFERENCES chefe_laboratorio(usuario_id, laboratorio_id) DEFERRABLE INITIALLY DEFERRED`
- `laboratorio_ativo_not_null`: `NOT NULL ativo`
- `laboratorio_chefe_usuario_id_not_null`: `NOT NULL chefe_usuario_id`
- `laboratorio_criado_em_not_null`: `NOT NULL criado_em`
- `laboratorio_dias_alerta_validade_not_null`: `NOT NULL dias_alerta_validade`
- `laboratorio_id_not_null`: `NOT NULL id`
- `laboratorio_localizacao_not_null`: `NOT NULL localizacao`
- `laboratorio_nome_not_null`: `NOT NULL nome`
- `laboratorio_pkey`: `PRIMARY KEY (id)`

Índices:

- `laboratorio_pkey`: `CREATE UNIQUE INDEX laboratorio_pkey ON gestao_lab.laboratorio USING btree (id)`

## movimentacao_estoque

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `id` | `bigint` | Sim | IDENTITY (BY DEFAULT) |
| `laboratorio_id` | `bigint` | Sim | — |
| `item_id` | `bigint` | Sim | — |
| `registrado_por` | `bigint` | Sim | — |
| `variacao` | `numeric(14,4)` | Sim | — |
| `quantidade_anterior` | `numeric(14,4)` | Sim | — |
| `quantidade_posterior` | `numeric(14,4)` | Sim | — |
| `motivo` | `text` | Sim | — |
| `criado_em` | `timestamp with time zone` | Sim | clock_timestamp() |

Restrições declarativas:

- `movimentacao_estoque_check`: `CHECK ((quantidade_posterior = (quantidade_anterior + variacao)))`
- `movimentacao_estoque_motivo_check`: `CHECK ((btrim(motivo) <> ''::text))`
- `movimentacao_estoque_quantidade_anterior_check`: `CHECK (((quantidade_anterior >= (0)::numeric) AND (quantidade_anterior <> 'NaN'::numeric)))`
- `movimentacao_estoque_quantidade_posterior_check`: `CHECK (((quantidade_posterior >= (0)::numeric) AND (quantidade_posterior <> 'NaN'::numeric)))`
- `movimentacao_estoque_variacao_check`: `CHECK (((variacao <> (0)::numeric) AND (variacao <> 'NaN'::numeric)))`
- `movimentacao_estoque_item_id_laboratorio_id_fkey`: `FOREIGN KEY (item_id, laboratorio_id) REFERENCES item_estoque(id, laboratorio_id)`
- `movimentacao_estoque_laboratorio_id_fkey`: `FOREIGN KEY (laboratorio_id) REFERENCES laboratorio(id)`
- `movimentacao_estoque_registrado_por_laboratorio_id_fkey`: `FOREIGN KEY (registrado_por, laboratorio_id) REFERENCES usuario(id, laboratorio_id)`
- `movimentacao_estoque_criado_em_not_null`: `NOT NULL criado_em`
- `movimentacao_estoque_id_not_null`: `NOT NULL id`
- `movimentacao_estoque_item_id_not_null`: `NOT NULL item_id`
- `movimentacao_estoque_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `movimentacao_estoque_motivo_not_null`: `NOT NULL motivo`
- `movimentacao_estoque_quantidade_anterior_not_null`: `NOT NULL quantidade_anterior`
- `movimentacao_estoque_quantidade_posterior_not_null`: `NOT NULL quantidade_posterior`
- `movimentacao_estoque_registrado_por_not_null`: `NOT NULL registrado_por`
- `movimentacao_estoque_variacao_not_null`: `NOT NULL variacao`
- `movimentacao_estoque_pkey`: `PRIMARY KEY (id)`

Índices:

- `movimentacao_estoque_pkey`: `CREATE UNIQUE INDEX movimentacao_estoque_pkey ON gestao_lab.movimentacao_estoque USING btree (id)`
- `movimentacao_item_idx`: `CREATE INDEX movimentacao_item_idx ON gestao_lab.movimentacao_estoque USING btree (item_id, criado_em)`

## notificacao

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `id` | `bigint` | Sim | IDENTITY (BY DEFAULT) |
| `laboratorio_id` | `bigint` | Sim | — |
| `destinatario_id` | `bigint` | Sim | — |
| `tipo` | `text` | Sim | — |
| `mensagem` | `text` | Sim | — |
| `referencia` | `jsonb` | Sim | '{}'::jsonb |
| `chave_deduplicacao` | `text` | Não | — |
| `criado_em` | `timestamp with time zone` | Sim | clock_timestamp() |
| `lida_em` | `timestamp with time zone` | Não | — |

Restrições declarativas:

- `notificacao_mensagem_check`: `CHECK ((btrim(mensagem) <> ''::text))`
- `notificacao_tipo_check`: `CHECK ((btrim(tipo) <> ''::text))`
- `notificacao_destinatario_id_laboratorio_id_fkey`: `FOREIGN KEY (destinatario_id, laboratorio_id) REFERENCES usuario(id, laboratorio_id)`
- `notificacao_laboratorio_id_fkey`: `FOREIGN KEY (laboratorio_id) REFERENCES laboratorio(id)`
- `notificacao_criado_em_not_null`: `NOT NULL criado_em`
- `notificacao_destinatario_id_not_null`: `NOT NULL destinatario_id`
- `notificacao_id_not_null`: `NOT NULL id`
- `notificacao_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `notificacao_mensagem_not_null`: `NOT NULL mensagem`
- `notificacao_referencia_not_null`: `NOT NULL referencia`
- `notificacao_tipo_not_null`: `NOT NULL tipo`
- `notificacao_pkey`: `PRIMARY KEY (id)`

Índices:

- `notificacao_deduplicada`: `CREATE UNIQUE INDEX notificacao_deduplicada ON gestao_lab.notificacao USING btree (destinatario_id, chave_deduplicacao) WHERE (chave_deduplicacao IS NOT NULL)`
- `notificacao_destinatario_idx`: `CREATE INDEX notificacao_destinatario_idx ON gestao_lab.notificacao USING btree (destinatario_id, criado_em DESC)`
- `notificacao_pkey`: `CREATE UNIQUE INDEX notificacao_pkey ON gestao_lab.notificacao USING btree (id)`

## ocorrencia

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `id` | `bigint` | Sim | IDENTITY (BY DEFAULT) |
| `laboratorio_id` | `bigint` | Sim | — |
| `autor_id` | `bigint` | Sim | — |
| `recurso_id` | `bigint` | Não | — |
| `item_estoque_id` | `bigint` | Não | — |
| `tipo` | `text` | Sim | — |
| `descricao` | `text` | Sim | — |
| `resolvida_em` | `timestamp with time zone` | Não | — |
| `criado_em` | `timestamp with time zone` | Sim | clock_timestamp() |

Restrições declarativas:

- `ocorrencia_check`: `CHECK ((num_nonnulls(recurso_id, item_estoque_id) <= 1))`
- `ocorrencia_descricao_check`: `CHECK ((btrim(descricao) <> ''::text))`
- `ocorrencia_tipo_check`: `CHECK ((tipo = ANY (ARRAY['DANO'::text, 'FALTA_ESTOQUE'::text, 'OUTRO'::text])))`
- `ocorrencia_autor_id_laboratorio_id_fkey`: `FOREIGN KEY (autor_id, laboratorio_id) REFERENCES usuario(id, laboratorio_id)`
- `ocorrencia_item_estoque_id_laboratorio_id_fkey`: `FOREIGN KEY (item_estoque_id, laboratorio_id) REFERENCES item_estoque(id, laboratorio_id)`
- `ocorrencia_laboratorio_id_fkey`: `FOREIGN KEY (laboratorio_id) REFERENCES laboratorio(id)`
- `ocorrencia_recurso_id_laboratorio_id_fkey`: `FOREIGN KEY (recurso_id, laboratorio_id) REFERENCES recurso(id, laboratorio_id)`
- `ocorrencia_autor_id_not_null`: `NOT NULL autor_id`
- `ocorrencia_criado_em_not_null`: `NOT NULL criado_em`
- `ocorrencia_descricao_not_null`: `NOT NULL descricao`
- `ocorrencia_id_not_null`: `NOT NULL id`
- `ocorrencia_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `ocorrencia_tipo_not_null`: `NOT NULL tipo`
- `ocorrencia_pkey`: `PRIMARY KEY (id)`

Índices:

- `ocorrencia_pkey`: `CREATE UNIQUE INDEX ocorrencia_pkey ON gestao_lab.ocorrencia USING btree (id)`

## ocorrencia_chave

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `id` | `bigint` | Sim | IDENTITY (BY DEFAULT) |
| `laboratorio_id` | `bigint` | Sim | — |
| `chave_id` | `bigint` | Sim | — |
| `registrado_por` | `bigint` | Sim | — |
| `condicao` | `condicao_chave` | Sim | — |
| `descricao` | `text` | Sim | — |
| `criado_em` | `timestamp with time zone` | Sim | clock_timestamp() |

Restrições declarativas:

- `ocorrencia_chave_descricao_check`: `CHECK ((btrim(descricao) <> ''::text))`
- `ocorrencia_chave_chave_id_laboratorio_id_fkey`: `FOREIGN KEY (chave_id, laboratorio_id) REFERENCES chave(id, laboratorio_id)`
- `ocorrencia_chave_laboratorio_id_fkey`: `FOREIGN KEY (laboratorio_id) REFERENCES laboratorio(id)`
- `ocorrencia_chave_registrado_por_laboratorio_id_fkey`: `FOREIGN KEY (registrado_por, laboratorio_id) REFERENCES usuario(id, laboratorio_id)`
- `ocorrencia_chave_chave_id_not_null`: `NOT NULL chave_id`
- `ocorrencia_chave_condicao_not_null`: `NOT NULL condicao`
- `ocorrencia_chave_criado_em_not_null`: `NOT NULL criado_em`
- `ocorrencia_chave_descricao_not_null`: `NOT NULL descricao`
- `ocorrencia_chave_id_not_null`: `NOT NULL id`
- `ocorrencia_chave_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `ocorrencia_chave_registrado_por_not_null`: `NOT NULL registrado_por`
- `ocorrencia_chave_pkey`: `PRIMARY KEY (id)`

Índices:

- `ocorrencia_chave_pkey`: `CREATE UNIQUE INDEX ocorrencia_chave_pkey ON gestao_lab.ocorrencia_chave USING btree (id)`

## professor

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `usuario_id` | `bigint` | Sim | — |
| `laboratorio_id` | `bigint` | Sim | — |
| `programa_pos` | `text` | Sim | — |
| `ramal` | `text` | Não | — |

Restrições declarativas:

- `professor_programa_pos_check`: `CHECK ((btrim(programa_pos) <> ''::text))`
- `professor_usuario_id_laboratorio_id_fkey`: `FOREIGN KEY (usuario_id, laboratorio_id) REFERENCES usuario(id, laboratorio_id) DEFERRABLE INITIALLY DEFERRED`
- `professor_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `professor_programa_pos_not_null`: `NOT NULL programa_pos`
- `professor_usuario_id_not_null`: `NOT NULL usuario_id`
- `professor_pkey`: `PRIMARY KEY (usuario_id)`
- `professor_subtipo`: `TRIGGER DEFERRABLE INITIALLY DEFERRED`
- `professor_usuario_id_laboratorio_id_key`: `UNIQUE (usuario_id, laboratorio_id)`

Índices:

- `professor_pkey`: `CREATE UNIQUE INDEX professor_pkey ON gestao_lab.professor USING btree (usuario_id)`
- `professor_usuario_id_laboratorio_id_key`: `CREATE UNIQUE INDEX professor_usuario_id_laboratorio_id_key ON gestao_lab.professor USING btree (usuario_id, laboratorio_id)`

## proibicao_aluno_equipamento

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `id` | `bigint` | Sim | IDENTITY (BY DEFAULT) |
| `laboratorio_id` | `bigint` | Sim | — |
| `aluno_id` | `bigint` | Sim | — |
| `equipamento_id` | `bigint` | Sim | — |
| `motivo` | `text` | Sim | — |
| `aplicada_por` | `bigint` | Sim | — |
| `criada_em` | `timestamp with time zone` | Sim | clock_timestamp() |
| `encerrada_em` | `timestamp with time zone` | Não | — |
| `encerrada_por` | `bigint` | Não | — |

Restrições declarativas:

- `proibicao_aluno_equipamento_check`: `CHECK (((encerrada_em IS NULL) = (encerrada_por IS NULL)))`
- `proibicao_aluno_equipamento_check1`: `CHECK (((encerrada_em IS NULL) OR (encerrada_em >= criada_em)))`
- `proibicao_aluno_equipamento_motivo_check`: `CHECK ((btrim(motivo) <> ''::text))`
- `proibicao_aluno_equipamento_aluno_id_laboratorio_id_fkey`: `FOREIGN KEY (aluno_id, laboratorio_id) REFERENCES aluno(usuario_id, laboratorio_id)`
- `proibicao_aluno_equipamento_aplicada_por_laboratorio_id_fkey`: `FOREIGN KEY (aplicada_por, laboratorio_id) REFERENCES chefe_laboratorio(usuario_id, laboratorio_id)`
- `proibicao_aluno_equipamento_encerrada_por_laboratorio_id_fkey`: `FOREIGN KEY (encerrada_por, laboratorio_id) REFERENCES chefe_laboratorio(usuario_id, laboratorio_id)`
- `proibicao_aluno_equipamento_equipamento_id_laboratorio_id_fkey`: `FOREIGN KEY (equipamento_id, laboratorio_id) REFERENCES equipamento(recurso_id, laboratorio_id)`
- `proibicao_aluno_equipamento_laboratorio_id_fkey`: `FOREIGN KEY (laboratorio_id) REFERENCES laboratorio(id)`
- `proibicao_aluno_equipamento_aluno_id_not_null`: `NOT NULL aluno_id`
- `proibicao_aluno_equipamento_aplicada_por_not_null`: `NOT NULL aplicada_por`
- `proibicao_aluno_equipamento_criada_em_not_null`: `NOT NULL criada_em`
- `proibicao_aluno_equipamento_equipamento_id_not_null`: `NOT NULL equipamento_id`
- `proibicao_aluno_equipamento_id_not_null`: `NOT NULL id`
- `proibicao_aluno_equipamento_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `proibicao_aluno_equipamento_motivo_not_null`: `NOT NULL motivo`
- `proibicao_aluno_equipamento_pkey`: `PRIMARY KEY (id)`
- `proibicao_aluno_equipamento_id_laboratorio_id_key`: `UNIQUE (id, laboratorio_id)`

Índices:

- `proibicao_aluno_equipamento_id_laboratorio_id_key`: `CREATE UNIQUE INDEX proibicao_aluno_equipamento_id_laboratorio_id_key ON gestao_lab.proibicao_aluno_equipamento USING btree (id, laboratorio_id)`
- `proibicao_aluno_equipamento_pkey`: `CREATE UNIQUE INDEX proibicao_aluno_equipamento_pkey ON gestao_lab.proibicao_aluno_equipamento USING btree (id)`
- `proibicao_ativa_unica`: `CREATE UNIQUE INDEX proibicao_ativa_unica ON gestao_lab.proibicao_aluno_equipamento USING btree (aluno_id, equipamento_id) WHERE (encerrada_em IS NULL)`
- `proibicao_equipamento_idx`: `CREATE INDEX proibicao_equipamento_idx ON gestao_lab.proibicao_aluno_equipamento USING btree (equipamento_id) WHERE (encerrada_em IS NULL)`

## protocolo

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `id` | `bigint` | Sim | IDENTITY (BY DEFAULT) |
| `laboratorio_id` | `bigint` | Sim | — |
| `titulo` | `text` | Sim | — |
| `autor_id` | `bigint` | Sim | — |
| `pdf_original` | `bytea` | Sim | — |
| `nome_arquivo` | `text` | Sim | — |
| `estado` | `estado_protocolo` | Sim | 'NAO_VALIDADO'::estado_protocolo |
| `assinado_em` | `timestamp with time zone` | Não | — |
| `assinado_por` | `bigint` | Não | — |
| `validado_em` | `timestamp with time zone` | Não | — |
| `validado_por` | `bigint` | Não | — |
| `criado_em` | `timestamp with time zone` | Sim | clock_timestamp() |

Restrições declarativas:

- `protocolo_check`: `CHECK (((assinado_em IS NULL) = (assinado_por IS NULL)))`
- `protocolo_check1`: `CHECK (((assinado_por IS NULL) OR (assinado_por = autor_id)))`
- `protocolo_check2`: `CHECK (((assinado_em IS NULL) OR (assinado_em >= criado_em)))`
- `protocolo_check3`: `CHECK ((((estado = 'VALIDADO'::estado_protocolo) AND (validado_em IS NOT NULL) AND (validado_por IS NOT NULL)) OR ((estado = 'NAO_VALIDADO'::estado_protocolo) AND (validado_em IS NULL) AND (validado_por IS NULL))))`
- `protocolo_check4`: `CHECK (((validado_em IS NULL) OR ((assinado_em IS NOT NULL) AND (validado_em >= assinado_em))))`
- `protocolo_nome_arquivo_check`: `CHECK ((lower(nome_arquivo) ~~ '%.pdf'::text))`
- `protocolo_pdf_original_check`: `CHECK (((octet_length(pdf_original) > 5) AND (SUBSTRING(pdf_original FROM 1 FOR 5) = decode('255044462d'::text, 'hex'::text))))`
- `protocolo_titulo_check`: `CHECK ((btrim(titulo) <> ''::text))`
- `protocolo_assinado_por_laboratorio_id_fkey`: `FOREIGN KEY (assinado_por, laboratorio_id) REFERENCES usuario(id, laboratorio_id)`
- `protocolo_autor_id_laboratorio_id_fkey`: `FOREIGN KEY (autor_id, laboratorio_id) REFERENCES usuario(id, laboratorio_id)`
- `protocolo_laboratorio_id_fkey`: `FOREIGN KEY (laboratorio_id) REFERENCES laboratorio(id)`
- `protocolo_validado_por_laboratorio_id_fkey`: `FOREIGN KEY (validado_por, laboratorio_id) REFERENCES chefe_laboratorio(usuario_id, laboratorio_id)`
- `protocolo_autor_id_not_null`: `NOT NULL autor_id`
- `protocolo_criado_em_not_null`: `NOT NULL criado_em`
- `protocolo_estado_not_null`: `NOT NULL estado`
- `protocolo_id_not_null`: `NOT NULL id`
- `protocolo_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `protocolo_nome_arquivo_not_null`: `NOT NULL nome_arquivo`
- `protocolo_pdf_original_not_null`: `NOT NULL pdf_original`
- `protocolo_titulo_not_null`: `NOT NULL titulo`
- `protocolo_pkey`: `PRIMARY KEY (id)`
- `protocolo_id_laboratorio_id_key`: `UNIQUE (id, laboratorio_id)`

Índices:

- `protocolo_autor_idx`: `CREATE INDEX protocolo_autor_idx ON gestao_lab.protocolo USING btree (autor_id)`
- `protocolo_id_laboratorio_id_key`: `CREATE UNIQUE INDEX protocolo_id_laboratorio_id_key ON gestao_lab.protocolo USING btree (id, laboratorio_id)`
- `protocolo_pkey`: `CREATE UNIQUE INDEX protocolo_pkey ON gestao_lab.protocolo USING btree (id)`

## protocolo_equipamento

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `protocolo_id` | `bigint` | Sim | — |
| `equipamento_id` | `bigint` | Sim | — |
| `laboratorio_id` | `bigint` | Sim | — |
| `vinculado_por` | `bigint` | Sim | — |
| `criado_em` | `timestamp with time zone` | Sim | clock_timestamp() |

Restrições declarativas:

- `protocolo_equipamento_equipamento_id_laboratorio_id_fkey`: `FOREIGN KEY (equipamento_id, laboratorio_id) REFERENCES equipamento(recurso_id, laboratorio_id)`
- `protocolo_equipamento_protocolo_id_laboratorio_id_fkey`: `FOREIGN KEY (protocolo_id, laboratorio_id) REFERENCES protocolo(id, laboratorio_id)`
- `protocolo_equipamento_vinculado_por_laboratorio_id_fkey`: `FOREIGN KEY (vinculado_por, laboratorio_id) REFERENCES chefe_laboratorio(usuario_id, laboratorio_id)`
- `protocolo_equipamento_criado_em_not_null`: `NOT NULL criado_em`
- `protocolo_equipamento_equipamento_id_not_null`: `NOT NULL equipamento_id`
- `protocolo_equipamento_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `protocolo_equipamento_protocolo_id_not_null`: `NOT NULL protocolo_id`
- `protocolo_equipamento_vinculado_por_not_null`: `NOT NULL vinculado_por`
- `protocolo_equipamento_pkey`: `PRIMARY KEY (protocolo_id, equipamento_id)`

Índices:

- `protocolo_equipamento_equip_idx`: `CREATE INDEX protocolo_equipamento_equip_idx ON gestao_lab.protocolo_equipamento USING btree (equipamento_id)`
- `protocolo_equipamento_pkey`: `CREATE UNIQUE INDEX protocolo_equipamento_pkey ON gestao_lab.protocolo_equipamento USING btree (protocolo_id, equipamento_id)`

## recurso

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `id` | `bigint` | Sim | IDENTITY (BY DEFAULT) |
| `laboratorio_id` | `bigint` | Sim | — |
| `tipo` | `tipo_recurso` | Sim | — |
| `nome` | `text` | Sim | — |
| `estado` | `estado_recurso` | Sim | 'DISPONIVEL'::estado_recurso |
| `responsavel_usuario_id` | `bigint` | Sim | — |
| `observacao` | `text` | Não | — |
| `criado_em` | `timestamp with time zone` | Sim | clock_timestamp() |

Restrições declarativas:

- `recurso_nome_check`: `CHECK ((btrim(nome) <> ''::text))`
- `recurso_laboratorio_id_fkey`: `FOREIGN KEY (laboratorio_id) REFERENCES laboratorio(id)`
- `recurso_responsavel_usuario_id_laboratorio_id_fkey`: `FOREIGN KEY (responsavel_usuario_id, laboratorio_id) REFERENCES professor(usuario_id, laboratorio_id)`
- `recurso_criado_em_not_null`: `NOT NULL criado_em`
- `recurso_estado_not_null`: `NOT NULL estado`
- `recurso_id_not_null`: `NOT NULL id`
- `recurso_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `recurso_nome_not_null`: `NOT NULL nome`
- `recurso_responsavel_usuario_id_not_null`: `NOT NULL responsavel_usuario_id`
- `recurso_tipo_not_null`: `NOT NULL tipo`
- `recurso_pkey`: `PRIMARY KEY (id)`
- `recurso_subtipo`: `TRIGGER DEFERRABLE INITIALLY DEFERRED`
- `recurso_id_laboratorio_id_key`: `UNIQUE (id, laboratorio_id)`
- `recurso_id_tipo_key`: `UNIQUE (id, tipo)`

Índices:

- `recurso_id_laboratorio_id_key`: `CREATE UNIQUE INDEX recurso_id_laboratorio_id_key ON gestao_lab.recurso USING btree (id, laboratorio_id)`
- `recurso_id_tipo_key`: `CREATE UNIQUE INDEX recurso_id_tipo_key ON gestao_lab.recurso USING btree (id, tipo)`
- `recurso_laboratorio_idx`: `CREATE INDEX recurso_laboratorio_idx ON gestao_lab.recurso USING btree (laboratorio_id)`
- `recurso_pkey`: `CREATE UNIQUE INDEX recurso_pkey ON gestao_lab.recurso USING btree (id)`
- `recurso_responsavel_idx`: `CREATE INDEX recurso_responsavel_idx ON gestao_lab.recurso USING btree (responsavel_usuario_id)`

## reserva

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `id` | `bigint` | Sim | IDENTITY (BY DEFAULT) |
| `laboratorio_id` | `bigint` | Sim | — |
| `usuario_id` | `bigint` | Sim | — |
| `recurso_principal_id` | `bigint` | Sim | — |
| `inicio` | `timestamp with time zone` | Sim | — |
| `fim` | `timestamp with time zone` | Sim | — |
| `periodo` | `tstzrange` | Não | GERADA: tstzrange(inicio, fim, '[)'::text) |
| `estado` | `estado_reserva` | Sim | 'CONFIRMADA'::estado_reserva |
| `bloqueia` | `boolean` | Não | GERADA: (estado = 'CONFIRMADA'::estado_reserva) |
| `criado_em` | `timestamp with time zone` | Sim | clock_timestamp() |
| `cancelado_em` | `timestamp with time zone` | Não | — |
| `cancelado_por` | `bigint` | Não | — |
| `motivo_cancelamento` | `text` | Não | — |

Restrições declarativas:

- `reserva_check`: `CHECK ((isfinite(inicio) AND isfinite(fim) AND (fim > inicio)))`
- `reserva_check1`: `CHECK ((((estado = 'CANCELADA'::estado_reserva) AND (cancelado_em IS NOT NULL) AND (cancelado_por IS NOT NULL) AND (NULLIF(btrim(motivo_cancelamento), ''::text) IS NOT NULL)) OR ((estado <> 'CANCELADA'::estado_reserva) AND (cancelado_em IS NULL) AND (cancelado_por IS NULL) AND (motivo_cancelamento IS NULL))))`
- `reserva_cancelado_por_laboratorio_id_fkey`: `FOREIGN KEY (cancelado_por, laboratorio_id) REFERENCES usuario(id, laboratorio_id)`
- `reserva_laboratorio_id_fkey`: `FOREIGN KEY (laboratorio_id) REFERENCES laboratorio(id)`
- `reserva_recurso_principal_id_laboratorio_id_fkey`: `FOREIGN KEY (recurso_principal_id, laboratorio_id) REFERENCES recurso(id, laboratorio_id)`
- `reserva_usuario_id_laboratorio_id_fkey`: `FOREIGN KEY (usuario_id, laboratorio_id) REFERENCES usuario(id, laboratorio_id)`
- `reserva_criado_em_not_null`: `NOT NULL criado_em`
- `reserva_estado_not_null`: `NOT NULL estado`
- `reserva_fim_not_null`: `NOT NULL fim`
- `reserva_id_not_null`: `NOT NULL id`
- `reserva_inicio_not_null`: `NOT NULL inicio`
- `reserva_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `reserva_recurso_principal_id_not_null`: `NOT NULL recurso_principal_id`
- `reserva_usuario_id_not_null`: `NOT NULL usuario_id`
- `reserva_pkey`: `PRIMARY KEY (id)`
- `conferir_reserva`: `TRIGGER DEFERRABLE INITIALLY DEFERRED`
- `reserva_id_laboratorio_id_key`: `UNIQUE (id, laboratorio_id)`
- `reserva_id_periodo_bloqueia_key`: `UNIQUE (id, periodo, bloqueia)`

Índices:

- `reserva_id_laboratorio_id_key`: `CREATE UNIQUE INDEX reserva_id_laboratorio_id_key ON gestao_lab.reserva USING btree (id, laboratorio_id)`
- `reserva_id_periodo_bloqueia_key`: `CREATE UNIQUE INDEX reserva_id_periodo_bloqueia_key ON gestao_lab.reserva USING btree (id, periodo, bloqueia)`
- `reserva_laboratorio_idx`: `CREATE INDEX reserva_laboratorio_idx ON gestao_lab.reserva USING btree (laboratorio_id)`
- `reserva_pkey`: `CREATE UNIQUE INDEX reserva_pkey ON gestao_lab.reserva USING btree (id)`
- `reserva_principal_idx`: `CREATE INDEX reserva_principal_idx ON gestao_lab.reserva USING btree (recurso_principal_id)`
- `reserva_usuario_periodo_idx`: `CREATE INDEX reserva_usuario_periodo_idx ON gestao_lab.reserva USING btree (usuario_id, inicio, fim) WHERE bloqueia`

## reserva_recurso

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `reserva_id` | `bigint` | Sim | — |
| `recurso_id` | `bigint` | Sim | — |
| `laboratorio_id` | `bigint` | Sim | — |
| `periodo` | `tstzrange` | Sim | — |
| `bloqueia` | `boolean` | Sim | — |
| `local_registrado` | `jsonb` | Sim | — |

Restrições declarativas:

- `reserva_recurso_recurso_id_laboratorio_id_fkey`: `FOREIGN KEY (recurso_id, laboratorio_id) REFERENCES recurso(id, laboratorio_id)`
- `reserva_recurso_reserva_id_laboratorio_id_fkey`: `FOREIGN KEY (reserva_id, laboratorio_id) REFERENCES reserva(id, laboratorio_id)`
- `reserva_recurso_reserva_id_periodo_bloqueia_fkey`: `FOREIGN KEY (reserva_id, periodo, bloqueia) REFERENCES reserva(id, periodo, bloqueia) ON UPDATE CASCADE`
- `reserva_recurso_bloqueia_not_null`: `NOT NULL bloqueia`
- `reserva_recurso_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `reserva_recurso_local_registrado_not_null`: `NOT NULL local_registrado`
- `reserva_recurso_periodo_not_null`: `NOT NULL periodo`
- `reserva_recurso_recurso_id_not_null`: `NOT NULL recurso_id`
- `reserva_recurso_reserva_id_not_null`: `NOT NULL reserva_id`
- `reserva_recurso_pkey`: `PRIMARY KEY (reserva_id, recurso_id)`
- `conferir_reserva_recurso`: `TRIGGER DEFERRABLE INITIALLY DEFERRED`
- `reserva_recurso_sem_sobreposicao`: `EXCLUDE USING gist (recurso_id WITH =, periodo WITH &&) WHERE (bloqueia)`

Índices:

- `reserva_recurso_pkey`: `CREATE UNIQUE INDEX reserva_recurso_pkey ON gestao_lab.reserva_recurso USING btree (reserva_id, recurso_id)`
- `reserva_recurso_recurso_idx`: `CREATE INDEX reserva_recurso_recurso_idx ON gestao_lab.reserva_recurso USING btree (recurso_id)`
- `reserva_recurso_sem_sobreposicao`: `CREATE INDEX reserva_recurso_sem_sobreposicao ON gestao_lab.reserva_recurso USING gist (recurso_id, periodo) WHERE bloqueia`

## sala

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `recurso_id` | `bigint` | Sim | — |
| `laboratorio_id` | `bigint` | Sim | — |
| `tipo` | `tipo_recurso` | Não | GERADA: 'SALA'::tipo_recurso |
| `identificacao` | `text` | Sim | — |
| `localizacao` | `text` | Sim | — |
| `capacidade` | `integer` | Sim | — |

Restrições declarativas:

- `sala_capacidade_check`: `CHECK ((capacidade > 0))`
- `sala_identificacao_check`: `CHECK ((btrim(identificacao) <> ''::text))`
- `sala_localizacao_check`: `CHECK ((btrim(localizacao) <> ''::text))`
- `sala_recurso_id_laboratorio_id_fkey`: `FOREIGN KEY (recurso_id, laboratorio_id) REFERENCES recurso(id, laboratorio_id)`
- `sala_recurso_id_tipo_fkey`: `FOREIGN KEY (recurso_id, tipo) REFERENCES recurso(id, tipo)`
- `sala_capacidade_not_null`: `NOT NULL capacidade`
- `sala_identificacao_not_null`: `NOT NULL identificacao`
- `sala_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `sala_localizacao_not_null`: `NOT NULL localizacao`
- `sala_recurso_id_not_null`: `NOT NULL recurso_id`
- `sala_pkey`: `PRIMARY KEY (recurso_id)`
- `sala_subtipo`: `TRIGGER DEFERRABLE INITIALLY DEFERRED`
- `sala_laboratorio_id_identificacao_key`: `UNIQUE (laboratorio_id, identificacao)`
- `sala_recurso_id_laboratorio_id_key`: `UNIQUE (recurso_id, laboratorio_id)`

Índices:

- `sala_laboratorio_id_identificacao_key`: `CREATE UNIQUE INDEX sala_laboratorio_id_identificacao_key ON gestao_lab.sala USING btree (laboratorio_id, identificacao)`
- `sala_pkey`: `CREATE UNIQUE INDEX sala_pkey ON gestao_lab.sala USING btree (recurso_id)`
- `sala_recurso_id_laboratorio_id_key`: `CREATE UNIQUE INDEX sala_recurso_id_laboratorio_id_key ON gestao_lab.sala USING btree (recurso_id, laboratorio_id)`

## schema_versao

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `versao` | `integer` | Sim | — |
| `descricao` | `text` | Sim | — |
| `aplicada_em` | `timestamp with time zone` | Sim | clock_timestamp() |

Restrições declarativas:

- `schema_versao_aplicada_em_not_null`: `NOT NULL aplicada_em`
- `schema_versao_descricao_not_null`: `NOT NULL descricao`
- `schema_versao_versao_not_null`: `NOT NULL versao`
- `schema_versao_pkey`: `PRIMARY KEY (versao)`

Índices:

- `schema_versao_pkey`: `CREATE UNIQUE INDEX schema_versao_pkey ON gestao_lab.schema_versao USING btree (versao)`

## sessao_usuario

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `id` | `bigint` | Sim | IDENTITY (BY DEFAULT) |
| `usuario_id` | `bigint` | Sim | — |
| `token_hash` | `bytea` | Sim | — |
| `criado_em` | `timestamp with time zone` | Sim | clock_timestamp() |
| `expira_em` | `timestamp with time zone` | Sim | — |
| `revogado_em` | `timestamp with time zone` | Não | — |

Restrições declarativas:

- `sessao_usuario_check`: `CHECK ((expira_em > criado_em))`
- `sessao_usuario_check1`: `CHECK (((revogado_em IS NULL) OR (revogado_em >= criado_em)))`
- `sessao_usuario_token_hash_check`: `CHECK ((octet_length(token_hash) = 32))`
- `sessao_usuario_usuario_id_fkey`: `FOREIGN KEY (usuario_id) REFERENCES usuario(id)`
- `sessao_usuario_criado_em_not_null`: `NOT NULL criado_em`
- `sessao_usuario_expira_em_not_null`: `NOT NULL expira_em`
- `sessao_usuario_id_not_null`: `NOT NULL id`
- `sessao_usuario_token_hash_not_null`: `NOT NULL token_hash`
- `sessao_usuario_usuario_id_not_null`: `NOT NULL usuario_id`
- `sessao_usuario_pkey`: `PRIMARY KEY (id)`
- `sessao_usuario_token_hash_key`: `UNIQUE (token_hash)`

Índices:

- `sessao_usuario_pkey`: `CREATE UNIQUE INDEX sessao_usuario_pkey ON gestao_lab.sessao_usuario USING btree (id)`
- `sessao_usuario_token_hash_key`: `CREATE UNIQUE INDEX sessao_usuario_token_hash_key ON gestao_lab.sessao_usuario USING btree (token_hash)`

## solicitacao_reativacao

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `id` | `bigint` | Sim | IDENTITY (BY DEFAULT) |
| `laboratorio_id` | `bigint` | Sim | — |
| `proibicao_id` | `bigint` | Sim | — |
| `solicitado_por` | `bigint` | Sim | — |
| `justificativa` | `text` | Sim | — |
| `estado` | `estado_solicitacao` | Sim | 'PENDENTE'::estado_solicitacao |
| `solicitada_em` | `timestamp with time zone` | Sim | clock_timestamp() |
| `respondida_em` | `timestamp with time zone` | Não | — |
| `respondida_por` | `bigint` | Não | — |
| `resposta` | `text` | Não | — |

Restrições declarativas:

- `solicitacao_reativacao_check`: `CHECK ((((estado <> 'PENDENTE'::estado_solicitacao) AND (respondida_em IS NOT NULL) AND (respondida_por IS NOT NULL) AND (NULLIF(btrim(resposta), ''::text) IS NOT NULL)) OR ((estado = 'PENDENTE'::estado_solicitacao) AND (respondida_em IS NULL) AND (respondida_por IS NULL) AND (resposta IS NULL))))`
- `solicitacao_reativacao_check1`: `CHECK (((respondida_em IS NULL) OR (respondida_em >= solicitada_em)))`
- `solicitacao_reativacao_justificativa_check`: `CHECK ((btrim(justificativa) <> ''::text))`
- `solicitacao_reativacao_laboratorio_id_fkey`: `FOREIGN KEY (laboratorio_id) REFERENCES laboratorio(id)`
- `solicitacao_reativacao_proibicao_id_laboratorio_id_fkey`: `FOREIGN KEY (proibicao_id, laboratorio_id) REFERENCES proibicao_aluno_equipamento(id, laboratorio_id)`
- `solicitacao_reativacao_respondida_por_laboratorio_id_fkey`: `FOREIGN KEY (respondida_por, laboratorio_id) REFERENCES chefe_laboratorio(usuario_id, laboratorio_id)`
- `solicitacao_reativacao_solicitado_por_laboratorio_id_fkey`: `FOREIGN KEY (solicitado_por, laboratorio_id) REFERENCES aluno(usuario_id, laboratorio_id)`
- `solicitacao_reativacao_estado_not_null`: `NOT NULL estado`
- `solicitacao_reativacao_id_not_null`: `NOT NULL id`
- `solicitacao_reativacao_justificativa_not_null`: `NOT NULL justificativa`
- `solicitacao_reativacao_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `solicitacao_reativacao_proibicao_id_not_null`: `NOT NULL proibicao_id`
- `solicitacao_reativacao_solicitada_em_not_null`: `NOT NULL solicitada_em`
- `solicitacao_reativacao_solicitado_por_not_null`: `NOT NULL solicitado_por`
- `solicitacao_reativacao_pkey`: `PRIMARY KEY (id)`

Índices:

- `solicitacao_aberta_unica`: `CREATE UNIQUE INDEX solicitacao_aberta_unica ON gestao_lab.solicitacao_reativacao USING btree (proibicao_id) WHERE (estado = 'PENDENTE'::estado_solicitacao)`
- `solicitacao_reativacao_pkey`: `CREATE UNIQUE INDEX solicitacao_reativacao_pkey ON gestao_lab.solicitacao_reativacao USING btree (id)`

## usuario

| Coluna | Tipo | Obrigatória | Padrão ou geração |
|---|---|---|---|
| `id` | `bigint` | Sim | IDENTITY (BY DEFAULT) |
| `laboratorio_id` | `bigint` | Sim | — |
| `nome` | `text` | Sim | — |
| `email` | `text` | Sim | — |
| `senha_hash` | `text` | Sim | — |
| `ativo` | `boolean` | Sim | true |
| `criado_em` | `timestamp with time zone` | Sim | clock_timestamp() |

Restrições declarativas:

- `usuario_email_check`: `CHECK (((email = lower(btrim(email))) AND (email ~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'::text)))`
- `usuario_nome_check`: `CHECK ((btrim(nome) <> ''::text))`
- `usuario_senha_hash_check`: `CHECK ((length(senha_hash) >= 40))`
- `usuario_laboratorio_id_fkey`: `FOREIGN KEY (laboratorio_id) REFERENCES laboratorio(id) DEFERRABLE INITIALLY DEFERRED`
- `usuario_ativo_not_null`: `NOT NULL ativo`
- `usuario_criado_em_not_null`: `NOT NULL criado_em`
- `usuario_email_not_null`: `NOT NULL email`
- `usuario_id_not_null`: `NOT NULL id`
- `usuario_laboratorio_id_not_null`: `NOT NULL laboratorio_id`
- `usuario_nome_not_null`: `NOT NULL nome`
- `usuario_senha_hash_not_null`: `NOT NULL senha_hash`
- `usuario_pkey`: `PRIMARY KEY (id)`
- `usuario_subtipo`: `TRIGGER DEFERRABLE INITIALLY DEFERRED`
- `usuario_email_key`: `UNIQUE (email)`
- `usuario_id_laboratorio_id_key`: `UNIQUE (id, laboratorio_id)`

Índices:

- `usuario_email_key`: `CREATE UNIQUE INDEX usuario_email_key ON gestao_lab.usuario USING btree (email)`
- `usuario_id_laboratorio_id_key`: `CREATE UNIQUE INDEX usuario_id_laboratorio_id_key ON gestao_lab.usuario USING btree (id, laboratorio_id)`
- `usuario_laboratorio_idx`: `CREATE INDEX usuario_laboratorio_idx ON gestao_lab.usuario USING btree (laboratorio_id)`
- `usuario_pkey`: `CREATE UNIQUE INDEX usuario_pkey ON gestao_lab.usuario USING btree (id)`

## Integridade adicional

As triggers verificam subclasses completas, geram a abrangência das reservas, impedem mudança de local/composição afetando reservas vigentes/futuras, validam empréstimos, cancelam reservas por manutenção/proibição, controlam reativação e preservam auditoria. A descrição funcional e as decisões de implementação estão no guia e no modelo relacional.
