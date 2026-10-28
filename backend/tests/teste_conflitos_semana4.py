
from datetime import datetime, timedelta, timezone

from gestao_lab.dominio.salas import Sala
from gestao_lab.dominio.bancadas import Bancada
from gestao_lab.dominio.equipamentos import Equipamento
from gestao_lab.dominio.reservas import Reserva, EstadoReserva
from gestao_lab.dominio.laboratorios import Laboratorio
from gestao_lab.dominio.usuarios import Professor, ChefeLaboratorio
from gestao_lab.dominio.erros import AcessoNegado, DadosInvalidos


dados = {
    "laboratorio_id": 1,
    "responsavel_usuario_id": 1,
    "localizacao": "Bloco A"
}

# Criação dos equipamentos.
equipamento1 = Equipamento(
    id=30, nome="Paquimetro",
    numero_patrimonio="PAT-001",
    complemento_local="Bancada 1",
    bancada_id=20, **dados
)

equipamento2 = Equipamento(
    id=31, nome="Microscopio",
    numero_patrimonio="PAT-002",
    complemento_local="Bancada 2",
    bancada_id=21, **dados
)

# Criação das bancadas.
bancada1 = Bancada(
    id=20, nome="Bancada 1",
    numero_identificacao="B1",
    sala_id=10,
    equipamentos=(equipamento1,),
    **dados
)

bancada2 = Bancada(
    id=21, nome="Bancada 2",
    numero_identificacao="B2",
    sala_id=10,
    equipamentos=(equipamento2,),
    **dados
)

# A sala contém as duas bancadas.
sala = Sala(
    id=10, nome="Sala 1",
    identificacao="S1",
    capacidade=15,
    bancadas=(bancada1, bancada2),
    **dados
)

inicio = datetime.now(timezone.utc) + timedelta(days=1)
fim = inicio + timedelta(hours=1)


def criar_reserva(recurso, inicio_reserva=inicio,
                  fim_reserva=fim,
                  estado=EstadoReserva.CONFIRMADA):
    return Reserva(
        usuario_id=1,
        laboratorio_id=1,
        recurso=recurso,
        inicio=inicio_reserva,
        fim=fim_reserva,
        estado=estado
    )


reserva_sala = criar_reserva(sala)
reserva_b1 = criar_reserva(bancada1)
reserva_b2 = criar_reserva(bancada2)
reserva_equipamento = criar_reserva(equipamento1)

# Testes de conflito.
assert reserva_sala.conflita_com(reserva_b1) is True
assert reserva_b1.conflita_com(reserva_equipamento) is True

# Bancadas diferentes podem ser usadas simultaneamente.
assert reserva_b1.conflita_com(reserva_b2) is False

# Reserva seguinte começa após o término da primeira.
reserva_posterior = criar_reserva(
    equipamento1,
    inicio_reserva=fim,
    fim_reserva=fim + timedelta(hours=1)
)

assert (
    reserva_equipamento.conflita_com(reserva_posterior)
    is False
)


# Laboratório e usuários fictícios para os testes.
laboratorio = Laboratorio(
    id=1,
    nome="Laboratório de Teste",
    localizacao="Bloco A",
    chefe_usuario_id=3
)

titular = Professor(
    id=1,
    nome="Ana",
    email="ana@example.org",
    laboratorio_id=1,
    senha_hash="hash-teste",
    programa_pos="Computação"
)

outro_professor = Professor(
    id=2,
    nome="Carlos",
    email="carlos@example.org",
    laboratorio_id=1,
    senha_hash="hash-teste",
    programa_pos="Computação"
)

chefe = ChefeLaboratorio(
    id=3,
    nome="Maria",
    email="maria@example.org",
    laboratorio_id=1,
    senha_hash="hash-teste",
    programa_pos="Computação"
)

# Teste 1: o titular pode cancelar a própria reserva.
reserva_cancelada = reserva_sala.cancelar(
    titular, laboratorio
)

assert reserva_cancelada.estado == EstadoReserva.CANCELADA
assert reserva_cancelada.cancelado_por == titular.id
assert reserva_cancelada.motivo_cancelamento
assert reserva_cancelada.cancelado_em is not None

# O objeto original não foi alterado.
assert reserva_sala.estado == EstadoReserva.CONFIRMADA

# A reserva cancelada não gera mais conflitos.
assert (
    reserva_cancelada.conflita_com(reserva_equipamento)
    is False
)

# Teste 2: Chefe pode cancelar com justificativa.
cancelada_pelo_chefe = reserva_sala.cancelar(
    chefe,
    laboratorio,
    motivo="Manutenção emergencial na sala."
)

assert cancelada_pelo_chefe.cancelado_por == chefe.id
assert (
    cancelada_pelo_chefe.motivo_cancelamento
    == "Manutenção emergencial na sala."
)

# Função auxiliar para conferir erros esperados.
def exigir_erro(tipo_erro, operacao):
    try:
        operacao()
    except tipo_erro:
        return

    raise AssertionError(
        f"Era esperado o erro {tipo_erro.__name__}."
    )


# Teste 3: Professor não pode cancelar reserva alheia.
exigir_erro(
    AcessoNegado,
    lambda: reserva_sala.cancelar(
        outro_professor, laboratorio
    )
)

# Teste 4: Chefe deve justificar cancelamento administrativo.
exigir_erro(
    DadosInvalidos,
    lambda: reserva_sala.cancelar(
        chefe, laboratorio
    )
)

# Teste 5: Não é permitido cancelar novamente.
exigir_erro(
    DadosInvalidos,
    lambda: reserva_cancelada.cancelar(
        titular, laboratorio
    )
)

print("Testes de conflitos e cancelamentos passaram!")
