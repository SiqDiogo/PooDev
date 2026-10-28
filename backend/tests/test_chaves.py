from datetime import datetime, timedelta, timezone

import pytest
import psycopg
from types import SimpleNamespace

from gestao_lab.aplicacao.servicos import DadosCadastro
from gestao_lab.dominio.erros import AcessoNegado, CadastroDuplicado, DadosInvalidos
from gestao_lab.dominio.usuarios import Perfil

pytestmark = pytest.mark.integracao


def reservar(sistema, token, recurso_id, inicio, fim):
    return SimpleNamespace(id=sistema.reservas.reservar(token, recurso_id=recurso_id, inicio=inicio, fim=fim))


def copia(sistema, destino_id, *, codigo="C1", designada_para=None):
    return sistema.chaves.cadastrar(sistema.token, codigo_copia=f'{codigo}-{sistema.chave}',
                                  destino_id=destino_id, designada_para=designada_para)


def test_copias_multiplas_compartilhadas_designadas_e_codigo_unico(sistema, recursos, portador):
    usuario, token = portador
    a = copia(sistema, recursos[0].id)
    b = copia(sistema, recursos[0].id, codigo="C2", designada_para=usuario.id)
    assert a.estado == "DISPONIVEL" and b.designada_para == usuario.id
    assert {c.id for c in sistema.chaves.painel(token)[0]} == {a.id, b.id}
    with pytest.raises(CadastroDuplicado, match="código de cópia"):
        copia(sistema, recursos[1].id)
    sistema.chaves.designar(sistema.token, a.id, usuario.id)
    assert sistema.chaves.consultar_gestao(sistema.token, a.id)[0].designada_para == usuario.id
    sistema.chaves.designar(sistema.token, a.id)
    assert sistema.chaves.consultar_gestao(sistema.token, a.id)[0].designada_para is None


def test_professor_controla_somente_chaves_do_destino_sob_sua_responsabilidade(sistema, recursos, dados_professor, periodo):
    professor = sistema.cadastro.cadastrar(sistema.token, Perfil.PROFESSOR, dados_professor)
    token = sistema.auth.entrar(professor.email, sistema.senha)
    sala = sistema.recursos.cadastrar_sala(sistema.token, nome="Sala do Professor", identificacao="SP", localizacao="Bloco P", capacidade=3, responsavel_id=professor.id)
    bancada = sistema.recursos.cadastrar_bancada(sistema.token, nome="Bancada do Chefe", numero_identificacao="BC", sala_id=sala.id)
    chave = sistema.chaves.cadastrar(token, codigo_copia=f'PROF-{sistema.chave}', destino_id=sala.id)
    assert chave.destino.responsavel_id == professor.id
    reserva = reservar(sistema, token, sala.id, *periodo)
    emprestimo = sistema.chaves.retirar(token, chave.id, reserva.id)
    sistema.chaves.devolver(token, emprestimo)
    for destino in (recursos[0].id, bancada.id):
        with pytest.raises(AcessoNegado):
            sistema.chaves.cadastrar(token, codigo_copia="NÃO PERMITIDA", destino_id=destino)
    assert len(sistema.chaves.dados_cadastro(token)[0]) == 1


def test_aluno_consulta_mas_nao_cadastra_designa_entrega_recebe_ou_altera_ocorrencia(sistema, recursos, portador, periodo):
    usuario, token = portador
    chave = copia(sistema, recursos[0].id)
    reserva = reservar(sistema, token, recursos[2].id, *periodo)
    with pytest.raises(AcessoNegado):
        sistema.chaves.cadastrar(token, codigo_copia="INVÁLIDA", destino_id=recursos[0].id)
    with pytest.raises(AcessoNegado):
        sistema.chaves.dados_cadastro(token)
    with pytest.raises(AcessoNegado):
        sistema.chaves.designar(token, chave.id, usuario.id)
    with pytest.raises(AcessoNegado):
        sistema.chaves.retirar(token, chave.id, reserva.id)
    emprestimo = sistema.chaves.retirar(sistema.token, chave.id, reserva.id)
    with pytest.raises(AcessoNegado):
        sistema.chaves.devolver(token, emprestimo)
    with pytest.raises(AcessoNegado):
        sistema.chaves.registrar_ocorrencia(token, chave.id, condicao="EXTRAVIADA", descricao="Teste")


def test_retirada_vincula_reserva_e_local_e_rejeita_emprestimo_e_designacao_duplicados(sistema, recursos, portador, periodo):
    usuario, token = portador
    chave = copia(sistema, recursos[0].id)
    reserva = reservar(sistema, token, recursos[2].id, *periodo)
    opcoes = sistema.chaves.opcoes_retirada(sistema.token, chave.id)[1]
    assert [r.id for r in opcoes] == [reserva.id]
    emprestimo = sistema.chaves.retirar(sistema.token, chave.id, reserva.id)
    atual = sistema.chaves.consultar_gestao(sistema.token, chave.id)[0]
    assert atual.estado == "EM_USO" and atual.portador_id == usuario.id
    with pytest.raises(DadosInvalidos, match="retirada em aberto"):
        sistema.chaves.retirar(sistema.token, chave.id, reserva.id)
    with pytest.raises(DadosInvalidos, match="Devolva"):
        sistema.chaves.designar(sistema.token, chave.id, usuario.id)
    sistema.chaves.devolver(sistema.token, emprestimo)
    assert sistema.chaves.consultar_gestao(sistema.token, chave.id)[0].estado == "DISPONIVEL"
    with pytest.raises(DadosInvalidos, match="devolvido"):
        sistema.chaves.devolver(sistema.token, emprestimo)


def test_chave_bancada_nao_autoriza_equipamento_direto_e_designacao_a_outro_aluno_bloqueia(sistema, recursos, portador, periodo):
    usuario, token = portador
    chave = copia(sistema, recursos[1].id)
    reserva = reservar(sistema, token, recursos[3].id, *periodo)
    assert sistema.chaves.opcoes_retirada(sistema.token, chave.id)[1] == []
    with pytest.raises(AcessoNegado):
        sistema.chaves.retirar(sistema.token, chave.id, reserva.id)
    sala = copia(sistema, recursos[0].id, codigo="RESTRITA", designada_para=sistema.chefe.id)
    with pytest.raises(AcessoNegado):
        sistema.chaves.retirar(sistema.token, sala.id, reserva.id)
    assert sala.id not in {c.id for c in sistema.chaves.painel(token)[0]}


def test_cancelamento_e_expiracao_nao_devolvem_chave_e_nao_autorizam_nova_retirada(sistema, recursos, portador, periodo):
    _, token = portador
    chave = copia(sistema, recursos[0].id)
    reserva = reservar(sistema, token, recursos[2].id, *periodo)
    emprestimo = sistema.chaves.retirar(sistema.token, chave.id, reserva.id)
    sistema.reservas.cancelar(token, reserva_id=reserva.id, motivo="Cancelamento de teste")
    assert sistema.chaves.consultar_gestao(sistema.token, chave.id)[0].portador_id == portador[0].id
    sistema.chaves.devolver(sistema.token, emprestimo)
    with pytest.raises(AcessoNegado):
        sistema.chaves.retirar(sistema.token, chave.id, reserva.id)
    passado = datetime.now(timezone.utc) - timedelta(days=1)
    with sistema.transacao() as tx:
        expirada = tx.reservas.criar(portador[0].id, recursos[2].id, passado, passado + timedelta(hours=1))
    with pytest.raises(AcessoNegado):
        sistema.chaves.retirar(sistema.token, chave.id, expirada)


def test_extravio_preserva_posse_e_devolucao_nao_oculta_condicao(sistema, recursos, portador, periodo):
    usuario, token = portador
    chave = copia(sistema, recursos[0].id)
    reserva = reservar(sistema, token, recursos[2].id, *periodo)
    emprestimo = sistema.chaves.retirar(sistema.token, chave.id, reserva.id)
    sistema.chaves.registrar_ocorrencia(sistema.token, chave.id, condicao="EXTRAVIADA", descricao="Cópia não localizada")
    atual = sistema.chaves.consultar_gestao(sistema.token, chave.id)[0]
    assert atual.estado == "EXTRAVIADA" and atual.portador_id == usuario.id
    assert any(e.descricao.startswith("Ocorrência de chave") for e in sistema.historico.listar(token))
    sistema.chaves.devolver(sistema.token, emprestimo)
    assert sistema.chaves.consultar_gestao(sistema.token, chave.id)[0].estado == "EXTRAVIADA"
    sistema.chaves.registrar_ocorrencia(sistema.token, chave.id, condicao="OPERACIONAL", descricao="Cópia localizada e conferida")
    assert sistema.chaves.consultar_gestao(sistema.token, chave.id)[0].estado == "DISPONIVEL"


@pytest.mark.parametrize("condicao,descricao", [("EM_USO", "Inválido"), ("EXTRAVIADA", " "), (None, "Teste")])
def test_ocorrencia_exige_condicao_e_descricao_validas(sistema, recursos, condicao, descricao):
    chave = copia(sistema, recursos[0].id)
    with pytest.raises(DadosInvalidos):
        sistema.chaves.registrar_ocorrencia(sistema.token, chave.id, condicao=condicao, descricao=descricao)
    assert sistema.chaves.consultar_gestao(sistema.token, chave.id)[0].estado == "DISPONIVEL"


def test_copia_indisponivel_e_destinatario_inativo_nao_podem_ser_usados(sistema, recursos, portador, periodo):
    usuario, token = portador
    chave = copia(sistema, recursos[0].id)
    reserva = reservar(sistema, token, recursos[2].id, *periodo)
    sistema.chaves.registrar_ocorrencia(sistema.token, chave.id, condicao="INDISPONIVEL", descricao="Chave danificada")
    with pytest.raises(DadosInvalidos, match="indisponível"):
        sistema.chaves.retirar(sistema.token, chave.id, reserva.id)
    sistema.cadastro.remover(sistema.token, usuario.id)
    with pytest.raises(DadosInvalidos, match="ativo"):
        sistema.chaves.designar(sistema.token, chave.id, usuario.id)


def test_devolucao_e_permitida_apos_desativacao_do_portador(sistema, recursos, portador, periodo):
    usuario, token = portador
    chave = copia(sistema, recursos[0].id)
    reserva = reservar(sistema, token, recursos[2].id, *periodo)
    emprestimo = sistema.chaves.retirar(sistema.token, chave.id, reserva.id)
    sistema.cadastro.remover(sistema.token, usuario.id)
    sistema.chaves.devolver(sistema.token, emprestimo)
    assert sistema.chaves.consultar_gestao(sistema.token, chave.id)[0].estado == "DISPONIVEL"


def test_chaves_historico_e_operacoes_respeitam_isolamento_entre_laboratorios(sistema, recursos, periodo):
    chave = copia(sistema, recursos[0].id)
    reserva = reservar(sistema, sistema.token, recursos[2].id, *periodo)
    emprestimo = sistema.chaves.retirar(sistema.token, chave.id, reserva.id)
    chefe = sistema.inicial.criar_chefe("Outro laboratório", "Outro local", DadosCadastro(
        nome="Outro chefe", email=f"outro.chaves.{sistema.chave}@example.org", senha=sistema.senha, programa_pos="Programa"))
    token = sistema.auth.entrar(chefe.email, sistema.senha)
    assert sistema.chaves.painel(token) == ([], [], [])
    assert sistema.historico.listar(token) == []
    for operacao in [lambda: sistema.chaves.designar(token, chave.id),
                     lambda: sistema.chaves.retirar(token, chave.id, reserva.id),
                     lambda: sistema.chaves.devolver(token, emprestimo)]:
        with pytest.raises(DadosInvalidos, match="neste laboratório"):
            operacao()


def test_fim_do_periodo_nao_encerra_emprestimo(sistema, recursos):
    chave = copia(sistema, recursos[0].id)
    with sistema.transacao() as tx:
        agora = datetime.now(timezone.utc)
        reserva = tx.reservas.criar(sistema.chefe.id, recursos[2].id, agora - timedelta(minutes=1), agora + timedelta(seconds=2))
        emprestimo = tx.chaves.retirar(sistema.chefe.id, reserva, chave.id, sistema.chefe.id)
    with psycopg.connect(sistema.url) as conn:
        conn.execute("SELECT pg_sleep(2.1)")
    assert sistema.chaves.consultar_gestao(sistema.token, chave.id)[0].emprestimo_aberto_id == emprestimo
    sistema.chaves.devolver(sistema.token, emprestimo)


def test_reserva_de_sala_autoriza_chaves_das_bancadas_abrangidas(sistema, recursos, portador, periodo):
    _, token = portador
    sala = copia(sistema, recursos[0].id)
    bancada = copia(sistema, recursos[1].id, codigo="B1")
    reserva = reservar(sistema, token, recursos[0].id, *periodo)
    for c in (sala, bancada):
        assert [r.id for r in sistema.chaves.opcoes_retirada(sistema.token, c.id)[1]] == [reserva.id]
        sistema.chaves.retirar(sistema.token, c.id, reserva.id)
