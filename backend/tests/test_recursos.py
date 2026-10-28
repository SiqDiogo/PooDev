import pytest

from gestao_lab.aplicacao.servicos import DadosCadastro
from gestao_lab.dominio.erros import AcessoNegado, CadastroDuplicado, DadosInvalidos
from gestao_lab.dominio.usuarios import Perfil

pytestmark = pytest.mark.integracao


def test_recursos_preservam_hierarquia_e_localizacao(sistema, recursos):
    sala, bancada, equipamento, direto = recursos
    salas, bancadas, equipamentos = sistema.recursos.listar(sistema.token)
    assert {r.id for r in salas[0].recursos_afetados()} == {sala.id, bancada.id, equipamento.id, direto.id}
    assert {r.id for r in bancadas[0].recursos_afetados()} == {bancada.id, equipamento.id}
    assert salas[0].localizacao == "Bloco A, sala 1"
    assert {e.id: e.complemento_local for e in equipamentos} == {equipamento.id: "Posição 1", direto.id: "Armário 2"}


def test_patrimonio_repetido_e_rejeitado_sem_recurso_incompleto(sistema, recursos):
    sala, bancada, equipamento, _ = recursos
    with pytest.raises(CadastroDuplicado):
        sistema.recursos.cadastrar_equipamento(sistema.token, nome="Repetido", numero_patrimonio=equipamento.numero_patrimonio.lower(),
            complemento_local="Outra posição", bancada_id=bancada.id)
    assert len(sistema.recursos.listar(sistema.token)[2]) == 2


def test_recurso_rejeita_sala_e_bancada_de_outro_laboratorio(sistema, recursos):
    sala, bancada, _, _ = recursos
    outro = sistema.inicial.criar_chefe("Outro laboratório", "Bloco B", DadosCadastro(
        nome="Outro chefe", email=f"outro.recursos.{sistema.chave}@example.org", senha=sistema.senha, programa_pos="Programa"))
    token = sistema.auth.entrar(outro.email, sistema.senha)
    with pytest.raises(DadosInvalidos, match="neste laboratório"):
        sistema.recursos.cadastrar_bancada(token, nome="Inválida", numero_identificacao="X", sala_id=sala.id)
    with pytest.raises(DadosInvalidos, match="neste laboratório"):
        sistema.recursos.cadastrar_equipamento(token, nome="Inválido", numero_patrimonio=f"X-{sistema.chave}",
            complemento_local="X", bancada_id=bancada.id)
    assert sistema.recursos.listar(token) == ([], [], [])


def test_professor_nao_pode_cadastrar_recursos(sistema, dados_professor):
    professor = sistema.cadastro.cadastrar(sistema.token, Perfil.PROFESSOR, dados_professor)
    token = sistema.auth.entrar(professor.email, sistema.senha)
    with pytest.raises(AcessoNegado):
        sistema.recursos.cadastrar_sala(token, nome="Sala", identificacao="S", localizacao="Bloco A", capacidade=10)


def test_responsavel_deve_ser_professor_ativo_do_laboratorio(sistema, dados_professor):
    professor = sistema.cadastro.cadastrar(sistema.token, Perfil.PROFESSOR, dados_professor)
    sistema.cadastro.remover(sistema.token, professor.id)
    with pytest.raises(DadosInvalidos, match="Professor ativo"):
        sistema.recursos.cadastrar_sala(sistema.token, nome="Sala", identificacao="S", localizacao="Bloco A", capacidade=10,
            responsavel_id=professor.id)
