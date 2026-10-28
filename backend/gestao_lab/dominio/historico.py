
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .erros import DadosInvalidos


class AcaoHistorico(StrEnum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass(frozen=True, kw_only=True)
class HistoricoUso:
    id: int
    laboratorio_id: int
    tabela: str
    registro_id: str
    acao: AcaoHistorico
    registrado_em: datetime

    ator_id: int | None = None
    motivo: str | None = None
    antes: dict | None = None
    depois: dict | None = None
    ator_nome: str | None = None
    recurso_nome: str | None = None
    usuario_nome: str | None = None
    descricao: str | None = None

    def __post_init__(self) -> None:

        if any(
            type(numero) is not int or numero <= 0
            for numero in (self.id, self.laboratorio_id)
        ):
            raise DadosInvalidos(
                "Identificador do histórico ou laboratório inválido."
            )

        if self.ator_id is not None and (
            type(self.ator_id) is not int
            or self.ator_id <= 0
        ):
            raise DadosInvalidos(
                "Identificador do responsável inválido."
            )

        if (
            not isinstance(self.tabela, str)
            or not self.tabela.strip()
        ):
            raise DadosInvalidos(
                "Tabela do evento não informada."
            )

        if (
            not isinstance(self.registro_id, str)
            or not self.registro_id.strip()
        ):
            raise DadosInvalidos(
                "Registro do evento não informado."
            )

        try:
            object.__setattr__(
                self,
                "acao",
                AcaoHistorico(self.acao)
            )
        except (TypeError, ValueError) as erro:
            raise DadosInvalidos(
                "Ação do histórico inválida."
            ) from erro

        if (
            not isinstance(self.registrado_em, datetime)
            or self.registrado_em.tzinfo is None
            or self.registrado_em.utcoffset() is None
        ):
            raise DadosInvalidos(
                "Data do histórico sem fuso horário."
            )

        if (
            self.antes is not None
            and not isinstance(self.antes, dict)
        ):
            raise DadosInvalidos(
                "Dados anteriores do histórico inválidos."
            )

        if (
            self.depois is not None
            and not isinstance(self.depois, dict)
        ):
            raise DadosInvalidos(
                "Dados posteriores do histórico inválidos."
            )

    def eh_cancelamento(self) -> bool:
        return (
            self.tabela == "reserva"
            and self.acao == AcaoHistorico.UPDATE
            and isinstance(self.antes, dict)
            and isinstance(self.depois, dict)
            and self.antes.get("estado") != "CANCELADA"
            and self.depois.get("estado") == "CANCELADA"
        )
