from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
import re

from .erros import AcessoNegado, DadosInvalidos


class Perfil(StrEnum):
    ALUNO = "ALUNO"
    PROFESSOR = "PROFESSOR"
    CHEFE = "CHEFE"


class TipoAluno(StrEnum):
    GRADUACAO = "GRADUACAO"
    MESTRADO = "MESTRADO"
    DOUTORADO = "DOUTORADO"
    POS = "POS"


def texto_obrigatorio(valor: str, campo: str, limite: int = 120) -> str:
    valor = valor.strip()
    if not valor or len(valor) > limite:
        raise DadosInvalidos(f"{campo}: informe entre 1 e {limite} caracteres.")
    return valor


def normalizar_email(email: str) -> str:
    email = email.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise DadosInvalidos("Informe um e-mail válido.")
    return email


@dataclass(frozen=True, kw_only=True)
class Usuario(ABC):
    nome: str
    email: str
    laboratorio_id: int
    senha_hash: str = field(repr=False)
    id: int | None = None
    ativo: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "nome", texto_obrigatorio(self.nome, "Nome"))
        object.__setattr__(self, "email", normalizar_email(self.email))
        if self.laboratorio_id <= 0 or (self.id is not None and self.id <= 0):
            raise DadosInvalidos("Identificador de usuário ou laboratório inválido.")

    @property
    @abstractmethod
    def perfil(self) -> Perfil:
        """Cada subtipo informa seu perfil pelo mesmo contrato."""

    def exigir_permissao_cadastro(self) -> None:
        raise AcessoNegado("Somente o Chefe do laboratório pode cadastrar usuários.")


@dataclass(frozen=True, kw_only=True)
class Professor(Usuario):
    programa_pos: str
    ramal: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "programa_pos", texto_obrigatorio(self.programa_pos, "Programa de pós"))
        if self.ramal:
            object.__setattr__(self, "ramal", texto_obrigatorio(self.ramal, "Ramal", 40))

    @property
    def perfil(self) -> Perfil:
        return Perfil.PROFESSOR


@dataclass(frozen=True, kw_only=True)
class ChefeLaboratorio(Professor):
    @property
    def perfil(self) -> Perfil:
        return Perfil.CHEFE

    def exigir_permissao_cadastro(self) -> None:
        if not self.ativo:
            raise AcessoNegado("O Chefe está inativo.")


@dataclass(frozen=True, kw_only=True)
class Aluno(Usuario):
    matricula: str
    tipo: TipoAluno
    orientador_id: int

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "matricula", texto_obrigatorio(self.matricula, "Matrícula", 64))
        try:
            object.__setattr__(self, "tipo", TipoAluno(self.tipo))
        except ValueError as erro:
            raise DadosInvalidos("Categoria de aluno inválida.") from erro
        if self.orientador_id <= 0:
            raise DadosInvalidos("Selecione um orientador.")

    @property
    def perfil(self) -> Perfil:
        return Perfil.ALUNO

    def validar_orientador(self, orientador: Usuario | None) -> None:
        if not isinstance(orientador, Professor) or not orientador.ativo:
            raise DadosInvalidos("O orientador deve ser um Professor ativo.")
        if orientador.laboratorio_id != self.laboratorio_id or orientador.id != self.orientador_id:
            raise DadosInvalidos("O orientador deve pertencer ao mesmo laboratório do aluno.")
