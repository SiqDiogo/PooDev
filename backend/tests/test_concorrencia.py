from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from types import SimpleNamespace
import psycopg
import pytest

from gestao_lab.dominio.erros import DadosInvalidos

pytestmark = [pytest.mark.integracao, pytest.mark.concorrencia]


@pytest.fixture(autouse=True)
def exigir_postgresql_nativo(sistema):
    with psycopg.connect(sistema.url) as conn:
        versao = conn.execute("SELECT version()").fetchone()[0]
    if "PGlite" in versao or "emscripten" in versao:
        pytest.skip("Concorrência exige PostgreSQL nativo; PGlite serializa conexões na instância WASM.")


def criar(sistema, token, recurso_id, inicio, fim):
    return SimpleNamespace(id=sistema.reservas.reservar(token, recurso_id=recurso_id, inicio=inicio, fim=fim))


def competir(primeira, segunda, mensagem):
    barreira = Barrier(2)

    def executar(operacao):
        barreira.wait(timeout=15)
        try:
            return True, operacao()
        except DadosInvalidos as erro:
            return False, str(erro)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futuros = [pool.submit(executar, operacao) for operacao in (primeira, segunda)]
        resultados = [f.result(timeout=30) for f in futuros]
    assert sum(sucesso for sucesso, _ in resultados) == 1, resultados
    assert mensagem in next(valor for sucesso, valor in resultados if not sucesso)


@pytest.mark.parametrize("indice", [0, 2])
def test_reservas_simultaneas_de_sala_ou_mesmo_equipamento_nao_se_sobrepoem(sistema, recursos, portador, periodo, indice):
    _, token = portador
    competir(lambda: criar(sistema, sistema.token, recursos[2].id, *periodo),
             lambda: criar(sistema, token, recursos[indice].id, *periodo), "já está reservado")
    assert len(sistema.reservas.listar(sistema.token)) == 1


def test_limite_por_usuario_resiste_a_confirmacoes_simultaneas(sistema, recursos, periodo):
    sistema.limites.configurar(sistema.token, duracao_minutos=None, quantidade=1)
    competir(lambda: criar(sistema, sistema.token, recursos[2].id, *periodo),
             lambda: criar(sistema, sistema.token, recursos[3].id, *periodo), "simultâneas")
    assert len(sistema.reservas.listar(sistema.token)) == 1


def test_mesma_copia_nao_e_entregue_a_dois_portadores_simultaneamente(sistema, recursos, portador, periodo):
    _, token = portador
    chave = sistema.chaves.cadastrar(sistema.token, codigo_copia=f'CONC-{sistema.chave}', destino_id=recursos[0].id)
    a = criar(sistema, sistema.token, recursos[2].id, *periodo)
    b = criar(sistema, token, recursos[3].id, *periodo)
    competir(lambda: sistema.chaves.retirar(sistema.token, chave.id, a.id),
             lambda: sistema.chaves.retirar(sistema.token, chave.id, b.id), "retirada em aberto")
    assert len(sistema.chaves.painel(sistema.token)[2]) == 1
