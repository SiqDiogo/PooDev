from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import TracebackType
from typing import Self
from .laboratorios import Laboratorio
from .usuarios import Usuario
from .salas import Sala
from .bancadas import Bancada
from .equipamentos import Equipamento
from .historico import HistoricoUso
from .chaves import CopiaChave, DestinoChave, EmprestimoChave, ReservaAutorizada


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

    @abstractmethod
    def desativar(
        self, usuario_id: int, laboratorio_id: int
    ) -> bool: ...

    @abstractmethod
    def possui_orientandos_ativos(
        self, professor_id: int
    ) -> bool: ...

class RepositorioLaboratorios(ABC):
    @abstractmethod
    def esta_ativo(self, laboratorio_id: int) -> bool: ...

    @abstractmethod
    def criar(self, nome: str, localizacao: str, chefe_id: int) -> int: ...

    @abstractmethod
    def buscar_por_id(
        self, laboratorio_id: int
    ) -> Laboratorio | None:
        """Busca um laboratório pelo identificador."""
        ...

    @abstractmethod
    def listar_ativos(self) -> list[Laboratorio]:
        """Lista os laboratórios ativos."""
        ...

    
    @abstractmethod
    def atualizar_limites(
        self,
        laboratorio_id: int,
        chefe_id: int,
        duracao: timedelta | None,
        quantidade: int | None
    ) -> Laboratorio:
        """Atualiza os limites de reserva do laboratório."""
        ...




class RepositorioRecursos(ABC):
    """Contrato para persistência de salas, bancadas e equipamentos."""

    @abstractmethod
    def salvar_sala(self, sala: Sala) -> Sala:
        """Salva uma sala e devolve o objeto com seu ID."""
        ...

    @abstractmethod
    def salvar_bancada(self, bancada: Bancada) -> Bancada:
        """Salva uma bancada vinculada a uma sala."""
        ...

    @abstractmethod
    def salvar_equipamento(
        self, equipamento: Equipamento
    ) -> Equipamento:
        """Salva um equipamento com patrimônio único."""
        ...

    @abstractmethod
    def buscar_sala(self, sala_id: int) -> Sala | None:
        """Busca uma sala pelo identificador."""
        ...

    @abstractmethod
    def buscar_bancada(self, bancada_id: int) -> Bancada | None:
        """Busca uma bancada pelo identificador."""
        ...

    @abstractmethod
    def listar_salas(self, laboratorio_id: int) -> list[Sala]:
        """Lista as salas de um laboratório."""
        ...

    @abstractmethod
    def listar_bancadas(self, sala_id: int) -> list[Bancada]:
        """Lista as bancadas pertencentes a uma sala."""
        ...

    @abstractmethod
    def listar_equipamentos(
        self, laboratorio_id: int
    ) -> list[Equipamento]:
        """Lista os equipamentos de um laboratório."""
        ...

    
    @abstractmethod
    def alterar_local_equipamento(
        self,
        chefe_id: int,
        equipamento: Equipamento
    ) -> None:
        """Atualiza o vínculo de um equipamento cadastrado."""
        ...



class RepositorioReservas(ABC):
    """Contrato para criação e cancelamento de reservas."""

    @abstractmethod
    def buscar(self, reserva_id, laboratorio_id) -> dict | None: ...

    @abstractmethod
    def disponibilidade(self, laboratorio_id, usuario_id, inicio, fim) -> list[dict]: ...

    @abstractmethod
    def criar(
        self,
        usuario_id: int,
        recurso_id: int,
        inicio: datetime,
        fim: datetime
    ) -> int:
        """Cria uma reserva e retorna seu identificador."""
        ...

    @abstractmethod
    def cancelar(
        self,
        ator_id: int,
        reserva_id: int,
        motivo: str
    ) -> None:
        """Cancela uma reserva registrada no banco."""
        ...

    
    @abstractmethod
    def listar(
        self,
        laboratorio_id: int,
        usuario_id: int,
        pode_ver_todas: bool
    ) -> list[dict]:
        """Lista reservas respeitando o laboratório e o perfil."""
        ...




class RepositorioHistoricoUso(ABC):
    """Contrato para consulta de eventos de reservas."""

    @abstractmethod
    def listar(
        self,
        laboratorio_id: int,
        solicitante_id: int,
        pode_ver_todas: bool,
        *,
        usuario_id: int | None = None,
        recurso_id: int | None = None,
        desde: datetime | None = None,
        ate: datetime | None = None
    ) -> list[HistoricoUso]:
        """Consulta eventos com filtros e restrição de acesso."""
        ...



class RepositorioChaves(ABC):
    @abstractmethod
    def destinos(self, laboratorio_id) -> list[DestinoChave]: ...

    @abstractmethod
    def listar(self, laboratorio_id) -> list[CopiaChave]: ...

    @abstractmethod
    def buscar(self, chave_id, laboratorio_id) -> CopiaChave | None: ...

    @abstractmethod
    def criar(self, codigo, destino, ator_id, designada_para) -> int: ...

    @abstractmethod
    def designar(self, chave_id, ator_id, designada_para) -> None: ...

    @abstractmethod
    def reservas_autorizadas(self, copia) -> list[ReservaAutorizada]: ...

    @abstractmethod
    def emprestimos(self, laboratorio_id) -> list[EmprestimoChave]: ...

    @abstractmethod
    def buscar_emprestimo(self, emprestimo_id, laboratorio_id) -> EmprestimoChave | None: ...

    @abstractmethod
    def retirar(self, usuario_id, reserva_id, chave_id, ator_id) -> int: ...

    @abstractmethod
    def devolver(self, emprestimo_id, ator_id) -> None: ...

    @abstractmethod
    def registrar_ocorrencia(self, ator_id, chave_id, condicao, descricao) -> None: ...


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
    recursos: RepositorioRecursos
    reservas: RepositorioReservas
    sessoes: RepositorioSessoes
    historico: RepositorioHistoricoUso
    chaves: RepositorioChaves

    @abstractmethod
    def contexto(self, ator_id: int | None, motivo: str) -> None: ...

    @abstractmethod
    def __enter__(self) -> Self: ...

    @abstractmethod
    def __exit__(self, tipo: type[BaseException] | None,
                 erro: BaseException | None, traceback: TracebackType | None) -> bool | None: ...
