from dataclasses import replace

import psycopg
import pytest

from gestao_lab.aplicacao.servicos import DadosCadastro
from gestao_lab.dominio.erros import AcessoNegado, CadastroDuplicado, CredenciaisInvalidas, DadosInvalidos
from gestao_lab.dominio.usuarios import Aluno, ChefeLaboratorio, Perfil, Professor

pytestmark = pytest.mark.integracao


def dados_aluno(s, **alteracoes):
    dados = dict(nome="Aluno de teste", email=f"aluno.{s.chave}@example.org", senha=s.senha,
                 matricula=s.chave, orientador_id=s.chefe.id, tipo="GRADUACAO")
    dados.update(alteracoes)
    return DadosCadastro(**dados)


def test_configuracao_cria_laboratorio_usuario_professor_e_chefe(sistema):
    with sistema.transacao() as tx:
        chefe = tx.usuarios.buscar_por_id(sistema.chefe.id)
        assert isinstance(chefe, ChefeLaboratorio) and isinstance(chefe, Professor)
        assert tx.laboratorios.esta_ativo(chefe.laboratorio_id)
    assert sistema.auth.identificar(sistema.token).id == sistema.chefe.id


def test_professor_e_aluno_podem_entrar_com_os_dados_cadastrados(sistema, dados_professor):
    professor = sistema.cadastro.cadastrar(sistema.token, Perfil.PROFESSOR, dados_professor)
    aluno = sistema.cadastro.cadastrar(sistema.token, Perfil.ALUNO, dados_aluno(sistema, orientador_id=professor.id))
    assert isinstance(professor, Professor) and not isinstance(professor, ChefeLaboratorio)
    assert isinstance(aluno, Aluno)
    for usuario in [professor, aluno]:
        token = sistema.auth.entrar(usuario.email, sistema.senha)
        atual = sistema.auth.identificar(token)
        assert type(atual) is type(usuario) and atual.laboratorio_id == sistema.chefe.laboratorio_id
        with pytest.raises(AcessoNegado):
            sistema.cadastro.cadastrar(token, Perfil.PROFESSOR, replace(dados_professor, email="proibido@example.org"))


def test_cadastro_normaliza_email_e_registra_ator(sistema, dados_professor):
    novo = sistema.cadastro.cadastrar(sistema.token, Perfil.PROFESSOR, replace(dados_professor, email=f" NOVO.{sistema.chave}@EXAMPLE.ORG "))
    assert novo.email == f"novo.{sistema.chave}@example.org"
    with psycopg.connect(sistema.url) as conn:
        ator = conn.execute("SELECT ator_id FROM gestao_lab.historico_uso WHERE tabela='usuario' AND registro_id=%s ORDER BY id DESC LIMIT 1", (str(novo.id),)).fetchone()[0]
        assert ator == sistema.chefe.id


def test_email_duplicado_nao_deixa_novo_usuario(sistema, dados_professor):
    sistema.cadastro.cadastrar(sistema.token, Perfil.PROFESSOR, dados_professor)
    antes = len(sistema.cadastro.listar(sistema.token))
    with pytest.raises(CadastroDuplicado):
        sistema.cadastro.cadastrar(sistema.token, Perfil.PROFESSOR, replace(dados_professor, email=dados_professor.email.upper()))
    assert len(sistema.cadastro.listar(sistema.token)) == antes


def test_matricula_duplicada_desfaz_a_insercao_da_base(sistema):
    primeiro = dados_aluno(sistema)
    sistema.cadastro.cadastrar(sistema.token, Perfil.ALUNO, primeiro)
    segundo = replace(primeiro, email=f"outro.{sistema.chave}@example.org")
    with pytest.raises(CadastroDuplicado):
        sistema.cadastro.cadastrar(sistema.token, Perfil.ALUNO, segundo)
    with sistema.transacao() as tx:
        assert tx.usuarios.buscar_por_email(segundo.email) is None


def test_orientador_de_outro_laboratorio_e_rejeitado(sistema):
    outro = sistema.inicial.criar_chefe("Outro laboratório", "Outra sala", DadosCadastro(
        nome="Outro Chefe", email=f"outro.chefe.{sistema.chave}@example.org", senha=sistema.senha, programa_pos="Outro programa"))
    with pytest.raises(DadosInvalidos):
        sistema.cadastro.cadastrar(sistema.token, Perfil.ALUNO, dados_aluno(sistema, orientador_id=outro.id))
    lista = sistema.cadastro.listar(sistema.token)
    assert all(u.laboratorio_id == sistema.chefe.laboratorio_id for u in lista)
    assert outro.id not in {u.id for u in lista}


def test_segundo_chefe_na_mesma_rota_nao_e_permitido(sistema, dados_professor):
    with pytest.raises(DadosInvalidos, match="único Chefe"):
        sistema.cadastro.cadastrar(sistema.token, Perfil.CHEFE, dados_professor)


def test_configuracao_inicial_duplicada_desfaz_novo_laboratorio(sistema):
    with psycopg.connect(sistema.url) as conn:
        antes = conn.execute("SELECT count(*) FROM gestao_lab.laboratorio").fetchone()[0]
    with pytest.raises(CadastroDuplicado):
        sistema.inicial.criar_chefe("Laboratório inválido", "Sala", DadosCadastro(
            nome="Pessoa", email=sistema.chefe.email, senha=sistema.senha, programa_pos="Programa"))
    with psycopg.connect(sistema.url) as conn:
        assert conn.execute("SELECT count(*) FROM gestao_lab.laboratorio").fetchone()[0] == antes


def test_credenciais_invalidas_nao_criam_sessao(sistema):
    for email, senha in [(sistema.chefe.email, "SenhaIncorreta2026!"), ("inexistente@example.org", sistema.senha)]:
        with pytest.raises(CredenciaisInvalidas, match="E-mail ou senha inválidos"):
            sistema.auth.entrar(email, senha)


def test_sair_revoga_sessao_e_cadastro(sistema, dados_professor):
    sistema.auth.sair(sistema.token)
    assert sistema.auth.identificar(sistema.token) is None
    with pytest.raises(AcessoNegado):
        sistema.cadastro.cadastrar(sistema.token, Perfil.PROFESSOR, dados_professor)


def test_sessao_expirada_e_rejeitada(sistema):
    with psycopg.connect(sistema.url) as conn:
        conn.execute("UPDATE gestao_lab.sessao_usuario SET criado_em=clock_timestamp()-interval '2 hours', expira_em=clock_timestamp()-interval '1 hour' WHERE usuario_id=%s", (sistema.chefe.id,))
    assert sistema.auth.identificar(sistema.token) is None


@pytest.mark.parametrize("alvo", ["usuario", "laboratorio"])
def test_inativacao_bloqueia_login_e_sessao(sistema, alvo):
    with sistema.transacao() as tx:
        tx.contexto(None, "Inativação no banco de testes")
        if alvo == "usuario":
            tx._conexao.execute("UPDATE gestao_lab.usuario SET ativo=false WHERE id=%s", (sistema.chefe.id,))
        else:
            tx._conexao.execute("UPDATE gestao_lab.laboratorio SET ativo=false WHERE id=%s", (sistema.chefe.laboratorio_id,))
    assert sistema.auth.identificar(sistema.token) is None
    with pytest.raises(CredenciaisInvalidas):
        sistema.auth.entrar(sistema.chefe.email, sistema.senha)


def test_redefinicao_local_revoga_sessoes_e_troca_credencial(sistema):
    nova = "OutraSenhaFicticia2026!"
    sistema.inicial.definir_senha(sistema.chefe.email, nova)
    assert sistema.auth.identificar(sistema.token) is None
    with pytest.raises(CredenciaisInvalidas):
        sistema.auth.entrar(sistema.chefe.email, sistema.senha)
    assert sistema.auth.identificar(sistema.auth.entrar(sistema.chefe.email, nova)).id == sistema.chefe.id


def test_token_no_banco_tem_apenas_resumo(sistema):
    with psycopg.connect(sistema.url) as conn:
        resumo = conn.execute("SELECT token_hash FROM gestao_lab.sessao_usuario WHERE usuario_id=%s", (sistema.chefe.id,)).fetchone()[0]
        assert len(resumo) == 32 and sistema.token.encode() != bytes(resumo)


def test_falha_adiada_no_commit_desfaz_usuario_incompleto(sistema):
    email = f"incompleto.{sistema.chave}@example.org"
    with pytest.raises(DadosInvalidos):
        with sistema.transacao() as tx:
            tx.contexto(sistema.chefe.id, "Verificação de transação incompleta")
            tx._conexao.execute("""
                INSERT INTO gestao_lab.usuario(laboratorio_id, nome, email, senha_hash)
                VALUES (%s, %s, %s, %s)
            """, (sistema.chefe.laboratorio_id, "Usuário incompleto", email, sistema.chefe.senha_hash))
            # O banco só detecta a ausência de Aluno ou Professor no COMMIT.
    with sistema.transacao() as tx:
        assert tx.usuarios.buscar_por_email(email) is None
