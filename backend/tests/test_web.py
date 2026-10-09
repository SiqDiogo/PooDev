from http.cookies import SimpleCookie
from io import BytesIO
import re
from types import SimpleNamespace
from urllib.parse import urlencode, urlsplit

import pytest

from gestao_lab.aplicacao.servicos import DadosCadastro
from gestao_lab.apresentacao.web import AplicacaoWeb
from gestao_lab.dominio.usuarios import Perfil
from gestao_lab.infraestrutura.configuracao import Configuracao

pytestmark = pytest.mark.integracao


class ClienteWSGI:
    def __init__(self, app):
        self.app, self.cookies = app, {}

    def requisitar(self, caminho, dados=None, metodo=None, **cabecalhos):
        url = urlsplit(caminho)
        corpo = urlencode(dados or {}).encode()
        env = {"REQUEST_METHOD": metodo or ("POST" if dados is not None else "GET"), "PATH_INFO": url.path,
               "QUERY_STRING": url.query, "HTTP_HOST": "127.0.0.1:8000", "REMOTE_ADDR": "127.0.0.1",
               "wsgi.url_scheme": "http", "wsgi.input": BytesIO(corpo), "CONTENT_LENGTH": str(len(corpo)),
               "CONTENT_TYPE": "application/x-www-form-urlencoded",
               "HTTP_COOKIE": "; ".join(f"{k}={v}" for k, v in self.cookies.items())}
        env.update(cabecalhos)
        capturado = {}

        def iniciar(status, headers):
            capturado.update(status=int(status.split()[0]), headers=headers)
            for nome, valor in headers:
                if nome.lower() == "set-cookie":
                    for k, c in SimpleCookie(valor).items():
                        if c["max-age"] == "0":
                            self.cookies.pop(k, None)
                        else:
                            self.cookies[k] = c.value

        body = b"".join(self.app(env, iniciar)).decode()
        return SimpleNamespace(**capturado, body=body)

    @staticmethod
    def csrf(resposta):
        return re.search(r'name="csrf" value="([^"]+)"', resposta.body).group(1)

    def entrar(self, email, senha):
        form = self.requisitar("/entrar")
        return self.requisitar("/entrar", {"csrf": self.csrf(form), "email": email, "senha": senha})


@pytest.fixture
def cliente(sistema):
    config = Configuracao(sistema.url, b"segredo-de-teste-com-32-caracteres")
    return ClienteWSGI(AplicacaoWeb(sistema.auth, sistema.cadastro, config))


def test_cadastro_pelos_formularios_e_login_dos_perfis(sistema, cliente):
    assert cliente.entrar(sistema.chefe.email, sistema.senha).status == 303
    form = cliente.requisitar("/cadastros/professor")
    email_prof = f"web.prof.{sistema.chave}@example.org"
    retorno = cliente.requisitar("/cadastros/professor", {"csrf": cliente.csrf(form), "nome": "Professor da interface",
                                 "email": email_prof, "programa_pos": "Biociências", "ramal": "1111",
                                 "senha": sistema.senha, "confirmacao": sistema.senha,
                                 "laboratorio_id": "999", "ator_id": "999", "perfil": "CHEFE"})
    assert retorno.status == 303
    with sistema.transacao() as tx:
        prof = tx.usuarios.buscar_por_email(email_prof)
    assert prof.perfil == Perfil.PROFESSOR and prof.laboratorio_id == sistema.chefe.laboratorio_id
    form = cliente.requisitar("/cadastros/aluno")
    assert f'value="{prof.id}"' in form.body
    email_aluno = f"web.aluno.{sistema.chave}@example.org"
    retorno = cliente.requisitar("/cadastros/aluno", {"csrf": cliente.csrf(form), "nome": "Aluno da interface", "email": email_aluno,
                                 "matricula": sistema.chave, "tipo": "MESTRADO", "orientador_id": str(prof.id),
                                 "senha": sistema.senha, "confirmacao": sistema.senha})
    assert retorno.status == 303
    lista = cliente.requisitar("/usuarios?cadastro=ok")
    assert "Usuário cadastrado." in lista.body and email_prof in lista.body and email_aluno in lista.body
    assert sistema.senha not in lista.body and "pbkdf2_sha256" not in lista.body
    assert cliente.entrar(email_aluno, sistema.senha).status == 303
    assert "Aluno da interface" in cliente.requisitar("/").body


@pytest.mark.parametrize("rota", ["/usuarios", "/cadastros/aluno", "/cadastros/professor"])
def test_professor_nao_acessa_cadastro_nem_lista(sistema, dados_professor, cliente, rota):
    prof = sistema.cadastro.cadastrar(sistema.token, Perfil.PROFESSOR, dados_professor)
    assert cliente.entrar(prof.email, sistema.senha).status == 303
    assert cliente.requisitar(rota).status == 403


@pytest.mark.parametrize("csrf", ["", "inventado", "não-ascii"])
def test_formulario_sem_csrf_valido_nao_grava(sistema, cliente, csrf):
    cliente.entrar(sistema.chefe.email, sistema.senha)
    antes = len(sistema.cadastro.listar(sistema.token))
    r = cliente.requisitar("/cadastros/professor", {"csrf": csrf, "nome": "Pessoa"})
    assert r.status == 403 and len(sistema.cadastro.listar(sistema.token)) == antes


def test_logout_exige_post_e_revoga_token(sistema, cliente):
    cliente.entrar(sistema.chefe.email, sistema.senha)
    token = cliente.cookies["lab_sessao"]
    assert cliente.requisitar("/sair").status == 405
    assert sistema.auth.identificar(token) is not None
    form = cliente.requisitar("/")
    assert cliente.requisitar("/sair", {"csrf": cliente.csrf(form)}).status == 303
    assert "lab_sessao" not in cliente.cookies and sistema.auth.identificar(token) is None


def test_csrf_e_origem_do_login_sao_verificados(sistema, cliente):
    assert cliente.requisitar("/entrar", {"email": sistema.chefe.email, "senha": sistema.senha, "csrf": "inventado"}).status == 403
    form = cliente.requisitar("/entrar")
    r = cliente.requisitar("/entrar", {"email": sistema.chefe.email, "senha": sistema.senha, "csrf": cliente.csrf(form)}, HTTP_ORIGIN="https://outro.example.org")
    assert r.status == 403


def test_erro_de_formulario_nao_devolve_senha(sistema, cliente):
    cliente.entrar(sistema.chefe.email, sistema.senha)
    form = cliente.requisitar("/cadastros/professor")
    r = cliente.requisitar("/cadastros/professor", {"csrf": cliente.csrf(form), "nome": "Pessoa",
                          "email": "p@example.org", "programa_pos": "Programa", "senha": sistema.senha, "confirmacao": "diferente"})
    assert r.status == 400 and "diferentes" in r.body
    assert sistema.senha not in r.body


def test_dados_da_listagem_sao_escapados(sistema, cliente):
    sistema.cadastro.cadastrar(sistema.token, Perfil.PROFESSOR, DadosCadastro(
        nome="<script>alert(1)</script>", email=f"escape.{sistema.chave}@example.org", senha=sistema.senha, programa_pos="Programa"))
    cliente.entrar(sistema.chefe.email, sistema.senha)
    r = cliente.requisitar("/usuarios")
    assert "<script>alert(1)</script>" not in r.body and "&lt;script&gt;" in r.body
    assert ("Cache-Control", "no-store") in r.headers


def test_host_invalido_e_limite_de_login(sistema, cliente):
    assert cliente.requisitar("/entrar", HTTP_HOST="outro.example.org").status == 400
    for _ in range(5):
        assert cliente.entrar(sistema.chefe.email, "SenhaIncorreta2026!").status == 401
    assert cliente.entrar(sistema.chefe.email, "SenhaIncorreta2026!").status == 429


def test_cookie_tem_protecoes_e_pagina_anonima_redireciona(sistema, cliente):
    assert cliente.requisitar("/usuarios").status == 303
    r = cliente.entrar(sistema.chefe.email, sistema.senha)
    cookie = next(v for k, v in r.headers if k == "Set-Cookie" and v.startswith("lab_sessao="))
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie
