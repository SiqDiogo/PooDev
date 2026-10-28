import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

from gestao_lab.aplicacao.seguranca import ProtecaoSenha
from gestao_lab.aplicacao.servicos import DadosCadastro, ServicoAutenticacao, ServicoCadastro, ServicoConfiguracaoInicial
from gestao_lab.infraestrutura.postgres import UnidadeTrabalhoPostgres
from gestao_lab.aplicacao.servicos import ServicoRecursos, ServicoReservas, ServicoHistoricoUso, ServicoLimitesReserva
from gestao_lab.aplicacao.chaves import ServicoChaves
from gestao_lab.dominio.usuarios import Perfil

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


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
    recursos = ServicoRecursos(transacao, autenticacao)
    reservas = ServicoReservas(transacao, autenticacao)
    historico = ServicoHistoricoUso(transacao, autenticacao)
    limites = ServicoLimitesReserva(transacao, autenticacao)
    chaves = ServicoChaves(transacao, autenticacao)
    inicial = ServicoConfiguracaoInicial(transacao, senhas)
    chave = uuid4().hex
    senha = "SenhaFicticiaDeTeste2026!"
    chefe = inicial.criar_chefe(f"Laboratório de teste {chave}", "Sala de teste",
                               DadosCadastro(nome="Chefe de teste", email=f"chefe.{chave}@example.org",
                                             senha=senha, programa_pos="Biociências"))
    token = autenticacao.entrar(chefe.email, senha)
    return SimpleNamespace(url=url, transacao=transacao, senhas=senhas, auth=autenticacao, cadastro=cadastro,
                           inicial=inicial, recursos=recursos, reservas=reservas, historico=historico, limites=limites, chaves=chaves, chave=chave, senha=senha, chefe=chefe, token=token)


@pytest.fixture
def dados_professor(sistema):
    return DadosCadastro(nome="Professor de teste", email=f"prof.{sistema.chave}@example.org",
                         senha=sistema.senha, programa_pos="Biociências", ramal="1234")


@pytest.fixture
def recursos(sistema):
    sala = sistema.recursos.cadastrar_sala(sistema.token, nome="Sala de teste", identificacao="S1", localizacao="Bloco A, sala 1", capacidade=10)
    bancada = sistema.recursos.cadastrar_bancada(sistema.token, nome="Bancada de teste", numero_identificacao="B1", sala_id=sala.id)
    equipamento = sistema.recursos.cadastrar_equipamento(sistema.token, nome="Microscópio", numero_patrimonio=f"EQ-{sistema.chave}",
        complemento_local="Posição 1", bancada_id=bancada.id)
    direto = sistema.recursos.cadastrar_equipamento(sistema.token, nome="Centrífuga", numero_patrimonio=f"D-{sistema.chave}",
        complemento_local="Armário 2", sala_direta_id=sala.id)
    return sala, bancada, equipamento, direto


@pytest.fixture
def periodo():
    inicio = (datetime.now(timezone.utc) + timedelta(days=1)).replace(second=0, microsecond=0)
    return inicio, inicio + timedelta(hours=1)


@pytest.fixture
def portador(sistema):
    usuario = sistema.cadastro.cadastrar(sistema.token, Perfil.ALUNO, DadosCadastro(
        nome="Portador da chave", email=f"portador.{sistema.chave}@example.org", senha=sistema.senha,
        matricula=sistema.chave, orientador_id=sistema.chefe.id))
    return usuario, sistema.auth.entrar(usuario.email, sistema.senha)
