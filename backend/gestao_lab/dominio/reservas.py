
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum

from .erros import AcessoNegado, DadosInvalidos
from .laboratorios import Laboratorio
from .recursos import Recurso
from .usuarios import Usuario, ChefeLaboratorio



class EstadoReserva(StrEnum):
    CONFIRMADA = "CONFIRMADA"
    CANCELADA = "CANCELADA"
    CONCLUIDA = "CONCLUIDA"


@dataclass(frozen=True, kw_only=True)
class Reserva:
    usuario_id: int
    laboratorio_id: int
    recurso: Recurso
    inicio: datetime
    fim: datetime
    id: int | None = None
    estado: EstadoReserva = EstadoReserva.CONFIRMADA
    
    cancelado_em: datetime | None = None
    cancelado_por: int | None = None
    motivo_cancelamento: str | None = None


    def __post_init__(self) -> None:
        if (
            type(self.usuario_id) is not int
            or self.usuario_id <= 0
            or type(self.laboratorio_id) is not int
            or self.laboratorio_id <= 0
        ):
            raise DadosInvalidos(
                "Usuário ou laboratório inválido."
            )

        if self.id is not None and (
            type(self.id) is not int or self.id <= 0
        ):
            raise DadosInvalidos(
                "Identificador da reserva inválido."
            )

        if (
            not isinstance(self.recurso, Recurso)
            or self.recurso.id is None
        ):
            raise DadosInvalidos(
                "O recurso precisa estar cadastrado."
            )

        if self.recurso.laboratorio_id != self.laboratorio_id:
            raise DadosInvalidos(
                "O recurso pertence a outro laboratório."
            )

        if (
            not isinstance(self.inicio, datetime)
            or not isinstance(self.fim, datetime)
        ):
            raise DadosInvalidos(
                "Informe datas e horários válidos."
            )

        if (
            self.inicio.tzinfo is None
            or self.inicio.utcoffset() is None
            or self.fim.tzinfo is None
            or self.fim.utcoffset() is None
        ):
            raise DadosInvalidos(
                "Informe horários com fuso horário."
            )

        if self.fim <= self.inicio:
            raise DadosInvalidos(
                "O fim deve ser posterior ao início."
            )

        try:
            object.__setattr__(
                self,
                "estado",
                EstadoReserva(self.estado)
            )
        except ValueError as erro:
            raise DadosInvalidos(
                "Estado da reserva inválido."
            ) from erro


        
        dados_cancelamento = (
            self.cancelado_em,
            self.cancelado_por,
            self.motivo_cancelamento
        )

        if self.estado == EstadoReserva.CANCELADA:
            if not (
                isinstance(self.cancelado_em, datetime)
                and self.cancelado_em.tzinfo is not None
                and self.cancelado_em.utcoffset() is not None
                and type(self.cancelado_por) is int
                and self.cancelado_por > 0
                and isinstance(self.motivo_cancelamento, str)
                and self.motivo_cancelamento.strip()
            ):
                raise DadosInvalidos(
                    "Reserva cancelada exige data, autor e motivo."
                )

        elif any(
            valor is not None for valor in dados_cancelamento
        ):
            raise DadosInvalidos(
                "Somente reservas canceladas possuem "
                "dados de cancelamento."
            )


    def recursos_afetados(self) -> tuple[Recurso, ...]:
        return self.recurso.recursos_afetados()

    

    
    def conflita_com(self, outra: "Reserva") -> bool:
        if not isinstance(outra, Reserva):
            raise DadosInvalidos(
                "É necessário comparar duas reservas."
            )

        # Apenas reservas confirmadas bloqueiam recursos.
        if (
            self.estado != EstadoReserva.CONFIRMADA
            or outra.estado != EstadoReserva.CONFIRMADA
        ):
            return False

        # Laboratórios diferentes não compartilham recursos.
        if self.laboratorio_id != outra.laboratorio_id:
            return False

        # Verifica se os períodos se sobrepõem.
        if (
            self.inicio >= outra.fim
            or outra.inicio >= self.fim
        ):
            return False

        # Obtém os IDs de todos os recursos afetados.
        meus_ids = {
            recurso.id
            for recurso in self.recursos_afetados()
            if recurso.id is not None
        }

        outros_ids = {
            recurso.id
            for recurso in outra.recursos_afetados()
            if recurso.id is not None
        }

        # Havendo algum ID em comum, existe conflito.
        return bool(meus_ids & outros_ids)



    
    def cancelar(
        self,
        ator: Usuario,
        laboratorio: Laboratorio,
        motivo: str | None = None
    ) -> "Reserva":

        # 1. Verifica se a reserva pode ser cancelada.
        if self.estado != EstadoReserva.CONFIRMADA:
            raise DadosInvalidos(
                "Apenas reservas confirmadas podem ser canceladas."
            )
        if self.fim <= datetime.now(timezone.utc):
            raise DadosInvalidos("Esta reserva já está encerrada.")

        # 2. Confere o laboratório.
        if (
            not isinstance(laboratorio, Laboratorio)
            or laboratorio.id != self.laboratorio_id
        ):
            raise DadosInvalidos(
                "Laboratório da reserva inválido."
            )

        # 3. Confere se o usuário está ativo e pertence ao laboratório.
        if (
            not isinstance(ator, Usuario)
            or not ator.ativo
            or ator.id is None
            or ator.laboratorio_id != self.laboratorio_id
        ):
            raise AcessoNegado(
                "Usuário não autorizado a cancelar esta reserva."
            )

        # 4. Identifica o proprietário e o Chefe responsável.
        eh_dono = ator.id == self.usuario_id

        eh_chefe = (
            isinstance(ator, ChefeLaboratorio)
            and ator.id == laboratorio.chefe_usuario_id
        )

        if not (eh_dono or eh_chefe):
            raise AcessoNegado(
                "Somente o titular ou o Chefe pode cancelar a reserva."
            )

        # 5. Valida o motivo.
        if motivo is not None and not isinstance(motivo, str):
            raise DadosInvalidos(
                "O motivo de cancelamento deve ser um texto."
            )

        motivo_final = motivo.strip() if motivo is not None else ""

        if not motivo_final and eh_dono:
            motivo_final = "Cancelamento solicitado pelo titular."

        if not motivo_final:
            raise DadosInvalidos(
                "O Chefe deve informar o motivo do cancelamento."
            )

        # 6. Retorna uma nova reserva com o estado atualizado.
        return replace(
            self,
            estado=EstadoReserva.CANCELADA,
            cancelado_em=datetime.now(timezone.utc),
            cancelado_por=ator.id,
            motivo_cancelamento=motivo_final
        )


