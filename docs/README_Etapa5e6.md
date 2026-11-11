# PooDev — semanas 5 e 6: estoque e protocolos

As semanas 5 e 6 acrescentam dois módulos ao Sistema de Gestão de Laboratório de Pesquisa. O primeiro registra materiais por lote, suas quantidades, movimentações e alertas. O segundo gerencia protocolos em PDF, desde o cadastro até a validação pelo Chefe e o vínculo com equipamentos.

O projeto mantém a organização em domínio, aplicação, infraestrutura e apresentação, com Python, PostgreSQL, Psycopg 3 e uma aplicação web WSGI própria. O agente especialista de IA ainda não faz parte desses módulos.

## Semana 5 — controle de estoque

### Modelo de domínio

**Arquivo:** `backend/gestao_lab/dominio/estoque.py`

- `ItemEstoque`: representa um material identificado por laboratório, nome, unidade e lote. Guarda quantidade, limite de estoque baixo, validade e situação do cadastro.
- `ItemEstoque.__post_init__()`: valida os campos quando o objeto é criado. Não aceita quantidade negativa nem valores numéricos com mais de quatro casas decimais.
- `ItemEstoque.estoque_baixo()`: indica quando a quantidade é menor ou igual ao limite informado.
- `ItemEstoque.validade_proxima(dias, hoje)`: verifica se a validade já passou ou se está dentro da janela de alerta.
- `MovimentacaoEstoque`: registra uma mudança de quantidade, com saldo anterior, saldo posterior, motivo, responsável e horário. A própria classe verifica se os valores são coerentes.

As classes usam `@dataclass(frozen=True)`. Com isso, o código cria representações validadas dos dados, sem alterar silenciosamente os atributos dos objetos já carregados. Uma alteração de estoque passa pelo serviço e pelo banco.

Os saldos usam `Decimal`, pois itens podem ser medidos em unidades fracionadas, como 0,1250 mL. Essa escolha evita as imprecisões habituais de `float` em cálculos decimais.

### Regras de aplicação

**Arquivo:** `backend/gestao_lab/aplicacao/servicos.py`, classe `ServicoEstoque`

| Método | Responsabilidade |
| --- | --- |
| `_exigir_chefe()` | Confirma que a sessão pertence ao Chefe ativo do laboratório correto. |
| `listar()` e `consultar()` | Recuperam os itens pertencentes ao laboratório. |
| `cadastrar()` | Monta um `ItemEstoque`, grava o material e solicita a avaliação dos alertas. |
| `movimentar()` | Valida item, variação e motivo; impede saída acima do saldo; registra o movimento. |
| `listar_movimentacoes()` | Recupera as movimentações registradas, com filtro opcional por item. |
| `listar_alertas()` | Recupera notificações de estoque baixo e validade destinadas ao Chefe. |

O cadastro e a movimentação estão restritos ao Chefe. Uma saída usa variação negativa; uma entrada usa variação positiva. Variação igual a zero é rejeitada, e toda movimentação exige motivo.

### Persistência, histórico e alertas

**Arquivo:** `backend/gestao_lab/infraestrutura/postgres.py`, classe `EstoquePostgres`

O repositório executa SQL com parâmetros pelo Psycopg. `criar()` grava o item e registra o contexto da operação. `movimentar()` chama a função PostgreSQL `gestao_lab.movimentar_estoque`, que atualiza o saldo. O histórico fica na tabela `movimentacao_estoque`.

Após cadastro e movimentação, `avaliar_alertas()` chama `gestao_lab.avaliar_alertas_estoque`. O banco registra notificações do tipo `ESTOQUE_BAIXO` ou `VALIDADE`. A chave de deduplicação evita repetir indefinidamente o mesmo alerta enquanto sua condição permanece ativa.

O comando de inicialização do servidor, em `backend/gestao_lab/__main__.py`, também inicia uma verificação periódica dos alertas com intervalo de dez minutos. É uma tarefa local em segundo plano; não há, nesta entrega, envio de e-mail por SMTP.

**Interface:** `backend/gestao_lab/apresentacao/paginas_estoque.py`, com a rota `/estoque` tratada em `apresentacao/web.py`. Os formulários usam a sessão e o token CSRF da aplicação.

**Exemplo:** um reagente de 100 mL, com limite de 25 mL, recebe uma saída de 80 mL. O saldo passa a 20 mL, a movimentação fica no histórico e surge um alerta de estoque baixo. Outra saída de 30 mL é rejeitada por falta de saldo.

## Semana 6 — protocolos em PDF

### Modelo e validação do arquivo

**Arquivo:** `backend/gestao_lab/dominio/protocolos.py`

- `Protocolo`: guarda metadados, autor, estado, datas de assinatura e validação e vínculos com equipamentos.
- `VinculoEquipamento`: representa um equipamento associado ao protocolo.
- `validar_documento_pdf()`: verifica título, nome do arquivo, extensão `.pdf`, assinatura inicial `%PDF-` e limite de 5 MiB.

A checagem `%PDF-` é uma validação inicial do tipo de arquivo, não uma análise completa da estrutura interna do PDF. O conteúdo binário é mantido como recebido.

### Operações e permissões

**Arquivo:** `backend/gestao_lab/aplicacao/protocolos.py`, classe `ServicoProtocolos`

| Método | Responsabilidade |
| --- | --- |
| `listar()` e `consultar()` | Mostram protocolos do laboratório do usuário autenticado. |
| `cadastrar()` | Valida o PDF, identifica o autor pela sessão e grava o arquivo. |
| `assinar()` | Permite a assinatura somente pelo autor identificado na sessão. |
| `validar()` | Permite a validação somente pelo Chefe, após a assinatura. |
| `vincular()` | Associa um protocolo validado a equipamento do mesmo laboratório, mediante autorização do Chefe. |
| `baixar()` | Recupera o nome e os bytes originais do PDF para usuário do laboratório. |

O fluxo de estados é: **cadastrado e não assinado → assinado → validado → vinculado a equipamento**. Um protocolo validado pode ter vários equipamentos associados.

A assinatura identifica o usuário autenticado e registra o horário no sistema. **Não é assinatura digital com certificado criptográfico.** Um protocolo assinado não pode ter seu conteúdo substituído, conforme as regras do PostgreSQL.

### Banco e interface

**Arquivo:** `backend/gestao_lab/infraestrutura/protocolos_postgres.py`, classe `ProtocolosPostgres`

O PDF original fica na coluna `pdf_original` (`bytea`) da tabela `protocolo`. Essa decisão mantém arquivo e metadados sob a mesma transação e evita depender de caminhos locais para baixar documentos. O método `arquivo()` devolve os bytes sem conversão.

As funções SQL `gestao_lab.assinar_protocolo` e `gestao_lab.validar_protocolo` aplicam as mudanças de estado. Restrições e gatilhos impedem edição indevida após assinatura ou validação. A tabela `protocolo_equipamento` mantém as associações.

**Interface:** `apresentacao/paginas_protocolos.py` monta as páginas, e `apresentacao/web.py` atende `/protocolos`, `/protocolos/novo`, `/protocolos/detalhe`, `/protocolos/assinar`, `/protocolos/validar`, `/protocolos/vincular` e `/protocolos/download`. O upload usa `multipart/form-data`, com controle de tamanho, sessão e CSRF. O download utiliza `Content-Type: application/pdf`.

## Por que essas escolhas técnicas?

| Escolha | Motivo no projeto |
| --- | --- |
| Classes de domínio separadas dos serviços | As validações ficam testáveis sem navegador ou PostgreSQL. Os serviços tratam autenticação e casos de uso. |
| Interfaces de repositório e `UnidadeTrabalho` | O serviço depende de operações definidas, enquanto a implementação PostgreSQL controla consultas e transações. |
| PostgreSQL com SQL explícito | Aproveita o esquema, funções de integridade, auditoria e regras de concorrência já construídos nas semanas anteriores. |
| Psycopg 3 sem ORM | Mantém visíveis as consultas e funções SQL que o trabalho precisa explicar na disciplina. |
| WSGI e HTML gerado pelo projeto | Preserva a arquitetura atual, sem acrescentar framework web apenas para os novos módulos. |
| `Decimal` para estoque | Mantém valores decimais precisos e limite de quatro casas no domínio. |
| `bytea` para PDFs pequenos | Permite salvar e recuperar o mesmo arquivo junto de seus metadados na transação do banco. |
| Sessão, autorização por laboratório e CSRF | Associam cada operação ao usuário e impedem ações de outro laboratório ou formulários não autorizados. |

## Arquivos e testes acrescentados

Na semana 5, o serviço, o domínio, o repositório, as páginas de estoque, o monitor de alertas e os testes foram integrados à base existente. As correções locais também ajustaram a inicialização pela CLI e testes dos scripts.

Na semana 6 foram acrescentados `dominio/protocolos.py`, `aplicacao/protocolos.py`, `infraestrutura/protocolos_postgres.py`, `apresentacao/paginas_protocolos.py` e testes específicos. As rotas, o repositório de contratos e a unidade de trabalho foram ampliados para receber o novo módulo.

Na validação disponível durante a preparação do pacote, o pytest registrou **54 testes aprovados e 72 ignorados**, além de quatro subtestes aprovados. Os testes ignorados exigem um PostgreSQL de testes configurado no ambiente de execução. Isso não substitui a conferência do fluxo completo no banco local da dupla.

O agente especialista de controle de estoque permanece em definição acadêmica e **não foi implementado** nesta versão.
