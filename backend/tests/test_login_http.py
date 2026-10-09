import http.cookiejar
import re
import threading
from dataclasses import replace
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener
from wsgiref.simple_server import make_server

import pytest

from gestao_lab.__main__ import AtendimentoLocal
from gestao_lab.apresentacao.web import AplicacaoWeb
from gestao_lab.dominio.usuarios import ChefeLaboratorio
from gestao_lab.infraestrutura.configuracao import Configuracao


class AutenticacaoDeTeste:
    def __init__(self):
        self.tentativas = 0
        self.token = "s" * 43
        self.chefe = ChefeLaboratorio(
            id=1, laboratorio_id=1, nome="Chefe de teste",
            email="chefe.a@example.org", senha_hash="x" * 64,
            programa_pos="Biologia",
        )

    def entrar(self, email, senha):
        self.tentativas += 1
        return self.token

    def identificar(self, token):
        return self.chefe if token == self.token else None

    def sair(self, token):
        pass


class ClienteHTTP:
    def __init__(self, porta):
        self.endereco = f"http://127.0.0.1:{porta}"
        self.cookies = http.cookiejar.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))

    def requisitar(self, rota, dados=None):
        corpo = urlencode(dados).encode() if dados is not None else None
        pedido = Request(self.endereco + rota, data=corpo)
        if dados is not None:
            pedido.add_header("Origin", self.endereco)
        try:
            resposta = self.opener.open(pedido, timeout=5)
        except HTTPError as erro:
            resposta = erro
        with resposta:
            return SimpleNamespace(status=resposta.code, body=resposta.read().decode(), headers=resposta.headers)

    def cookie(self, nome):
        return next((c.value for c in self.cookies if c.name == nome), "")

    @staticmethod
    def csrf(resposta):
        return re.search(r'name="csrf" value="([^"]+)"', resposta.body).group(1)


@pytest.fixture
def sistema_http():
    autenticacao = AutenticacaoDeTeste()
    servidor = make_server("127.0.0.1", 0, None, handler_class=AtendimentoLocal)
    config = Configuracao("postgresql://localhost/banco_nao_utilizado", b"a" * 32, porta=servidor.server_port)
    servidor.set_app(AplicacaoWeb(autenticacao, None, config))
    thread = threading.Thread(target=lambda: servidor.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    try:
        yield SimpleNamespace(cliente=ClienteHTTP(servidor.server_port), auth=autenticacao,
                              servidor=servidor, config=config)
    finally:
        servidor.shutdown()
        servidor.server_close()
        thread.join(timeout=2)


def enviar_login(cliente, formulario):
    return cliente.requisitar("/entrar", {"csrf": cliente.csrf(formulario),
                             "email": "chefe.a@example.org", "senha": "SenhaFicticia2026!"})


@pytest.mark.parametrize("arquivo", ["/favicon.ico", "/imagem-inexistente.png", "/manifest.webmanifest"])
def test_arquivo_inexistente_nao_invalida_login(sistema_http, arquivo):
    cliente = sistema_http.cliente
    formulario = cliente.requisitar("/entrar")
    cookie = cliente.cookie("lab_form")

    resposta = cliente.requisitar(arquivo)

    assert resposta.status == 404
    assert not resposta.headers.get("Location")
    assert not resposta.headers.get("Set-Cookie")
    assert cliente.cookie("lab_form") == cookie
    assert enviar_login(cliente, formulario).status == 200
    assert sistema_http.auth.tentativas == 1


def test_login_antigo_apos_reinicio_exibe_novo_formulario(sistema_http):
    cliente = sistema_http.cliente
    antigo = cliente.requisitar("/entrar")
    sistema_http.servidor.set_app(AplicacaoWeb(
        sistema_http.auth, None, replace(sistema_http.config, segredo_csrf=b"b" * 32)))

    resposta = enviar_login(cliente, antigo)

    assert resposta.status == 403
    assert sistema_http.auth.tentativas == 0
    assert "O formulário expirou." in resposta.body
    assert "SenhaFicticia2026!" not in resposta.body
    assert cliente.csrf(resposta) != cliente.csrf(antigo)
    assert 'value="chefe.a@example.org"' in resposta.body
    assert enviar_login(cliente, resposta).status == 200


def test_login_sem_cookie_e_rejeitado_e_pode_ser_reaberto(sistema_http):
    cliente = sistema_http.cliente
    formulario = cliente.requisitar("/entrar")
    cliente.cookies.clear()

    resposta = enviar_login(cliente, formulario)

    assert resposta.status == 403
    assert sistema_http.auth.tentativas == 0
    assert "SenhaFicticia2026!" not in resposta.body
    assert cliente.csrf(resposta) == cliente.cookie("lab_form")
    assert enviar_login(cliente, resposta).status == 200
