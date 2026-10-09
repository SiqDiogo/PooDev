from dataclasses import dataclass, field
from http import HTTPStatus
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import logging
import time

from . import paginas
from .csrf import ProtecaoCSRF
from ..aplicacao.servicos import DadosCadastro
from ..dominio.erros import AcessoNegado, CredenciaisInvalidas, DadosInvalidos, ErroAplicacao, FalhaPersistencia
from ..dominio.usuarios import Perfil, Professor


@dataclass
class Resposta:
    corpo: str | bytes = ""
    status: int = 200
    headers: list[tuple[str, str]] = field(default_factory=list)


class LimiteLogin:
    def __init__(self):
        self._falhas = {}

    def bloqueado(self, chave):
        agora = time.monotonic()
        # A janela é local ao processo e evita crescimento indefinido do mapa.
        self._falhas = {k: [t for t in v if agora - t < 900] for k, v in self._falhas.items() if any(agora - t < 900 for t in v)}
        return len(self._falhas.get(chave, [])) >= 5

    def falhou(self, chave):
        self._falhas.setdefault(chave, []).append(time.monotonic())

    def limpar(self, chave):
        self._falhas.pop(chave, None)


class AplicacaoWeb:
    def __init__(self, autenticacao, cadastro, configuracao):
        self._autenticacao = autenticacao
        self._cadastro = cadastro
        self._configuracao = configuracao
        self._csrf = ProtecaoCSRF(configuracao.segredo_csrf)
        self._limite = LimiteLogin()

    def __call__(self, environ, start_response):
        try:
            resposta = self._rotear(environ)
        except AcessoNegado as erro:
            resposta = Resposta(paginas.layout("Acesso restrito", paginas.aviso(str(erro), True)), 403)
        except DadosInvalidos as erro:
            resposta = Resposta(paginas.layout("Confira os dados", paginas.aviso(str(erro), True)), 400)
        except FalhaPersistencia as erro:
            resposta = Resposta(paginas.layout("Serviço indisponível", paginas.aviso(str(erro), True)), 503)
        except Exception as erro:
            # Não imprimir os argumentos da exceção: podem incluir dados da conexão.
            logging.getLogger(__name__).error("Falha no atendimento HTTP: %s", type(erro).__name__)
            resposta = Resposta(paginas.layout("Não foi possível continuar", paginas.aviso("Tente novamente mais tarde.", True)), 500)
        corpo = resposta.corpo.encode("utf-8") if isinstance(resposta.corpo, str) else resposta.corpo
        headers = [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(corpo))),
                   ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                   ("X-Frame-Options", "DENY"), ("Referrer-Policy", "same-origin"),
                   ("Content-Security-Policy", "default-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")]
        if any(k.lower() == "content-type" for k, _ in resposta.headers):
            headers = [(k, v) for k, v in headers if k != "Content-Type"]
        start_response(f"{resposta.status} {HTTPStatus(resposta.status).phrase}", headers + resposta.headers)
        return [corpo]

    @staticmethod
    def _cookie(nome, valor, apagar=False):
        cookie = SimpleCookie()
        cookie[nome] = valor
        cookie[nome]["path"] = "/"
        cookie[nome]["httponly"] = True
        cookie[nome]["samesite"] = "Strict"
        if apagar:
            cookie[nome]["max-age"] = 0
        return "Set-Cookie", cookie[nome].OutputString()

    def _login(self, mensagem="", email="", status=200):
        desafio = self._csrf.emitir_login()
        return Resposta(paginas.login(desafio, mensagem, email), status, [self._cookie("lab_form", desafio)])

    @staticmethod
    def _redirecionar(destino, headers=None):
        return Resposta(status=303, headers=[("Location", destino)] + (headers or []))

    @staticmethod
    def _ler_formulario(environ):
        try:
            tamanho = int(environ.get("CONTENT_LENGTH") or "0")
        except ValueError as erro:
            raise DadosInvalidos("Formulário inválido.") from erro
        if not 0 < tamanho <= 16384 or environ.get("CONTENT_TYPE", "").split(";")[0] != "application/x-www-form-urlencoded":
            raise DadosInvalidos("Formulário inválido ou muito grande.")
        try:
            campos = parse_qs(environ["wsgi.input"].read(tamanho).decode("utf-8"), keep_blank_values=True, max_num_fields=20)
        except (ValueError, UnicodeError) as erro:
            raise DadosInvalidos("Formulário inválido.") from erro
        if any(len(valores) != 1 for valores in campos.values()):
            raise DadosInvalidos("O formulário contém campos duplicados.")
        return {k: v[0] for k, v in campos.items()}

    def _rotear(self, environ):
        porta = self._configuracao.porta
        host = environ.get("HTTP_HOST", "")
        if host not in {f"127.0.0.1:{porta}", f"localhost:{porta}"}:
            raise DadosInvalidos("Endereço de acesso inválido.")
        metodo = environ.get("REQUEST_METHOD", "GET")
        rota = environ.get("PATH_INFO", "/")
        if metodo not in {"GET", "POST"}:
            return Resposta("Método não permitido.", 405, [("Allow", "GET, POST")])
        if metodo == "POST":
            origem = environ.get("HTTP_ORIGIN") or environ.get("HTTP_REFERER")
            if origem:
                try:
                    origem_url = urlsplit(origem)
                except ValueError as erro:
                    raise AcessoNegado("Endereço de origem inválido.") from erro
                if (origem_url.scheme, origem_url.netloc) != (environ.get("wsgi.url_scheme", "http"), host):
                    raise AcessoNegado("Abra o formulário neste endereço para continuar.")
        try:
            cookies = SimpleCookie(environ.get("HTTP_COOKIE", ""))
            token = cookies["lab_sessao"].value if "lab_sessao" in cookies else ""
        except CookieError:
            token, cookies = "", SimpleCookie()
        if rota == "/estilo.css" and metodo == "GET":
            return Resposta((Path(__file__).parent / "estilo.css").read_bytes(), headers=[("Content-Type", "text/css; charset=utf-8")])
        if rota == "/entrar":
            if metodo == "GET":
                return self._login()
            campos = self._ler_formulario(environ)
            desafio = cookies["lab_form"].value if "lab_form" in cookies else ""
            if not self._csrf.validar_login(desafio, campos.get("csrf", "")):
                return self._login("O formulário expirou. Tente entrar novamente.",
                                   email=campos.get("email", ""), status=403)
            chave = (environ.get("REMOTE_ADDR", ""), campos.get("email", "").strip().lower())
            if self._limite.bloqueado(chave):
                resposta = self._login("Muitas tentativas. Aguarde 15 minutos para tentar novamente.", status=429)
                resposta.headers.append(("Retry-After", "900"))
                return resposta
            try:
                novo_token = self._autenticacao.entrar(campos.get("email", ""), campos.get("senha", ""))
            except CredenciaisInvalidas as erro:
                self._limite.falhou(chave)
                return self._login(str(erro), campos.get("email", ""), 401)
            self._limite.limpar(chave)
            if token:
                self._autenticacao.sair(token)
            return self._redirecionar("/", [self._cookie("lab_sessao", novo_token), self._cookie("lab_form", "", True)])
        # Arquivos ausentes, como favicon.ico, não devem abrir outro formulário.
        # O redirecionamento anterior trocava o cookie da página de login aberta.
        if rota not in {"/", "/usuarios", "/cadastros/aluno", "/cadastros/professor", "/sair"}:
            return Resposta(paginas.layout("Página não encontrada", '<p><a href="/">Voltar ao início</a></p>'), 404)
        usuario = self._autenticacao.identificar(token)
        if usuario is None:
            return self._redirecionar("/entrar", [self._cookie("lab_sessao", "", True)])
        csrf = self._csrf.para_sessao(token)
        if metodo == "POST":
            campos = self._ler_formulario(environ)
            if not self._csrf.validar_sessao(token, campos.get("csrf", "")):
                raise AcessoNegado("O formulário expirou. Abra a página novamente.")
        if rota == "/sair":
            if metodo != "POST":
                return Resposta("Use o botão Sair.", 405, [("Allow", "POST")])
            self._autenticacao.sair(token)
            return self._redirecionar("/entrar", [self._cookie("lab_sessao", "", True)])
        if rota == "/" and metodo == "GET":
            return Resposta(paginas.perfil(usuario, csrf))
        if rota == "/usuarios" and metodo == "GET":
            lista = self._cadastro.listar(token)
            mensagem = "Usuário cadastrado." if environ.get("QUERY_STRING") == "cadastro=ok" else ""
            return Resposta(paginas.usuarios(lista, usuario, csrf, mensagem))
        if rota in {"/cadastros/aluno", "/cadastros/professor"}:
            lista = self._cadastro.listar(token)
            orientadores = [u for u in lista if isinstance(u, Professor) and u.ativo]
            perfil = Perfil.ALUNO if rota.endswith("aluno") else Perfil.PROFESSOR
            mensagem = ""
            if metodo == "POST":
                try:
                    if campos.get("senha") != campos.get("confirmacao"):
                        raise DadosInvalidos("As senhas informadas são diferentes.")
                    try:
                        orientador = int(campos.get("orientador_id") or "0")
                    except ValueError as erro:
                        raise DadosInvalidos("Selecione um orientador válido.") from erro
                    dados = DadosCadastro(nome=campos.get("nome", ""), email=campos.get("email", ""), senha=campos.get("senha", ""),
                                           matricula=campos.get("matricula", ""), tipo=campos.get("tipo", "GRADUACAO"),
                                           orientador_id=orientador, programa_pos=campos.get("programa_pos", ""), ramal=campos.get("ramal") or None)
                    self._cadastro.cadastrar(token, perfil, dados)
                    return self._redirecionar("/usuarios?cadastro=ok")
                except AcessoNegado:
                    raise
                except FalhaPersistencia:
                    raise
                except ErroAplicacao as erro:
                    mensagem = str(erro)
            return Resposta(paginas.cadastro(perfil, usuario, csrf, orientadores, campos if metodo == "POST" else None, mensagem), 400 if mensagem else 200)
        return Resposta(paginas.layout("Página não encontrada", '<p><a href="/">Voltar ao início</a></p>', usuario, csrf), 404)
