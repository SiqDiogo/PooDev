"""Testes unitários independentes de PostgreSQL; também executáveis com unittest."""
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from urllib.parse import urlencode

from gestao_lab.aplicacao.protocolos import ServicoProtocolos
from gestao_lab.apresentacao.web import AplicacaoWeb
from gestao_lab.dominio.erros import AcessoNegado, DadosInvalidos
from gestao_lab.dominio.protocolos import (
    LIMITE_PDF_BYTES, Protocolo, VinculoEquipamento, validar_documento_pdf
)
from gestao_lab.dominio.usuarios import Aluno, ChefeLaboratorio


PDF = b"%PDF-1.4\n\x00\xe2\x93\x99conteudo original\n%%EOF"


class ProtocolosEmMemoria:
    def __init__(self):
        self.registros = {}
        self.arquivos = {}
        self.vinculos = {}

    def criar(self, lab, autor, titulo, nome, pdf):
        identificador = len(self.registros) + 1
        self.registros[identificador] = Protocolo(
            id=identificador, laboratorio_id=lab, titulo=titulo,
            nome_arquivo=nome, autor_id=autor, autor_nome="Autor de teste",
            estado="NAO_VALIDADO", criado_em=datetime.now(timezone.utc),
            assinado_em=None, validado_em=None
        )
        self.arquivos[identificador] = pdf
        return identificador

    def listar(self, lab):
        return [p for p in self.registros.values() if p.laboratorio_id == lab]

    def buscar(self, protocolo_id, lab):
        protocolo = self.registros.get(protocolo_id)
        if protocolo is None or protocolo.laboratorio_id != lab:
            return None
        return replace(protocolo, vinculos=tuple(self.vinculos.get(protocolo_id, [])))

    def assinar(self, autor, protocolo_id):
        p = self.registros[protocolo_id]
        self.registros[protocolo_id] = replace(p, assinado_em=datetime.now(timezone.utc))

    def validar(self, chefe, protocolo_id):
        p = self.registros[protocolo_id]
        self.registros[protocolo_id] = replace(
            p, estado="VALIDADO", validado_em=datetime.now(timezone.utc)
        )

    def vincular(self, protocolo_id, equipamento_id, lab, chefe):
        vinculos = self.vinculos.setdefault(protocolo_id, [])
        if not any(v.equipamento_id == equipamento_id for v in vinculos):
            vinculos.append(VinculoEquipamento(equipamento_id, "Microscópio", "EQ-1"))

    def arquivo(self, protocolo_id, lab):
        p = self.buscar(protocolo_id, lab)
        return (p.nome_arquivo, self.arquivos[p.id]) if p else None


class TransacaoFalsa:
    def __init__(self, repositorio):
        self.protocolos = repositorio
        self.recursos = SimpleNamespace(
            listar_equipamentos=lambda lab: [
                SimpleNamespace(id=10, laboratorio_id=1, nome="Microscópio", numero_patrimonio="EQ-1")
            ] if lab == 1 else []
        )
        self.contextos = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def contexto(self, ator_id, motivo):
        self.contextos.append((ator_id, motivo))


class AutenticacaoFalsa:
    def __init__(self, usuarios):
        self.usuarios = usuarios

    def identificar_na_transacao(self, tx, token):
        return self.usuarios.get(token)

    def identificar(self, token):
        return self.usuarios.get(token)


def sistema_falso():
    chefe = ChefeLaboratorio(
        id=1, nome="Chefe de teste", email="chefe@example.org",
        laboratorio_id=1, senha_hash="hash", programa_pos="Biociências"
    )
    aluno = Aluno(
        id=2, nome="Autor de teste", email="autor@example.org",
        laboratorio_id=1, senha_hash="hash", matricula="AL-1",
        orientador_id=1, tipo="GRADUACAO"
    )
    outro = ChefeLaboratorio(
        id=3, nome="Chefe de outro laboratório", email="outro@example.org",
        laboratorio_id=2, senha_hash="hash", programa_pos="Biociências"
    )
    repositorio = ProtocolosEmMemoria()
    tx = TransacaoFalsa(repositorio)
    auth = AutenticacaoFalsa({"chefe": chefe, "autor": aluno, "outro": outro})
    servico = ServicoProtocolos(lambda: tx, auth)
    return servico, repositorio, auth


class TesteProtocolos(unittest.TestCase):
    def test_valida_tipo_tamanho_extensao_e_nao_muda_bytes(self):
        self.assertEqual(
            validar_documento_pdf("  Protocolo de teste  ", "documento.PDF", PDF),
            ("Protocolo de teste", "documento.PDF")
        )
        for nome, arquivo in [
            ("../outro.pdf", PDF), ("arquivo.txt", PDF),
            ("documento.pdf", b"NAO E PDF"),
            ("documento.pdf", b"%PDF-" + b"x" * LIMITE_PDF_BYTES),
        ]:
            with self.subTest(nome=nome, tamanho=len(arquivo)):
                with self.assertRaises(DadosInvalidos):
                    validar_documento_pdf("Título", nome, arquivo)

    def test_assinatura_autor_validacao_chefe_e_vinculo(self):
        servico, repositorio, _ = sistema_falso()
        pid = servico.cadastrar(
            "autor", titulo="Reagentes", nome_arquivo="ensaio.pdf", pdf_original=PDF
        )
        with self.assertRaises(DadosInvalidos):
            servico.validar("chefe", pid)
        with self.assertRaises(AcessoNegado):
            servico.assinar("chefe", pid)
        servico.assinar("autor", pid)
        with self.assertRaises(DadosInvalidos):
            servico.assinar("autor", pid)
        with self.assertRaises(AcessoNegado):
            servico.validar("autor", pid)
        with self.assertRaises(DadosInvalidos):
            servico.vincular("chefe", pid, 10)
        servico.validar("chefe", pid)
        servico.vincular("chefe", pid, 10)
        servico.vincular("chefe", pid, 10)
        protocolo, _ = servico.consultar("chefe", pid)
        self.assertEqual(len(protocolo.vinculos), 1)
        self.assertTrue(protocolo.assinado and protocolo.validado)
        self.assertEqual(servico.baixar("autor", pid), ("ensaio.pdf", PDF))
        self.assertEqual(repositorio.arquivos[pid], PDF)

    def test_isolamento_de_laboratorios(self):
        servico, _, _ = sistema_falso()
        pid = servico.cadastrar(
            "autor", titulo="Manual", nome_arquivo="manual.pdf", pdf_original=PDF
        )
        self.assertFalse(servico.listar("outro"))
        with self.assertRaises(DadosInvalidos):
            servico.consultar("outro", pid)
        with self.assertRaises(DadosInvalidos):
            servico.baixar("outro", pid)
        with self.assertRaises(DadosInvalidos):
            servico.assinar("outro", pid)

    def test_wsgi_upload_csrf_download_e_arquivo_original(self):
        servico, _, auth = sistema_falso()
        app = AplicacaoWeb(
            auth, None,
            SimpleNamespace(porta=8000, segredo_csrf=b"segredo-de-teste-para-protocolo-2026"),
            protocolos=servico
        )
        token = "autor"
        csrf = app._csrf.para_sessao(token)

        def requisitar(rota, corpo=b"", tipo="application/x-www-form-urlencoded", metodo="GET"):
            resposta = {}
            ambiente = {
                "REQUEST_METHOD": metodo, "PATH_INFO": rota.split("?")[0],
                "QUERY_STRING": rota.partition("?")[2],
                "HTTP_HOST": "127.0.0.1:8000", "HTTP_COOKIE": f"lab_sessao={token}",
                "wsgi.url_scheme": "http", "wsgi.input": BytesIO(corpo),
                "CONTENT_LENGTH": str(len(corpo)), "CONTENT_TYPE": tipo,
            }
            def iniciar(status, headers):
                resposta["status"] = int(status.split()[0])
                resposta["headers"] = dict(headers)
            resposta["body"] = b"".join(app(ambiente, iniciar))
            return resposta

        form = requisitar("/protocolos/novo")
        self.assertEqual(form["status"], 200)
        self.assertIn(b'multipart/form-data', form["body"])
        separador = b"fronteiraPooDev123"
        corpo = (
            b"--" + separador + b'\r\nContent-Disposition: form-data; name="csrf"\r\n\r\n'
            + csrf.encode() + b"\r\n"
            + b"--" + separador + b'\r\nContent-Disposition: form-data; name="titulo"\r\n\r\n'
            + "Protocolo <script>".encode() + b"\r\n"
            + b"--" + separador + b'\r\nContent-Disposition: form-data; name="arquivo"; filename="ensaio.pdf"\r\n'
            + b"Content-Type: application/pdf\r\n\r\n" + PDF + b"\r\n"
            + b"--" + separador + b"--\r\n"
        )
        tipo = "multipart/form-data; boundary=fronteiraPooDev123"
        tentativa = requisitar("/protocolos/novo", corpo.replace(csrf.encode(), b"invalido"), tipo, "POST")
        self.assertEqual(tentativa["status"], 403)
        criado = requisitar("/protocolos/novo", corpo, tipo, "POST")
        self.assertEqual(criado["status"], 303)
        self.assertEqual(criado["headers"]["Location"], "/protocolos/detalhe?id=1")
        detalhe = requisitar("/protocolos/detalhe?id=1")
        self.assertNotIn(b"<script>", detalhe["body"])
        self.assertIn(b"&lt;script&gt;", detalhe["body"])
        baixado = requisitar("/protocolos/download?id=1")
        self.assertEqual(baixado["status"], 200)
        self.assertEqual(baixado["body"], PDF)
        self.assertEqual(baixado["headers"]["Content-Type"], "application/pdf")
        self.assertIn("attachment;", baixado["headers"]["Content-Disposition"])
        campos_post = urlencode({"csrf": csrf, "protocolo_id": "1"}).encode()
        self.assertEqual(
            requisitar("/protocolos/download?id=1", campos_post,
                       "application/x-www-form-urlencoded", "POST")["status"], 405
        )


if __name__ == "__main__":
    unittest.main()
