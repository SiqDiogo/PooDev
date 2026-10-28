# Semana 4 — Reservas e controle de chaves

Qualquer perfil autenticado consulta a disponibilidade e reserva uma sala, bancada ou equipamento do próprio laboratório. Salas e bancadas abrangem seus componentes; equipamentos distintos podem ser utilizados separadamente. Os horários das telas seguem Brasília.

O Chefe configura duração máxima e quantidade simultânea de reservas. O titular ou o Chefe cancela uma reserva ainda não encerrada, informando um motivo. O PostgreSQL valida conflitos, limites e permissões durante a gravação.

Em **Chaves**, o Chefe ou Professor responsável cadastra as cópias e pode compartilhá-las ou designá-las a usuários ativos. O responsável registra a entrega física vinculada a uma reserva autorizada e o recebimento na devolução. Cada cópia admite um empréstimo aberto por vez.

Fim e cancelamento de reserva preservam a posse da chave. Extravio e indisponibilidade são registrados como ocorrências; a cópia pode voltar à condição operacional após conferência, mantendo o histórico.

**Recursos** exibe a localização dos equipamentos. O Chefe mantém os vínculos e pode alterar a sala, bancada e complemento, respeitando as reservas afetadas. **Histórico** reúne reservas, chaves, localização e limites, com ator, motivo e filtros; cada usuário consulta suas operações e o Chefe consulta o laboratório.

As operações reutilizam as funções SQL existentes. Os testes de integração usam um banco separado em `TEST_DATABASE_URL`; os de concorrência exigem PostgreSQL nativo. As tarefas do VS Code permitem executar todos os testes ou somente a concorrência. Os scripts `teste_*semana4.py` também são executados pela bateria do pytest.
