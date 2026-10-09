import argparse
from getpass import getpass
from wsgiref.simple_server import make_server, WSGIRequestHandler

from .aplicacao.seguranca import ProtecaoSenha
from .aplicacao.servicos import DadosCadastro, ServicoAutenticacao, ServicoCadastro, ServicoConfiguracaoInicial
from .apresentacao.web import AplicacaoWeb
from .dominio.erros import DadosInvalidos, ErroAplicacao
from .infraestrutura.configuracao import Configuracao
from .infraestrutura.postgres import UnidadeTrabalhoPostgres


class AtendimentoLocal(WSGIRequestHandler):
    def setup(self):
        self.request.settimeout(10)
        super().setup()

    def log_message(self, formato, *args):
        # O acesso local não precisa registrar e-mails, tokens ou corpos de formulário.
        pass


def pedir_senha():
    senha = getpass("Senha (12 a 128 caracteres): ")
    if senha != getpass("Confirmar senha: "):
        raise DadosInvalidos("As senhas informadas são diferentes.")
    return senha


def main():
    parser = argparse.ArgumentParser(description="Cadastro e autenticação do laboratório")
    parser.add_argument("comando", choices=("servir", "criar-chefe", "definir-senha"))
    args = parser.parse_args()
    try:
        config = Configuracao.do_ambiente()
        transacao = lambda: UnidadeTrabalhoPostgres(config.database_url)
        senhas = ProtecaoSenha()
        configuracao = ServicoConfiguracaoInicial(transacao, senhas)
        if args.comando == "criar-chefe":
            laboratorio = input("Nome do laboratório: ")
            localizacao = input("Localização do laboratório: ")
            nome = input("Nome do Chefe: ")
            email = input("E-mail do Chefe: ")
            programa = input("Programa de pós: ")
            ramal = input("Ramal (opcional): ") or None
            dados = DadosCadastro(nome=nome, email=email, programa_pos=programa, ramal=ramal, senha=pedir_senha())
            chefe = configuracao.criar_chefe(laboratorio, localizacao, dados)
            print(f"Chefe cadastrado: {chefe.nome}. Laboratório: {chefe.laboratorio_id}.")
        elif args.comando == "definir-senha":
            email = input("E-mail do usuário: ")
            configuracao.definir_senha(email, pedir_senha())
            print("Senha redefinida e sessões anteriores revogadas.")
        else:
            autenticacao = ServicoAutenticacao(transacao, senhas, config.horas_sessao)
            cadastro = ServicoCadastro(transacao, senhas, autenticacao)
            app = AplicacaoWeb(autenticacao, cadastro, config)
            # O servidor de referência atende a demonstração local; a interface é WSGI.
            with make_server("127.0.0.1", config.porta, app, handler_class=AtendimentoLocal) as servidor:
                print(f"Abra http://127.0.0.1:{config.porta} — Ctrl+C para encerrar.")
                servidor.serve_forever()
    except (ErroAplicacao, OSError) as erro:
        if isinstance(erro, ErroAplicacao):
            parser.exit(1, f"Erro: {erro}\n")
        parser.exit(1, "Erro ao abrir o servidor local. Confira a porta configurada.\n")
    except (KeyboardInterrupt, EOFError):
        print("\nOperação encerrada.")


if __name__ == "__main__":
    main()
