-- Consultas de leitura. Execute depois de instalar, com ou sem massa de exemplo.
SET search_path = gestao_lab, public;
SET TIME ZONE 'America/Sao_Paulo';

-- 1. Local exato de cada unidade física de equipamento.
SELECT recurso_id,recurso_nome,numero_patrimonio,laboratorio_nome,sala_identificacao,
       sala_nome,sala_localizacao,bancada_identificacao,bancada_nome,complemento_local,estado
FROM vw_local_equipamento ORDER BY laboratorio_id,sala_id,bancada_id,numero_patrimonio;

-- 2. Cópias de chave e portador atual, sem estado EM_USO desatualizado.
SELECT id,codigo_copia,sala_id,bancada_id,estado,designada_para,portador_usuario_id,retirada_em
FROM vw_chave_estado ORDER BY laboratorio_id,codigo_copia;

-- 3. Recursos materializados em cada reserva; local_registrado é histórico.
SELECT r.id reserva_id,u.nome usuario,r.estado,r.inicio,r.fim,rr.recurso_id,rr.local_registrado
FROM reserva r JOIN usuario u ON u.id=r.usuario_id JOIN reserva_recurso rr ON rr.reserva_id=r.id
ORDER BY r.id,rr.recurso_id;

-- 4. Unidades e conjuntos disponíveis no intervalo informado.
-- Consulta de disponibilidade não garante confirmação; criar_reserva confirma atomicamente.
SELECT id,tipo,nome,recurso_disponivel(id,'2099-11-03 08:00-03','2099-11-03 10:00-03') disponivel
FROM recurso WHERE laboratorio_id=1 ORDER BY tipo,id;

-- 5. Proibições ativas e pedidos de reativação.
SELECT p.id,p.aluno_id,p.equipamento_id,p.motivo,s.id solicitacao_id,s.estado
FROM proibicao_aluno_equipamento p LEFT JOIN solicitacao_reativacao s ON s.proibicao_id=p.id
WHERE p.encerrada_em IS NULL ORDER BY p.id,s.id;

-- 6. Alertas de estoque e fila de e-mails (envio real pertence à aplicação).
SELECT i.id,i.nome,i.lote,i.quantidade,i.unidade,i.validade
FROM item_estoque i JOIN laboratorio l ON l.id=i.laboratorio_id
WHERE i.ativo AND (i.quantidade<=i.limite_estoque_baixo OR i.validade<=current_date+l.dias_alerta_validade);
SELECT e.id,n.destinatario_id,n.tipo,e.estado,e.tentativas,e.proxima_tentativa_em
FROM envio_email e JOIN notificacao n ON n.id=e.notificacao_id
WHERE e.estado<>'ENVIADO' ORDER BY e.proxima_tentativa_em;

-- 7. Histórico do laboratório; a aplicação filtra por usuário/perfil autenticado.
SELECT registrado_em,ator_id,tabela,registro_id,acao,motivo,antes,depois
FROM historico_uso WHERE laboratorio_id=1 ORDER BY registrado_em DESC LIMIT 50;

-- Operações ilustrativas, comentadas para não alterar dados ao executar este arquivo:
-- SELECT criar_reserva(3,301,'2099-11-03 08:00-03','2099-11-03 10:00-03');
-- SELECT cancelar_reserva(3,<id_da_reserva>,'Desistência do usuário');
-- SELECT retirar_chave(3,<id_da_reserva>,1,2);
-- SELECT devolver_chave(<id_do_emprestimo>,2);
-- SELECT proibir_aluno(1,3,301,'Motivo informado pelo Chefe');
-- SELECT solicitar_reativacao(3,<id_da_proibicao>,'Justificativa do aluno');
-- SELECT responder_reativacao(1,<id_da_solicitacao>,true,'Aprovado pelo Chefe');
-- SELECT definir_estado_recurso(1,301,'MANUTENCAO','Revisão programada');
-- SELECT movimentar_estoque(1,1,-5,'Uso em atividade do laboratório');
-- SELECT avaliar_alertas_estoque(1);
