
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock

from gestao_lab.dominio.erros import AcessoNegado
from gestao_lab.dominio.historico import HistoricoUso
from gestao_lab.dominio.laboratorios import Laboratorio
from gestao_lab.dominio.usuarios import (
    Professor,
    ChefeLaboratorio
)
from gestao_lab.infraestrutura.postgres import (
    HistoricoUsoPostgres
)
from gestao_lab.aplicacao.servicos import (
    ServicoHistoricoUso
)


agora = datetime.now(timezone.utc)

# TESTE 1 — Repositório transforma linhas em objetos.
linha = {
    "id": 5,
    "laboratorio_id": 1,
    "tabela": "reserva",
    "registro_id": "10",
    "acao": "UPDATE",
    "registrado_em": agora,
    "ator_id": 1,
    "motivo": "Cancelamento de teste",
    "antes": {"estado": "CONFIRMADA"},
    "depois": {"estado": "CANCELADA"}
}

conexao = Mock()
linha.update(ator_nome="Chefe", recurso_nome="Equipamento", usuario_nome="Professor", reserva_id=10, codigo_copia=None,
             designada_anterior=None, designada_atual=None)
cursor_eventos, cursor_locais = Mock(), Mock()
cursor_eventos.fetchall.return_value = [linha]
cursor_locais.fetchall.return_value = []
conexao.execute.side_effect = [cursor_eventos, cursor_locais]

repositorio = HistoricoUsoPostgres(conexao)

eventos = repositorio.listar(
    1,
    2,
    False,
    recurso_id=3
)

assert len(eventos) == 1
assert isinstance(eventos[0], HistoricoUso)
assert eventos[0].eh_cancelamento()

sql, parametros = conexao.execute.call_args_list[0].args

assert "gestao_lab.historico_uso" in sql
assert "JOIN gestao_lab.reserva" in sql
assert "reserva_recurso" in sql

assert parametros[0] == 1
assert 2 in parametros and 3 in parametros

print("Teste 1: repositório funcionando.")


# TESTE 2 — Serviço limita a consulta do Professor.
professor = Professor(
    id=2,
    laboratorio_id=1,
    nome="Professor Teste",
    email="professor@example.org",
    senha_hash="hash_teste",
    programa_pos="Computacao"
)

chefe = ChefeLaboratorio(
    id=1,
    laboratorio_id=1,
    nome="Chefe Teste",
    email="chefe@example.org",
    senha_hash="hash_teste",
    programa_pos="Computacao"
)

laboratorio = Laboratorio(
    id=1,
    nome="Laboratorio Teste",
    localizacao="Bloco A",
    chefe_usuario_id=1
)

transacao = MagicMock()
transacao.__enter__.return_value = transacao
transacao.laboratorios.buscar_por_id.return_value = laboratorio
transacao.historico.listar.return_value = eventos

autenticacao = Mock()
autenticacao.identificar_na_transacao.return_value = professor

servico = ServicoHistoricoUso(
    lambda: transacao,
    autenticacao
)

resultado = servico.listar(
    "token_teste",
    recurso_id=3
)

assert resultado == eventos

transacao.historico.listar.assert_called_once_with(
    1,
    2,
    False,
    usuario_id=None,
    recurso_id=3,
    desde=None,
    ate=None
)

print("Teste 2: consulta do Professor funcionando.")


# TESTE 3 — Professor não consulta histórico alheio.
transacao.historico.listar.reset_mock()

try:
    servico.listar(
        "token_teste",
        usuario_id=1
    )
except AcessoNegado:
    pass
else:
    raise AssertionError(
        "Professor não deveria consultar outro usuário."
    )

transacao.historico.listar.assert_not_called()

print("Teste 3: acesso indevido bloqueado.")


# TESTE 4 — Chefe consulta outro usuário do laboratório.
autenticacao.identificar_na_transacao.return_value = chefe

servico.listar(
    "token_teste",
    usuario_id=2
)

transacao.historico.listar.assert_called_once_with(
    1,
    1,
    True,
    usuario_id=2,
    recurso_id=None,
    desde=None,
    ate=None
)

print("Teste 4: consulta do Chefe funcionando.")

print("Todos os 4 testes da consulta de histórico passaram!")
