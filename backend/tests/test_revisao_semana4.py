from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import psycopg
import pytest

from gestao_lab.dominio.erros import AcessoNegado, DadosInvalidos
from test_web import cliente

pytestmark = pytest.mark.integracao


def reservar(sistema, recurso, periodo, token=None):
    return sistema.reservas.reservar(token or sistema.token, recurso_id=recurso.id, inicio=periodo[0], fim=periodo[1])


def dados_periodo(periodo):
    fuso = timezone(timedelta(hours=-3))
    return {nome: data.astimezone(fuso).strftime("%Y-%m-%dT%H:%M") for nome, data in zip(("inicio", "fim"), periodo)}


def test_reserva_no_passado_e_rejeitada_sem_gravacao(sistema, recursos):
    inicio = datetime.now(timezone.utc) - timedelta(days=1)
    with pytest.raises(DadosInvalidos, match="futuro"):
        reservar(sistema, recursos[2], (inicio, inicio + timedelta(hours=1)))
    assert sistema.reservas.listar(sistema.token) == []


def test_reserva_encerrada_nao_e_cancelada_e_nao_oferece_acao_na_tela(sistema, recursos, cliente):
    inicio = datetime.now(timezone.utc) - timedelta(days=1)
    with sistema.transacao() as tx:
        rid = tx.reservas.criar(sistema.chefe.id, recursos[2].id, inicio, inicio + timedelta(hours=1))
    with pytest.raises(DadosInvalidos, match="encerrada"):
        sistema.reservas.cancelar(sistema.token, reserva_id=rid, motivo="Teste")
    cliente.entrar(sistema.chefe.email, sistema.senha)
    resposta = cliente.requisitar("/reservas")
    assert resposta.status == 200 and 'name="reserva_id"' not in resposta.body
    assert sistema.reservas.listar(sistema.token)[0]["estado"] == "CONFIRMADA"


@pytest.mark.parametrize("primeiro,segundo", [(0,2), (2,0), (1,2), (2,1)])
def test_conflitos_de_conjunto_em_ambos_os_sentidos_com_rollback(sistema, recursos, periodo, primeiro, segundo):
    reservar(sistema, recursos[primeiro], periodo)
    with pytest.raises(DadosInvalidos, match="reservado"):
        reservar(sistema, recursos[segundo], periodo)
    assert len(sistema.reservas.listar(sistema.token)) == 1


def test_unidades_distintas_limite_simultaneo_e_intervalos_consecutivos(sistema, recursos, periodo):
    inicio, fim = periodo
    sistema.limites.configurar(sistema.token, duracao_minutos=60, quantidade=1)
    reservar(sistema, recursos[2], periodo)
    with pytest.raises(DadosInvalidos, match="simultâneas"):
        reservar(sistema, recursos[3], periodo)
    reservar(sistema, recursos[3], (fim, fim + timedelta(hours=1)))
    assert len(sistema.reservas.listar(sistema.token)) == 2
    with pytest.raises(DadosInvalidos):
        sistema.limites.configurar(sistema.token, duracao_minutos=60, quantidade=2147483648)


def test_desvinculo_pela_interface_preserva_o_complemento_informado(sistema, recursos, cliente):
    cliente.entrar(sistema.chefe.email, sistema.senha)
    pagina = cliente.requisitar("/recursos/vinculos")
    resposta = cliente.requisitar("/recursos/vinculos", {"csrf": cliente.csrf(pagina), "acao": "desvincular",
        "equipamento_id": recursos[2].id, "complemento_local": "Prateleira 9"})
    assert resposta.status == 303
    e = sistema.recursos.consultar_localizacao(sistema.token, recursos[2].id)
    assert e.bancada_id is None and e.sala_direta_id == recursos[0].id and e.complemento_local == "Prateleira 9"


def test_historico_inclui_chaves_e_localizacao_com_ator_e_filtros(sistema, recursos, portador, periodo):
    usuario, token = portador
    desde = datetime.now(timezone.utc)
    copia = sistema.chaves.cadastrar(sistema.token, codigo_copia=f'HIST-{sistema.chave}', destino_id=recursos[0].id)
    rid = reservar(sistema, recursos[2], periodo, token)
    emprestimo = sistema.chaves.retirar(sistema.token, copia.id, rid)
    sistema.reservas.cancelar(sistema.token, reserva_id=rid, motivo="Mudança de posição")
    sistema.chaves.devolver(sistema.token, emprestimo)
    sistema.recursos.alterar_localizacao(sistema.token, recursos[2].id, sala_direta_id=recursos[0].id, complemento_local="Prateleira 9")
    eventos = sistema.historico.listar(token, recurso_id=recursos[2].id, desde=desde)
    descricoes = [e.descricao for e in eventos]
    for acao in ("Reserva confirmada", "Reserva cancelada", "Retirada de chave", "Devolução de chave", "Localização alterada"):
        assert any(d.startswith(acao) for d in descricoes)
    evento = next(e for e in eventos if e.descricao.startswith("Localização alterada"))
    assert "Posição 1" in evento.descricao and "Prateleira 9" in evento.descricao and evento.ator_nome == sistema.chefe.nome
    assert sistema.historico.listar(token, recurso_id=recursos[3].id) == []
    with pytest.raises(AcessoNegado):
        sistema.historico.listar(token, usuario_id=sistema.chefe.id)
    with psycopg.connect(sistema.url) as conn:
        assert conn.execute("SELECT local_registrado->>'complemento_local' FROM gestao_lab.reserva_recurso WHERE reserva_id=%s AND recurso_id=%s",
                            (rid, recursos[2].id)).fetchone()[0] == "Posição 1"


def test_mudanca_de_local_bloqueada_por_reserva_futura_e_consulta_liberada_para_aluno(sistema, recursos, portador, periodo):
    _, token = portador
    reservar(sistema, recursos[0], periodo)
    with pytest.raises(DadosInvalidos, match="reserva ativa ou futura"):
        sistema.recursos.alterar_localizacao(sistema.token, recursos[2].id, bancada_id=recursos[1].id, complemento_local="Posição 9")
    assert sistema.recursos.listar(token)[2]
    with pytest.raises(AcessoNegado):
        sistema.recursos.alterar_localizacao(token, recursos[2].id, bancada_id=recursos[1].id, complemento_local="Posição 9")


def test_consulta_de_disponibilidade_na_tela_nao_cria_reserva(sistema, recursos, cliente, periodo):
    reservar(sistema, recursos[2], periodo)
    cliente.entrar(sistema.chefe.email, sistema.senha)
    pagina = cliente.requisitar('/reservas/nova?' + urlencode(dados_periodo(periodo)))
    assert pagina.status == 200 and "Disponibilidade no período" in pagina.body and "Posição 1" in pagina.body
    livres = {r["recurso_id"]: r["livre"] for r in sistema.reservas.disponibilidade(sistema.token, *periodo)}
    assert livres == {recursos[0].id:False, recursos[1].id:False, recursos[2].id:False, recursos[3].id:True}
    assert len(sistema.reservas.listar(sistema.token)) == 1


def test_horario_de_brasilia_e_usuario_da_sessao_na_confirmacao(sistema, recursos, cliente, portador, periodo):
    usuario, _ = portador
    cliente.entrar(usuario.email, sistema.senha)
    form = cliente.requisitar('/reservas/nova')
    resposta = cliente.requisitar('/reservas/nova', dict(dados_periodo(periodo), csrf=cliente.csrf(form),
        recurso_id=recursos[2].id, usuario_id=sistema.chefe.id))
    assert resposta.status == 303
    with psycopg.connect(sistema.url) as conn:
        dono, inicio = conn.execute('SELECT usuario_id,inicio FROM gestao_lab.reserva WHERE laboratorio_id=%s', (usuario.laboratorio_id,)).fetchone()
    assert dono == usuario.id and inicio == periodo[0]
