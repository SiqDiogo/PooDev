from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Self

from .usuarios import Usuario


@dataclass(frozen=True)
class Sessao:
    usuario_id: int
    expira_em: datetime
    revogado_em: datetime | None

    def esta_valida(self, agora: datetime) -> bool:
        return self.revogado_em is None and self.expira_em > agora


class RepositorioUsuarios(ABC):
    @abstractmethod
    def buscar_por_email(self, email: str) -> Usuario | None: ...

    @abstractmethod
    def buscar_por_id(self, usuario_id: int) -> Usuario | None: ...

    @abstractmethod
    def listar(self, laboratorio_id: int) -> list[Usuario]: ...

    @abstractmethod
    def salvar(self, usuario: Usuario) -> Usuario: ...

    @abstractmethod
    def reservar_id(self) -> int: ...

    @abstractmethod
    def alterar_senha(self, usuario_id: int, senha_hash: str) -> None: ...


class RepositorioLaboratorios(ABC):
    @abstractmethod
    def esta_ativo(self, laboratorio_id: int) -> bool: ...

    @abstractmethod
    def criar(self, nome: str, localizacao: str, chefe_id: int) -> int: ...


class RepositorioSessoes(ABC):
    @abstractmethod
    def criar(self, usuario_id: int, token_hash: bytes, expira_em: datetime) -> None: ...

    @abstractmethod
    def buscar(self, token_hash: bytes) -> Sessao | None: ...

    @abstractmethod
    def revogar(self, token_hash: bytes) -> None: ...

    @abstractmethod
    def revogar_do_usuario(self, usuario_id: int) -> None: ...


class UnidadeTrabalho(ABC):
    """Agrupa os repositórios; a operação inteira confirma ou desfaz suas gravações."""

    usuarios: RepositorioUsuarios
    laboratorios: RepositorioLaboratorios
    sessoes: RepositorioSessoes

    @abstractmethod
    def contexto(self, ator_id: int | None, motivo: str) -> None: ...

    @abstractmethod
    def __enter__(self) -> Self: ...

    @abstractmethod
    def __exit__(self, tipo: type[BaseException] | None,
                 erro: BaseException | None, traceback: TracebackType | None) -> bool | None: ...
