from dataclasses import dataclass, field
from http import HTTPStatus
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import logging
import time

from . import paginas
from . import paginas_chaves
from .csrf import ProtecaoCSRF
from ..aplicacao.servicos import DadosCadastro
from ..dominio.erros import AcessoNegado, CredenciaisInvalidas, DadosInvalidos, ErroAplicacao, FalhaPersistencia
from ..dominio.usuarios import Perfil, Professor, ChefeLaboratorio
from datetime import date, datetime, timedelta, timezone


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
    def __init__(self, autenticacao, cadastro, configuracao, recursos=None, reservas=None, historico=None, limites=None, chaves=None):
        self._autenticacao = autenticacao
        self._cadastro = cadastro
        self._recursos = recursos
        self._chaves = chaves
        self._fuso = timezone(timedelta(hours=-3))
        self._reservas = reservas
        self._configuracao = configuracao
        self._csrf = ProtecaoCSRF(configuracao.segredo_csrf)
        self._limite = LimiteLogin()
        self._historico = historico
        self._limites = limites

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

    @staticmethod
    def _identificador(valor):
        try:
            numero = int(valor)
        except (TypeError, ValueError) as erro:
            raise DadosInvalidos(
                "Selecione um cadastro válido."
            ) from erro

        if not 0 < numero <= 9223372036854775807:
            raise DadosInvalidos(
                "Selecione um cadastro válido."
            )

        return numero


    
    @staticmethod
    def _data_hora_reserva(valor):
        try:
            instante = datetime.strptime(
                valor,
                "%Y-%m-%dT%H:%M"
            )
        except (TypeError, ValueError) as erro:
            raise DadosInvalidos(
                "Informe data e horário válidos."
            ) from erro

        # Horário local de Brasília: UTC-03:00.
        fuso_brasilia = timezone(
            timedelta(hours=-3)
        )

        return instante.replace(
            tzinfo=fuso_brasilia
        )


    
    @staticmethod
    def _data_filtro_historico(valor, fim=False):
        if not valor:
            return None

        try:
            dia = date.fromisoformat(valor)

            fuso = timezone(
                timedelta(hours=-3)
            )

            instante = datetime(
                dia.year,
                dia.month,
                dia.day,
                tzinfo=fuso
            )

            # O final selecionado é inclusivo no formulário.
            # A consulta SQL utiliza limite superior exclusivo.
            if fim:
                instante += timedelta(days=1)

            return instante

        except (TypeError, ValueError, OverflowError) as erro:
            raise DadosInvalidos(
                "Informe uma data válida no filtro."
            ) from erro




    @staticmethod
    def _ler_consulta(environ):
        try:
            parametros = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True, max_num_fields=10)
        except ValueError as erro:
            raise DadosInvalidos("Os parâmetros da página são inválidos.") from erro
        if any(len(valores) != 1 for valores in parametros.values()):
            raise DadosInvalidos("A página contém parâmetros duplicados.")
        return {nome: valores[0] for nome, valores in parametros.items()}

    def _rotear_chaves(self, rota, metodo, environ, campos, token, usuario, csrf):
        if self._chaves is None:
            raise FalhaPersistencia("Serviço de chaves indisponível.")
        dados = self._ler_consulta(environ) if metodo == "GET" else campos
        if rota == "/chaves":
            if metodo != "GET":
                return Resposta("Método não permitido.", 405, [("Allow", "GET")])
            copias, destinos, emprestimos = self._chaves.painel(token)
            mensagem = "Operação registrada." if dados.get("operacao") == "ok" else ""
            return Resposta(paginas_chaves.painel(usuario, csrf, copias, destinos, emprestimos, self._fuso, mensagem))
        mensagem = ""
        chave_id = None
        if rota not in {"/chaves/nova", "/chaves/devolver"}:
            chave_id = self._identificador(dados.get("id") if metodo == "GET" else dados.get("chave_id"))
        if rota == "/chaves/nova":
            destinos, usuarios = self._chaves.dados_cadastro(token)
        elif rota == "/chaves/devolver":
            emprestimo_id = self._identificador(dados.get("id") if metodo == "GET" else dados.get("emprestimo_id"))
            emprestimo = self._chaves.consultar_devolucao(token, emprestimo_id)
        else:
            copia, usuarios = self._chaves.consultar_gestao(token, chave_id)
        if metodo == "POST":
            try:
                if rota == "/chaves/nova":
                    self._chaves.cadastrar(token, codigo_copia=dados.get("codigo_copia", ""),
                        destino_id=self._identificador(dados.get("destino_id")),
                        designada_para=self._identificador(dados["designada_para"]) if dados.get("designada_para") else None)
                elif rota == "/chaves/designar":
                    self._chaves.designar(token, chave_id,
                        self._identificador(dados["designada_para"]) if dados.get("designada_para") else None)
                elif rota == "/chaves/retirar":
                    self._chaves.retirar(token, chave_id, self._identificador(dados.get("reserva_id")))
                elif rota == "/chaves/devolver":
                    self._chaves.devolver(token, emprestimo_id)
                elif rota == "/chaves/ocorrencia":
                    self._chaves.registrar_ocorrencia(token, chave_id, condicao=dados.get("condicao"), descricao=dados.get("descricao", ""))
                return self._redirecionar("/chaves?operacao=ok")
            except (AcessoNegado, FalhaPersistencia):
                raise
            except ErroAplicacao as erro:
                mensagem = str(erro)
        if rota == "/chaves/nova":
            pagina = paginas_chaves.nova(usuario, csrf, destinos, usuarios, dados, mensagem)
        elif rota == "/chaves/designar":
            pagina = paginas_chaves.designar(usuario, csrf, copia, usuarios, dados if metodo == "POST" else None, mensagem)
        elif rota == "/chaves/ocorrencia":
            pagina = paginas_chaves.ocorrencia(usuario, csrf, copia, dados, mensagem)
        elif rota == "/chaves/devolver":
            pagina = paginas_chaves.devolver(usuario, csrf, emprestimo, mensagem)
        else:
            if mensagem:
                # A cópia pode ter sido retirada em outra sessão enquanto o formulário estava aberto.
                return Resposta(paginas.layout("Retirada não registrada", paginas.aviso(mensagem, True) + '<p><a href="/chaves">Voltar às chaves</a></p>', usuario, csrf), 400)
            copia, reservas = self._chaves.opcoes_retirada(token, chave_id)
            pagina = paginas_chaves.retirar(usuario, csrf, copia, reservas, self._fuso, dados, mensagem)
        return Resposta(pagina, 400 if mensagem else 200)

    def _rotear_localizacao(self, metodo, environ, campos, token, usuario, csrf):
        if self._recursos is None:
            raise FalhaPersistencia("Serviço de recursos indisponível.")
        dados = self._ler_consulta(environ) if metodo == "GET" else campos
        equipamento_id = self._identificador(dados.get("id") if metodo == "GET" else dados.get("equipamento_id"))
        equipamento = self._recursos.consultar_localizacao(token, equipamento_id)
        mensagem = ""
        if metodo == "POST":
            try:
                self._recursos.alterar_localizacao(token, equipamento_id,
                    bancada_id=self._identificador(dados["bancada_id"]) if dados.get("bancada_id") else None,
                    sala_direta_id=self._identificador(dados["sala_direta_id"]) if dados.get("sala_direta_id") else None,
                    complemento_local=dados.get("complemento_local", ""))
                return self._redirecionar("/recursos?local=ok")
            except DadosInvalidos as erro:
                mensagem = str(erro)
        salas, bancadas, _ = self._recursos.listar(token)
        return Resposta(paginas.formulario_localizacao(usuario, csrf, equipamento, salas, bancadas,
                        dados if metodo == "POST" else None, mensagem), 400 if mensagem else 200)

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
        
        if rota not in {
            "/",
            "/usuarios",
            "/usuarios/remover",
            "/cadastros/aluno",
            "/cadastros/professor",
            "/recursos",
            "/cadastros/sala",
            "/cadastros/bancada",
            "/cadastros/equipamento",
            "/reservas/nova",
            "/reservas",
            "/reservas/cancelar",
            "/historico",
            "/limites-reserva",
            "/recursos/vinculos",
            "/recursos/localizacao",
            "/chaves",
            "/chaves/nova",
            "/chaves/designar",
            "/chaves/retirar",
            "/chaves/devolver",
            "/chaves/ocorrencia",
            "/sair",
        }:
            return Resposta(
                paginas.layout(
                    "Página não encontrada",
                    '<p><a href="/">Voltar ao início</a></p>'
                ),
                404
            )

        usuario = self._autenticacao.identificar(token)
        if usuario is None:
            return self._redirecionar("/entrar", [self._cookie("lab_sessao", "", True)])
        csrf = self._csrf.para_sessao(token)
        if metodo == "POST":
            campos = self._ler_formulario(environ)
            if not self._csrf.validar_sessao(token, campos.get("csrf", "")):
                raise AcessoNegado("O formulário expirou. Abra a página novamente.")
        if rota.startswith("/chaves"):
            return self._rotear_chaves(rota, metodo, environ, campos if metodo == "POST" else {}, token, usuario, csrf)
        if rota == "/recursos/localizacao":
            return self._rotear_localizacao(metodo, environ, campos if metodo == "POST" else {}, token, usuario, csrf)
        if rota == "/sair":
            if metodo != "POST":
                return Resposta("Use o botão Sair.", 405, [("Allow", "POST")])
            self._autenticacao.sair(token)
            return self._redirecionar("/entrar", [self._cookie("lab_sessao", "", True)])
        if rota == "/" and metodo == "GET":
            return Resposta(paginas.perfil(usuario, csrf))
        if rota == "/reservas" and metodo == "GET":

            if self._reservas is None:
                raise FalhaPersistencia(
                    "Serviço de reservas indisponível."
                )

            lista = self._reservas.listar(token)

            mensagem = (
                "Reserva cancelada com sucesso."
                if environ.get("QUERY_STRING") == "cancelada=ok"
                else ""
            )

            return Resposta(
                paginas.pagina_reservas(
                    usuario,
                    csrf,
                    lista,
                    mensagem
                )
            )
        if rota == "/reservas/cancelar":

            if metodo != "POST":
                return Resposta(
                    "Método não permitido.",
                    405,
                    [("Allow", "POST")]
                )

            if self._reservas is None:
                raise FalhaPersistencia(
                    "Serviço de reservas indisponível."
                )

            try:
                reserva_id = self._identificador(
                    campos.get("reserva_id")
                )

                motivo = campos.get("motivo", "")

                self._reservas.cancelar(
                    token,
                    reserva_id=reserva_id,
                    motivo=motivo
                )

            except (AcessoNegado, FalhaPersistencia):
                raise

            except ErroAplicacao as erro:
                lista = self._reservas.listar(token)

                return Resposta(
                    paginas.pagina_reservas(
                        usuario,
                        csrf,
                        lista,
                        str(erro),
                        True
                    ),
                    400
                )

            return self._redirecionar(
                "/reservas?cancelada=ok"
            )
        if rota == "/historico":

            if metodo != "GET":
                return Resposta(
                    "Método não permitido.",
                    405,
                    [("Allow", "GET")]
                )

            if self._historico is None or self._reservas is None:
                raise FalhaPersistencia(
                    "Serviço de histórico indisponível."
                )

            try:
                parametros = parse_qs(
                    environ.get("QUERY_STRING", ""),
                    keep_blank_values=True,
                    max_num_fields=10
                )
            except ValueError as erro:
                raise DadosInvalidos(
                    "Filtros de pesquisa inválidos."
                ) from erro

            nomes = (
                "usuario_id",
                "recurso_id",
                "desde",
                "ate"
            )

            filtros = {}

            for nome in nomes:
                valores = parametros.get(nome, [""])

                if len(valores) != 1:
                    raise DadosInvalidos(
                        "Não repita os filtros de pesquisa."
                    )

                filtros[nome] = valores[0].strip()

            mensagem = ""
            eventos = []

            try:
                usuario_id = (
                    self._identificador(
                        filtros["usuario_id"]
                    )
                    if filtros["usuario_id"]
                    else None
                )

                recurso_id = (
                    self._identificador(
                        filtros["recurso_id"]
                    )
                    if filtros["recurso_id"]
                    else None
                )

                desde = self._data_filtro_historico(
                    filtros["desde"]
                )

                ate = self._data_filtro_historico(
                    filtros["ate"],
                    fim=True
                )

                eventos = self._historico.listar(
                    token,
                    usuario_id=usuario_id,
                    recurso_id=recurso_id,
                    desde=desde,
                    ate=ate
                )

            except DadosInvalidos as erro:
                mensagem = str(erro)

            # Recursos disponíveis como opções do filtro.
            salas, bancadas, equipamentos = (
                self._reservas.listar_recursos(token)
            )

            recursos = (
                list(salas)
                + list(bancadas)
                + list(equipamentos)
            )

            # Apenas o Chefe pode selecionar outro usuário.
            usuarios = (
                self._cadastro.listar(token)
                if isinstance(usuario, ChefeLaboratorio)
                else []
            )

            return Resposta(
                paginas.pagina_historico(
                    usuario,
                    csrf,
                    eventos,
                    recursos,
                    usuarios,
                    filtros,
                    mensagem
                ),
                400 if mensagem else 200
            )
        if rota == "/limites-reserva":

            # A tela é exclusiva do Chefe.
            if not isinstance(usuario, ChefeLaboratorio):
                raise AcessoNegado(
                    "Somente o Chefe pode configurar "
                    "os limites de reserva."
                )

            if self._limites is None:
                raise FalhaPersistencia(
                    "Serviço de limites indisponível."
                )

            mensagem = ""

            if metodo == "POST":

                try:
                    # Converte os campos para números.
                    # Campo vazio significa ausência de limite.
                    def inteiro_opcional(nome):
                        texto = campos.get(nome, "").strip()

                        if not texto:
                            return None

                        try:
                            numero = int(texto)
                        except ValueError as erro:
                            raise DadosInvalidos(
                                "Informe um número inteiro válido."
                            ) from erro

                        if numero <= 0:
                            raise DadosInvalidos(
                                "Os limites devem ser positivos."
                            )

                        return numero

                    duracao = inteiro_opcional(
                        "duracao_minutos"
                    )

                    quantidade = inteiro_opcional(
                        "quantidade"
                    )

                    # Solicita a alteração ao serviço.
                    self._limites.configurar(
                        token,
                        duracao_minutos=duracao,
                        quantidade=quantidade
                    )

                    return self._redirecionar(
                        "/limites-reserva?salvo=ok"
                    )

                except (AcessoNegado, FalhaPersistencia):
                    raise

                except ErroAplicacao as erro:
                    mensagem = str(erro)

            # Consulta os limites atuais.
            laboratorio = self._limites.consultar(token)

            sucesso = (
                "Limites de reserva atualizados com sucesso."
                if (
                    metodo == "GET"
                    and environ.get("QUERY_STRING") == "salvo=ok"
                )
                else ""
            )

            return Resposta(
                paginas.formulario_limites_reserva(
                    usuario,
                    csrf,
                    laboratorio,
                    dados=campos if metodo == "POST" else None,
                    mensagem=mensagem,
                    sucesso=sucesso
                ),
                400 if mensagem else 200
            )
        if rota == "/recursos/vinculos":

            # Apenas o Chefe pode acessar esta página.
            if not isinstance(usuario, ChefeLaboratorio):
                raise AcessoNegado(
                    "Somente o Chefe pode alterar vínculos "
                    "de equipamentos."
                )

            if self._recursos is None:
                raise FalhaPersistencia(
                    "Serviço de recursos indisponível."
                )

            mensagem = ""

            # Processa os formulários.
            if metodo == "POST":
                try:
                    acao = campos.get("acao", "")

                    if acao not in {
                        "vincular",
                        "desvincular"
                    }:
                        raise DadosInvalidos(
                            "Operação de vínculo inválida."
                        )

                    equipamento_id = self._identificador(
                        campos.get("equipamento_id")
                    )

                    complemento = (
                        campos.get("complemento_local", "")
                        .strip() or None
                    )

                    if acao == "vincular":
                        bancada_id = self._identificador(
                            campos.get("bancada_id")
                        )

                        self._recursos.vincular_equipamento(
                            token,
                            equipamento_id=equipamento_id,
                            bancada_id=bancada_id,
                            complemento_local=complemento
                        )

                    else:
                        self._recursos.desvincular_equipamento(
                            token,
                            equipamento_id=equipamento_id,
                            complemento_local=complemento
                        )

                    return self._redirecionar(
                        f"/recursos/vinculos?acao={acao}"
                    )

                except (AcessoNegado, FalhaPersistencia):
                    raise

                except ErroAplicacao as erro:
                    mensagem = str(erro)

            # Consulta a localização atual.
            _, bancadas, equipamentos = (
                self._recursos.listar(token)
            )

            sucesso = ""

            if metodo == "GET":
                acao_confirmada = parse_qs(
                    environ.get("QUERY_STRING", "")
                ).get("acao", [""])[0]

                sucesso = {
                    "vincular":
                        "Equipamento vinculado com sucesso.",
                    "desvincular":
                        "Equipamento desvinculado com sucesso."
                }.get(acao_confirmada, "")

            return Resposta(
                paginas.formulario_vinculos_equipamento(
                    usuario,
                    csrf,
                    bancadas,
                    equipamentos,
                    dados=campos if metodo == "POST" else None,
                    mensagem=mensagem,
                    sucesso=sucesso
                ),
                400 if mensagem else 200
            )



        
        if rota == "/reservas/nova":

            if self._reservas is None:
                raise FalhaPersistencia(
                    "Serviço de reservas indisponível."
                )

            mensagem = ""
            disponibilidade = None
            dados_consulta = self._ler_consulta(environ) if metodo == "GET" else campos
            if metodo == "GET" and (dados_consulta.get("inicio") or dados_consulta.get("fim")):
                try:
                    disponibilidade = self._reservas.disponibilidade(token,
                        self._data_hora_reserva(dados_consulta.get("inicio")), self._data_hora_reserva(dados_consulta.get("fim")))
                except DadosInvalidos as erro:
                    mensagem = str(erro)

            # Processa o formulário enviado.
            if metodo == "POST":
                try:
                    recurso_id = self._identificador(
                        campos.get("recurso_id")
                    )

                    inicio = self._data_hora_reserva(
                        campos.get("inicio")
                    )

                    fim = self._data_hora_reserva(
                        campos.get("fim")
                    )

                    self._reservas.reservar(
                        token,
                        recurso_id=recurso_id,
                        inicio=inicio,
                        fim=fim
                    )

                    return self._redirecionar(
                        "/reservas/nova?criada=ok"
                    )

                except (AcessoNegado, FalhaPersistencia):
                    raise

                except ErroAplicacao as erro:
                    mensagem = str(erro)

            # A listagem está disponível para
            # qualquer usuário autenticado.
            salas, bancadas, equipamentos = (
                self._reservas.listar_recursos(token)
            )

            parametros = parse_qs(
                environ.get("QUERY_STRING", "")
            )

            sucesso = (
                "Reserva registrada com sucesso."
                if (
                    metodo == "GET"
                    and parametros.get("criada") == ["ok"]
                )
                else ""
            )

            return Resposta(
                paginas.formulario_reserva(
                    usuario,
                    csrf,
                    salas,
                    bancadas,
                    equipamentos,
                    dados=dados_consulta,
                    mensagem=mensagem,
                    sucesso=sucesso,
                    disponibilidade=disponibilidade
                ),
                400 if mensagem else 200
            )
        



        
        if rota == "/usuarios" and metodo == "GET":
            lista = self._cadastro.listar(token)

            query = environ.get("QUERY_STRING", "")

            if query == "cadastro=ok":
                mensagem = "Usuário cadastrado."
            elif query == "remocao=ok":
                mensagem = "Cadastro removido (conta desativada)."
            else:
                mensagem = ""

            return Resposta(
                paginas.usuarios(lista, usuario, csrf, mensagem)
            )

        if rota == "/usuarios/remover":

            if metodo == "GET":
                parametros = parse_qs(
                    environ.get("QUERY_STRING", "")
                )

                identificador = self._identificador(
                    (parametros.get("id") or [None])[0]
                )

                alvo = self._cadastro.consultar(
                    token, identificador
                )

                return Resposta(
                    paginas.confirmar_remocao(
                        alvo, usuario, csrf
                    )
                )

            identificador = self._identificador(
                campos.get("usuario_id")
            )

            self._cadastro.remover(token, identificador)

            return self._redirecionar(
                "/usuarios?remocao=ok"
            )


        
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

        if rota in {
            "/recursos",
            "/cadastros/sala",
            "/cadastros/bancada",
            "/cadastros/equipamento",
        }:
            if rota != "/recursos" and not isinstance(usuario, ChefeLaboratorio):
                raise AcessoNegado(
                    "Somente o Chefe pode gerenciar recursos."
                )

            if self._recursos is None:
                raise FalhaPersistencia(
                    "Serviço de recursos indisponível."
                )

            if rota == "/recursos":
                if metodo != "GET":
                    return Resposta(
                        "Método não permitido.",
                        405,
                        [("Allow", "GET")]
                    )

                salas, bancadas, equipamentos = (
                    self._recursos.listar(token)
                )

                mensagem = (
                    "Recurso cadastrado com sucesso."
                    if environ.get("QUERY_STRING") == "cadastro=ok"
                    else ""
                )

                return Resposta(
                    paginas.painel_recursos(
                        usuario, csrf,
                        salas, bancadas, equipamentos,
                        mensagem
                    )
                )

            mensagem = ""
            responsaveis = self._recursos.responsaveis(token)

            if metodo == "POST":
                try:
                    if rota == "/cadastros/sala":
                        self._recursos.cadastrar_sala(
                            token,
                            nome=campos.get("nome", ""),
                            identificacao=campos.get(
                                "identificacao", ""
                            ),
                            localizacao=campos.get(
                                "localizacao", ""
                            ),
                            responsavel_id=self._identificador(campos["responsavel_id"]) if campos.get("responsavel_id") else None,
                            capacidade=self._identificador(
                                campos.get("capacidade")
                            )
                        )

                    elif rota == "/cadastros/bancada":
                        self._recursos.cadastrar_bancada(
                            token,
                            nome=campos.get("nome", ""),
                            numero_identificacao=campos.get(
                                "numero_identificacao", ""
                            ),
                            responsavel_id=self._identificador(campos["responsavel_id"]) if campos.get("responsavel_id") else None,
                            sala_id=self._identificador(
                                campos.get("sala_id")
                            )
                        )

                    elif rota == "/cadastros/equipamento":
                        bancada_id = (
                            self._identificador(
                                campos["bancada_id"]
                            )
                            if campos.get("bancada_id")
                            else None
                        )

                        sala_id = (
                            self._identificador(
                                campos["sala_direta_id"]
                            )
                            if campos.get("sala_direta_id")
                            else None
                        )

                        self._recursos.cadastrar_equipamento(
                            token,
                            nome=campos.get("nome", ""),
                            numero_patrimonio=campos.get(
                                "numero_patrimonio", ""
                            ),
                            complemento_local=campos.get(
                                "complemento_local", ""
                            ),
                            responsavel_id=self._identificador(campos["responsavel_id"]) if campos.get("responsavel_id") else None,
                            bancada_id=bancada_id,
                            sala_direta_id=sala_id,
                            foto_uri=campos.get("foto_uri") or None,
                            observacao=campos.get(
                                "observacao"
                            ) or None
                        )

                    return self._redirecionar(
                        "/recursos?cadastro=ok"
                    )

                except (AcessoNegado, FalhaPersistencia):
                    raise

                except ErroAplicacao as erro:
                    mensagem = str(erro)

            salas, bancadas, equipamentos = (
                self._recursos.listar(token)
            )

            dados = campos if metodo == "POST" else None
            status = 400 if mensagem else 200

            if rota == "/cadastros/sala":
                return Resposta(
                    paginas.formulario_sala(
                        usuario, csrf, dados, mensagem, responsaveis
                    ),
                    status
                )

            if rota == "/cadastros/bancada":
                return Resposta(
                    paginas.formulario_bancada(
                        usuario, csrf, salas, dados, mensagem, responsaveis
                    ),
                    status
                )

            if rota == "/cadastros/equipamento":
                return Resposta(
                    paginas.formulario_equipamento(
                        usuario, csrf,
                        salas, bancadas, dados, mensagem, responsaveis
                    ),
                    status
                )

        return Resposta(paginas.layout("Página não encontrada", '<p><a href="/">Voltar ao início</a></p>', usuario, csrf), 404)
