# Semana 2 — Cadastro de perfis

Esta etapa implementa os perfis Aluno, Professor e Chefe de Laboratório, com cadastro, login, logout e consulta do próprio perfil. Os dados são gravados no PostgreSQL da primeira semana.

## Funcionamento

O Chefe cadastra Alunos e Professores do próprio laboratório e consulta a lista de usuários. Professor e Aluno acessam seu perfil após o login. O primeiro Chefe é configurado localmente pelo VS Code.

- E-mail e matrícula são únicos em todo o sistema.
- O orientador do Aluno deve ser um Professor ativo do mesmo laboratório. O Chefe também pode orientar.
- As senhas são armazenadas como hash. A sessão identifica quem está realizando o cadastro.
- O cadastro é gravado em uma transação: usuário e perfil são salvos juntos.

`Usuario` reúne os dados comuns. `Aluno` e `Professor` herdam dessa classe; `ChefeLaboratorio` herda de `Professor`.

| Pasta em `gestao_lab/` | Função |
| --- | --- |
| `dominio/` | Classes dos perfis e validações dos dados. |
| `aplicacao/` | Regras de cadastro, autenticação e primeiro acesso. |
| `infraestrutura/` | Conexão e consultas ao PostgreSQL. |
| `apresentacao/` | Páginas e atendimento dos formulários. |

## Primeiro acesso

Prepare o ambiente pelo [README principal](../README.md). Em **Executar e Depurar**, escolha uma das opções e pressione `F5`:

| Situação do banco | Configuração |
| --- | --- |
| Sem laboratório e sem Chefe | **Laboratório: criar Chefe inicial**. Cria ambos. |
| Dados de exemplo instalados, sem senha de acesso definida | **Laboratório: redefinir senha**. Use `chefe.a@example.org`. |
| Chefe já configurado, com senha conhecida | **Laboratório: iniciar sistema**. |

A senha da conta deve ter entre 12 e 128 caracteres. Ela é diferente da senha de conexão com o PostgreSQL. Criar outro Chefe pelo comando inicial cria outro laboratório.

## Conferência

Entre como Chefe, cadastre um Professor e depois um Aluno. Confira a lista e faça login com cada conta. Tente repetir um e-mail ou uma matrícula para verificar a rejeição do cadastro.

Para os testes sem banco, execute **Tasks: Run Task > Laboratório: testar domínio**. Os testes de integração exigem um banco separado chamado, por exemplo, `gestao_laboratorio_teste_semana2`, com o schema instalado. Defina `TEST_DATABASE_URL` no `.env` e execute **Laboratório: executar todos os testes** com `F5`.

Sem o banco de testes configurado, os testes de integração são ignorados. A interface de reservas, chaves e estoque fica para as próximas etapas.
