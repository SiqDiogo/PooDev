import os
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

from gestao_lab.aplicacao.seguranca import ProtecaoSenha
from gestao_lab.aplicacao.servicos import DadosCadastro, ServicoAutenticacao, ServicoCadastro, ServicoConfiguracaoInicial
from gestao_lab.infraestrutura.postgres import UnidadeTrabalhoPostgres


@pytest.fixture
def sistema():
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("Defina TEST_DATABASE_URL para executar a integração.")
    banco = conninfo_to_dict(url).get("dbname", "")
    if not (banco.startswith("gestao_laboratorio_teste") or banco.startswith("poodev_teste_")):
        pytest.fail("TEST_DATABASE_URL deve apontar para um banco de teste com nome permitido.")
    with psycopg.connect(url) as conn:
        assert conn.execute("SELECT to_regclass('gestao_lab.usuario') IS NOT NULL").fetchone()[0], "Instale o schema no banco de testes."
    transacao = lambda: UnidadeTrabalhoPostgres(url)
    senhas = ProtecaoSenha()
    autenticacao = ServicoAutenticacao(transacao, senhas)
    cadastro = ServicoCadastro(transacao, senhas, autenticacao)
    inicial = ServicoConfiguracaoInicial(transacao, senhas)
    chave = uuid4().hex
    senha = "SenhaFicticiaDeTeste2026!"
    chefe = inicial.criar_chefe(f"Laboratório de teste {chave}", "Sala de teste",
                               DadosCadastro(nome="Chefe de teste", email=f"chefe.{chave}@example.org",
                                             senha=senha, programa_pos="Biociências"))
    token = autenticacao.entrar(chefe.email, senha)
    return SimpleNamespace(url=url, transacao=transacao, senhas=senhas, auth=autenticacao, cadastro=cadastro,
                           inicial=inicial, chave=chave, senha=senha, chefe=chefe, token=token)


@pytest.fixture
def dados_professor(sistema):
    return DadosCadastro(nome="Professor de teste", email=f"prof.{sistema.chave}@example.org",
                         senha=sistema.senha, programa_pos="Biociências", ramal="1234")
