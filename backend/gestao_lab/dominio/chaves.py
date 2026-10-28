from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .erros import AcessoNegado, DadosInvalidos
from .usuarios import ChefeLaboratorio, Professor


def identificador(valor):
    if type(valor) is not int or not 0 < valor <= 9223372036854775807:
        raise DadosInvalidos("Selecione um registro válido.")
    return valor


class CondicaoChave(StrEnum):
    OPERACIONAL = "OPERACIONAL"
    EXTRAVIADA = "EXTRAVIADA"
    INDISPONIVEL = "INDISPONIVEL"


@dataclass(frozen=True, kw_only=True)
class DestinoChave:
    id: int
    laboratorio_id: int
    nome: str
    tipo: str
    local: str
    responsavel_id: int

    def pode_gerenciar(self, ator):
        return ator.laboratorio_id == self.laboratorio_id and (
            isinstance(ator, ChefeLaboratorio)
            or isinstance(ator, Professor) and ator.id == self.responsavel_id
        )

    def exigir_gestor(self, ator):
        if not self.pode_gerenciar(ator):
            raise AcessoNegado("Somente o Chefe ou o Professor responsável por este local pode controlar suas chaves.")


@dataclass(frozen=True, kw_only=True)
class CopiaChave:
    id: int
    codigo_copia: str
    destino: DestinoChave
    estado: str
    condicao: str
    designada_para: int | None
    designada_nome: str | None
    portador_id: int | None
    portador_nome: str | None
    emprestimo_aberto_id: int | None


@dataclass(frozen=True, kw_only=True)
class EmprestimoChave:
    id: int
    chave_id: int
    codigo_copia: str
    usuario_id: int
    usuario_nome: str
    reserva_id: int
    destino: DestinoChave
    retirada_em: datetime
    entregue_nome: str
    devolucao_em: datetime | None
    recebido_nome: str | None


@dataclass(frozen=True, kw_only=True)
class ReservaAutorizada:
    id: int
    usuario_nome: str
    recurso_nome: str
    inicio: datetime
    fim: datetime

