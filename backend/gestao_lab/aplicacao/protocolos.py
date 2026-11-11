from ..dominio.erros import AcessoNegado, DadosInvalidos
from ..dominio.protocolos import validar_documento_pdf
from ..dominio.usuarios import ChefeLaboratorio


class ServicoProtocolos:
    """Cadastro e validação de protocolos sob a identidade da sessão autenticada."""

    def __init__(self, transacao, autenticacao):
        self._transacao = transacao
        self._autenticacao = autenticacao

    def _ator(self, tx, token):
        ator = self._autenticacao.identificar_na_transacao(tx, token)
        if ator is None:
            raise AcessoNegado("Entre novamente para continuar.")
        return ator

    @staticmethod
    def _protocolo(tx, protocolo_id, laboratorio_id):
        if type(protocolo_id) is not int or protocolo_id <= 0:
            raise DadosInvalidos("Selecione um protocolo válido.")
        protocolo = tx.protocolos.buscar(protocolo_id, laboratorio_id)
        if protocolo is None:
            raise DadosInvalidos("Protocolo não encontrado neste laboratório.")
        return protocolo

    def listar(self, token):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            return tx.protocolos.listar(ator.laboratorio_id)

    def consultar(self, token, protocolo_id):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            protocolo = self._protocolo(tx, protocolo_id, ator.laboratorio_id)
            equipamentos = (
                tx.recursos.listar_equipamentos(ator.laboratorio_id)
                if isinstance(ator, ChefeLaboratorio) and protocolo.validado
                else []
            )
            return protocolo, equipamentos

    def cadastrar(self, token, *, titulo, nome_arquivo, pdf_original):
        titulo, nome_arquivo = validar_documento_pdf(titulo, nome_arquivo, pdf_original)
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            tx.contexto(ator.id, "Cadastro de protocolo em PDF")
            return tx.protocolos.criar(
                ator.laboratorio_id, ator.id, titulo, nome_arquivo, pdf_original
            )

    def assinar(self, token, protocolo_id):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            protocolo = self._protocolo(tx, protocolo_id, ator.laboratorio_id)
            if protocolo.autor_id != ator.id:
                raise AcessoNegado("Somente o autor pode assinar este protocolo.")
            if protocolo.assinado:
                raise DadosInvalidos("O protocolo já foi assinado.")
            tx.contexto(ator.id, "Assinatura de protocolo pelo autor")
            tx.protocolos.assinar(ator.id, protocolo_id)

    def validar(self, token, protocolo_id):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            if not isinstance(ator, ChefeLaboratorio):
                raise AcessoNegado("Somente o Chefe pode validar protocolos.")
            protocolo = self._protocolo(tx, protocolo_id, ator.laboratorio_id)
            if not protocolo.assinado:
                raise DadosInvalidos("O autor precisa assinar o protocolo antes da validação.")
            if protocolo.validado:
                raise DadosInvalidos("Este protocolo já está validado.")
            tx.contexto(ator.id, "Validação de protocolo pelo Chefe")
            tx.protocolos.validar(ator.id, protocolo_id)

    def vincular(self, token, protocolo_id, equipamento_id):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            if not isinstance(ator, ChefeLaboratorio):
                raise AcessoNegado("Somente o Chefe pode vincular protocolos a equipamentos.")
            protocolo = self._protocolo(tx, protocolo_id, ator.laboratorio_id)
            if not protocolo.validado:
                raise DadosInvalidos("Somente protocolos validados podem ser vinculados.")
            if type(equipamento_id) is not int or equipamento_id <= 0:
                raise DadosInvalidos("Selecione um equipamento válido.")
            if not any(
                e.id == equipamento_id
                for e in tx.recursos.listar_equipamentos(ator.laboratorio_id)
            ):
                raise DadosInvalidos("Equipamento não encontrado neste laboratório.")
            tx.contexto(ator.id, "Vínculo entre protocolo e equipamento")
            tx.protocolos.vincular(
                protocolo_id, equipamento_id, ator.laboratorio_id, ator.id
            )

    def baixar(self, token, protocolo_id):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            self._protocolo(tx, protocolo_id, ator.laboratorio_id)
            arquivo = tx.protocolos.arquivo(protocolo_id, ator.laboratorio_id)
            if arquivo is None:
                raise DadosInvalidos("Arquivo do protocolo não encontrado.")
            return arquivo
