from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from gestao_lab import __main__ as entrada


@pytest.fixture
def ambiente_cli(monkeypatch):
    config = SimpleNamespace(
        database_url="postgresql://localhost/poodev_teste_cli",
        porta=8000,
        horas_sessao=8,
        segredo_csrf=b"segredo-exclusivo-do-teste-de-cli",
    )
    monkeypatch.setattr(entrada.Configuracao, "do_ambiente", lambda: config)
    monkeypatch.setattr(entrada, "pedir_senha", lambda: "SenhaDeTeste2026!")
    monkeypatch.setattr("builtins.input", lambda _mensagem: "valor_teste")
    return monkeypatch


@pytest.mark.parametrize("comando", ["criar-chefe", "definir-senha"])
def test_comandos_administrativos_nao_iniciam_servidor(ambiente_cli, comando):
    ambiente_cli.setattr("sys.argv", ["gestao_lab", comando])
    configuracao = Mock()
    configuracao.criar_chefe.return_value = SimpleNamespace(
        nome="Chefe de teste", laboratorio_id=1
    )
    ambiente_cli.setattr(
        entrada, "ServicoConfiguracaoInicial", Mock(return_value=configuracao)
    )
    iniciar_monitoramento = Mock(side_effect=AssertionError("Monitoramento indevido"))
    iniciar_servidor = Mock(side_effect=AssertionError("Servidor indevido"))
    ambiente_cli.setattr(entrada, "iniciar_monitoramento_estoque", iniciar_monitoramento)
    ambiente_cli.setattr(entrada, "make_server", iniciar_servidor)

    entrada.main()

    iniciar_monitoramento.assert_not_called()
    iniciar_servidor.assert_not_called()
    if comando == "criar-chefe":
        configuracao.criar_chefe.assert_called_once()
    else:
        configuracao.definir_senha.assert_called_once()


def test_comando_servir_encerra_monitoramento(ambiente_cli):
    ambiente_cli.setattr("sys.argv", ["gestao_lab", "servir"])
    parada = Mock()
    servidor = Mock()
    monitoramento = Mock(return_value=parada)
    iniciar_servidor = Mock(return_value=nullcontext(servidor))
    ambiente_cli.setattr(entrada, "iniciar_monitoramento_estoque", monitoramento)
    ambiente_cli.setattr(entrada, "make_server", iniciar_servidor)

    entrada.main()

    monitoramento.assert_called_once()
    iniciar_servidor.assert_called_once()
    servidor.serve_forever.assert_called_once()
    parada.set.assert_called_once()
