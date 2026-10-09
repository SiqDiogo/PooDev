from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from gestao_lab.aplicacao.seguranca import ProtecaoSenha, TokensSessao
from gestao_lab.aplicacao.servicos import DadosCadastro
from gestao_lab.apresentacao.csrf import ProtecaoCSRF
from gestao_lab.dominio.erros import AcessoNegado, DadosInvalidos
from gestao_lab.dominio.repositorios import Sessao
from gestao_lab.dominio.usuarios import Aluno, ChefeLaboratorio, Perfil, Professor, TipoAluno, Usuario


def professor(**alteracoes):
    dados = dict(id=1, nome="  Maria Silva  ", email=" MARIA@EXAMPLE.ORG ", laboratorio_id=1,
                 senha_hash="hash-que-nao-deve-aparecer", programa_pos="Biociências")
    dados.update(alteracoes)
    return Professor(**dados)


def aluno(**alteracoes):
    dados = dict(nome="João", email="joao@example.org", laboratorio_id=1, senha_hash="hash",
                 matricula="2026001", tipo=TipoAluno.GRADUACAO, orientador_id=1)
    dados.update(alteracoes)
    return Aluno(**dados)


def test_usuario_e_abstrato():
    with pytest.raises(TypeError):
        Usuario(nome="Pessoa", email="p@example.org", laboratorio_id=1, senha_hash="hash")


def test_normalizacao_e_encapsulamento():
    p = professor()
    assert p.nome == "Maria Silva" and p.email == "maria@example.org"
    assert "hash-que-nao-deve-aparecer" not in repr(p)
    with pytest.raises(FrozenInstanceError):
        p.laboratorio_id = 2


@pytest.mark.parametrize("email", ["sem-arroba", "p@dominio", "p @example.org", "a" * 255 + "@example.org"])
def test_email_invalido(email):
    with pytest.raises(DadosInvalidos):
        professor(email=email)


@pytest.mark.parametrize("dados", [{"nome": " "}, {"programa_pos": ""}, {"ramal": "x" * 41}, {"laboratorio_id": 0}])
def test_professor_exige_campos_validos(dados):
    with pytest.raises(DadosInvalidos):
        professor(**dados)


def test_chefe_e_professor_e_tem_permissao_propria():
    chefe = ChefeLaboratorio(nome="Ana", email="ana@example.org", laboratorio_id=1,
                            senha_hash="hash", programa_pos="Biociências")
    assert isinstance(chefe, Professor) and isinstance(chefe, Usuario)
    assert chefe.perfil == Perfil.CHEFE
    chefe.exigir_permissao_cadastro()
    for usuario in [professor(), aluno()]:
        with pytest.raises(AcessoNegado):
            usuario.exigir_permissao_cadastro()


@pytest.mark.parametrize("dados", [{"matricula": ""}, {"tipo": "INVALIDO"}, {"orientador_id": 0}])
def test_aluno_exige_dados_academicos(dados):
    with pytest.raises(DadosInvalidos):
        aluno(**dados)


@pytest.mark.parametrize("orientador", [None, professor(laboratorio_id=2), professor(ativo=False), professor(id=2), aluno()])
def test_orientador_incompativel(orientador):
    with pytest.raises(DadosInvalidos):
        aluno().validar_orientador(orientador)


def test_orientador_valido():
    aluno().validar_orientador(professor())


def test_hash_tem_salt_individual_e_verifica_sem_guardar_senha():
    protecao = ProtecaoSenha()
    senha = "SenhaFicticiaDeTeste2026!"
    primeiro, segundo = protecao.gerar_hash(senha), protecao.gerar_hash(senha)
    assert primeiro != segundo and senha not in primeiro
    assert protecao.verificar(senha, primeiro)
    assert not protecao.verificar("SenhaIncorreta2026!", primeiro)
    assert not protecao.verificar(senha, "hash-da-carga-ficticia")
    assert "SenhaFicticiaDeTeste2026!" not in repr(DadosCadastro(nome="Pessoa", email="p@example.org", senha=senha))


@pytest.mark.parametrize("senha", ["curta", "x" * 129])
def test_senha_fora_do_limite(senha):
    with pytest.raises(DadosInvalidos):
        ProtecaoSenha().gerar_hash(senha)


def test_token_nao_e_guardado_em_texto_no_banco():
    token = TokensSessao.gerar()
    assert TokensSessao.formato_valido(token) and len(TokensSessao.resumir(token)) == 32
    assert not TokensSessao.formato_valido("token-manipulado")


def test_sessao_expira_e_revoga():
    agora = datetime.now(timezone.utc)
    assert Sessao(1, agora + timedelta(hours=1), None).esta_valida(agora)
    assert not Sessao(1, agora, None).esta_valida(agora)
    assert not Sessao(1, agora + timedelta(hours=1), agora).esta_valida(agora)


def test_csrf_rejeita_alteracao_e_outra_sessao():
    csrf = ProtecaoCSRF(b"segredo-de-teste-com-32-caracteres")
    desafio = csrf.emitir_login()
    assert csrf.validar_login(desafio, desafio)
    assert not csrf.validar_login(desafio, desafio + "a")
    assert not csrf.validar_login("", "")
    token = TokensSessao.gerar()
    assert csrf.validar_sessao(token, csrf.para_sessao(token))
    assert not csrf.validar_sessao(TokensSessao.gerar(), csrf.para_sessao(token))


def test_csrf_login_expirado(monkeypatch):
    import gestao_lab.apresentacao.csrf as modulo
    monkeypatch.setattr(modulo.time, "time", lambda: 1000)
    csrf = ProtecaoCSRF(b"segredo-de-teste-com-32-caracteres")
    desafio = csrf.emitir_login()
    monkeypatch.setattr(modulo.time, "time", lambda: 1901)
    assert not csrf.validar_login(desafio, desafio)
