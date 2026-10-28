from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from ..dominio.salas import Sala
from ..dominio.bancadas import Bancada
from ..dominio.equipamentos import Equipamento
import secrets

from .seguranca import ProtecaoSenha, TokensSessao
from ..dominio.erros import AcessoNegado, CredenciaisInvalidas, DadosInvalidos
from ..dominio.repositorios import UnidadeTrabalho
from ..dominio.usuarios import Aluno, ChefeLaboratorio, Perfil, Professor, TipoAluno, Usuario, normalizar_email, texto_obrigatorio
from ..dominio.reservas import Reserva
from ..dominio.historico import HistoricoUso

FabricaTransacao = Callable[[], UnidadeTrabalho]


@dataclass(frozen=True, kw_only=True)
class DadosCadastro:
    nome: str
    email: str
    senha: str = field(repr=False)
    programa_pos: str = ""
    ramal: str | None = None
    matricula: str = ""
    tipo: str = "GRADUACAO"
    orientador_id: int = 0


class ServicoAutenticacao:
    def __init__(self, transacao: FabricaTransacao, senhas: ProtecaoSenha, horas_sessao: int = 8):
        self._transacao = transacao
        self._senhas = senhas
        self._duracao = timedelta(hours=horas_sessao)
        # A tentativa de um e-mail inexistente também executa uma derivação de senha.
        self._hash_ficticio = senhas.gerar_hash(secrets.token_urlsafe(32))

    def entrar(self, email: str, senha: str) -> str:
        with self._transacao() as tx:
            usuario = tx.usuarios.buscar_por_email(email.strip().lower())
            correto = self._senhas.verificar(senha, usuario.senha_hash if usuario else self._hash_ficticio)
            if not correto or usuario is None or not usuario.ativo or not tx.laboratorios.esta_ativo(usuario.laboratorio_id):
                raise CredenciaisInvalidas("E-mail ou senha inválidos.")
            token = TokensSessao.gerar()
            tx.sessoes.criar(usuario.id, TokensSessao.resumir(token), datetime.now(timezone.utc) + self._duracao)
            return token

    def identificar_na_transacao(self, tx: UnidadeTrabalho, token: str) -> Usuario | None:
        if not TokensSessao.formato_valido(token):
            return None
        sessao = tx.sessoes.buscar(TokensSessao.resumir(token))
        if sessao is None or not sessao.esta_valida(datetime.now(timezone.utc)):
            return None
        usuario = tx.usuarios.buscar_por_id(sessao.usuario_id)
        if usuario is None or not usuario.ativo or not tx.laboratorios.esta_ativo(usuario.laboratorio_id):
            return None
        return usuario

    def identificar(self, token: str) -> Usuario | None:
        if not TokensSessao.formato_valido(token):
            return None
        with self._transacao() as tx:
            return self.identificar_na_transacao(tx, token)

    def sair(self, token: str) -> None:
        if TokensSessao.formato_valido(token):
            with self._transacao() as tx:
                tx.sessoes.revogar(TokensSessao.resumir(token))


class ServicoCadastro:
    def __init__(self, transacao: FabricaTransacao, senhas: ProtecaoSenha, autenticacao: ServicoAutenticacao):
        self._transacao = transacao
        self._senhas = senhas
        self._autenticacao = autenticacao

    def _exigir_chefe(
        self,
        tx: UnidadeTrabalho,
        token: str,
        *,
        para_remocao: bool = False
) -> Usuario:

        ator = self._autenticacao.identificar_na_transacao(tx, token)

        if ator is None:
            raise AcessoNegado("Entre novamente para continuar.")

        if para_remocao and not isinstance(ator, ChefeLaboratorio):
            raise AcessoNegado(
                "Somente o Chefe do laboratório pode remover cadastros."
            )

        ator.exigir_permissao_cadastro()

        return ator

    def listar(self, token: str) -> list[Usuario]:
        with self._transacao() as tx:
            ator = self._exigir_chefe(tx, token)
            return tx.usuarios.listar(ator.laboratorio_id)

    def consultar(self, token: str, usuario_id: int) -> Usuario:
        with self._transacao() as tx:
            ator = self._exigir_chefe(
                tx, token, para_remocao=True
            )

            alvo = tx.usuarios.buscar_por_id(usuario_id)

            if alvo is None or alvo.laboratorio_id != ator.laboratorio_id:
                raise DadosInvalidos(
                "Cadastro não encontrado neste laboratório."
                )

            ator.exigir_permissao_remocao(alvo)

            return alvo


    def remover(self, token: str, usuario_id: int) -> None:
        with self._transacao() as tx:
            ator = self._exigir_chefe(
                tx, token, para_remocao=True
            )

            alvo = tx.usuarios.buscar_por_id(usuario_id)

            if alvo is None or alvo.laboratorio_id != ator.laboratorio_id:
                raise DadosInvalidos(
                    "Cadastro não encontrado neste laboratório."
                )

            ator.exigir_permissao_remocao(alvo)

            if isinstance(alvo, Professor):
                if tx.usuarios.possui_orientandos_ativos(alvo.id):
                    raise DadosInvalidos(
                        "Este professor ainda orienta alunos ativos "
                        "e não pode ter o cadastro removido."
                    )

            tx.contexto(
                ator.id,
                "Desativação de cadastro pelo Chefe de Laboratório"
            )

            if not tx.usuarios.desativar(
                alvo.id, ator.laboratorio_id
            ):
                raise DadosInvalidos(
                    "Este cadastro já está inativo."
                )

            tx.sessoes.revogar_do_usuario(alvo.id)

    def cadastrar(self, token: str, perfil: Perfil, dados: DadosCadastro) -> Usuario:
        with self._transacao() as tx:
            ator = self._exigir_chefe(tx, token)
            base = dict(nome=dados.nome, email=dados.email, laboratorio_id=ator.laboratorio_id, senha_hash="")
            if perfil == Perfil.ALUNO:
                usuario = Aluno(**base, matricula=dados.matricula, tipo=dados.tipo, orientador_id=dados.orientador_id)
                usuario.validar_orientador(tx.usuarios.buscar_por_id(usuario.orientador_id))
            elif perfil == Perfil.PROFESSOR:
                usuario = Professor(**base, programa_pos=dados.programa_pos, ramal=dados.ramal)
            else:
                raise DadosInvalidos("Cada laboratório tem um único Chefe, criado na configuração inicial.")
            # Validamos o objeto antes de calcular o hash e iniciar as gravações.
            usuario = replace(usuario, senha_hash=self._senhas.gerar_hash(dados.senha))
            tx.contexto(ator.id, f"Cadastro de {usuario.perfil.lower()}")
            return tx.usuarios.salvar(usuario)



class ServicoRecursos:
    """Coordena os cadastros de recursos do laboratório."""

    def __init__(
        self,
        transacao: FabricaTransacao,
        autenticacao: ServicoAutenticacao
    ):
        self._transacao = transacao
        self._autenticacao = autenticacao

    def _exigir_chefe(
        self, tx: UnidadeTrabalho, token: str
    ) -> ChefeLaboratorio:

        ator = self._autenticacao.identificar_na_transacao(
            tx, token
        )

        if ator is None:
            raise AcessoNegado(
                "Entre novamente para continuar."
            )

        if not isinstance(ator, ChefeLaboratorio):
            raise AcessoNegado(
                "Somente o Chefe do laboratório "
                "pode cadastrar recursos."
            )

        ator.exigir_permissao_cadastro()
        return ator

    @staticmethod
    def _validar_responsavel(
        tx: UnidadeTrabalho,
        responsavel_id: int,
        laboratorio_id: int
    ) -> None:

        if type(responsavel_id) is not int or responsavel_id <= 0:
            raise DadosInvalidos(
                "Selecione um responsável válido."
            )

        responsavel = tx.usuarios.buscar_por_id(
            responsavel_id
        )

        if (
            not isinstance(responsavel, Professor)
            or not responsavel.ativo
            or responsavel.laboratorio_id != laboratorio_id
        ):
            raise DadosInvalidos(
                "O responsável deve ser um Professor "
                "ativo do mesmo laboratório."
            )

    @staticmethod
    def _buscar_sala(
        tx: UnidadeTrabalho,
        sala_id: int,
        laboratorio_id: int
    ) -> Sala:

        if type(sala_id) is not int or sala_id <= 0:
            raise DadosInvalidos("Selecione uma sala válida.")

        sala = tx.recursos.buscar_sala(sala_id)

        if sala is None or sala.laboratorio_id != laboratorio_id:
            raise DadosInvalidos(
                "Sala não encontrada neste laboratório."
            )

        return sala

    def cadastrar_sala(
        self,
        token: str,
        *,
        nome: str,
        identificacao: str,
        localizacao: str,
        capacidade: int,
        responsavel_id: int | None = None
    ) -> Sala:

        with self._transacao() as tx:
            chefe = self._exigir_chefe(tx, token)

            responsavel = (
                chefe.id
                if responsavel_id is None
                else responsavel_id
            )

            self._validar_responsavel(
                tx, responsavel, chefe.laboratorio_id
            )

            sala = Sala(
                nome=nome,
                identificacao=identificacao,
                localizacao=localizacao,
                capacidade=capacidade,
                laboratorio_id=chefe.laboratorio_id,
                responsavel_usuario_id=responsavel
            )

            tx.contexto(chefe.id, "Cadastro de sala")

            return tx.recursos.salvar_sala(sala)

    def cadastrar_bancada(
        self,
        token: str,
        *,
        nome: str,
        numero_identificacao: str,
        sala_id: int,
        responsavel_id: int | None = None
    ) -> Bancada:

        with self._transacao() as tx:
            chefe = self._exigir_chefe(tx, token)

            sala = self._buscar_sala(
                tx, sala_id, chefe.laboratorio_id
            )

            responsavel = (
                chefe.id
                if responsavel_id is None
                else responsavel_id
            )

            self._validar_responsavel(
                tx, responsavel, chefe.laboratorio_id
            )

            bancada = Bancada(
                nome=nome,
                numero_identificacao=numero_identificacao,
                sala_id=sala_id,
                localizacao=sala.localizacao,
                laboratorio_id=chefe.laboratorio_id,
                responsavel_usuario_id=responsavel
            )

            tx.contexto(chefe.id, "Cadastro de bancada")

            return tx.recursos.salvar_bancada(bancada)

    def cadastrar_equipamento(
        self,
        token: str,
        *,
        nome: str,
        numero_patrimonio: str,
        complemento_local: str,
        bancada_id: int | None = None,
        sala_direta_id: int | None = None,
        foto_uri: str | None = None,
        observacao: str | None = None,
        responsavel_id: int | None = None
    ) -> Equipamento:

        with self._transacao() as tx:
            chefe = self._exigir_chefe(tx, token)

            if (
                (bancada_id is None)
                == (sala_direta_id is None)
            ):
                raise DadosInvalidos(
                    "Informe uma bancada ou uma sala, "
                    "mas não ambas."
                )

            if bancada_id is not None:
                if type(bancada_id) is not int or bancada_id <= 0:
                    raise DadosInvalidos(
                        "Selecione uma bancada válida."
                    )

                bancada = tx.recursos.buscar_bancada(
                    bancada_id
                )

                if (
                    bancada is None
                    or bancada.laboratorio_id != chefe.laboratorio_id
                ):
                    raise DadosInvalidos(
                        "Bancada não encontrada neste laboratório."
                    )

                sala = self._buscar_sala(
                    tx,
                    bancada.sala_id,
                    chefe.laboratorio_id
                )

            else:
                sala = self._buscar_sala(
                    tx,
                    sala_direta_id,
                    chefe.laboratorio_id
                )

            responsavel = (
                chefe.id
                if responsavel_id is None
                else responsavel_id
            )

            self._validar_responsavel(
                tx, responsavel, chefe.laboratorio_id
            )

            equipamento = Equipamento(
                nome=nome,
                numero_patrimonio=numero_patrimonio,
                localizacao=sala.localizacao,
                complemento_local=complemento_local,
                bancada_id=bancada_id,
                sala_direta_id=sala_direta_id,
                foto_uri=foto_uri,
                observacao=observacao,
                laboratorio_id=chefe.laboratorio_id,
                responsavel_usuario_id=responsavel
            )

            tx.contexto(chefe.id, "Cadastro de equipamento")

            return tx.recursos.salvar_equipamento(
                equipamento
            )


    
    @staticmethod
    def _buscar_equipamento(
        tx: UnidadeTrabalho,
        equipamento_id: int,
        laboratorio_id: int
    ) -> Equipamento:

        if (
            type(equipamento_id) is not int
            or equipamento_id <= 0
        ):
            raise DadosInvalidos(
                "Selecione um equipamento válido."
            )

        equipamento = next(
            (
                e
                for e in tx.recursos.listar_equipamentos(
                    laboratorio_id
                )
                if e.id == equipamento_id
            ),
            None
        )

        if (
            equipamento is None
            or equipamento.laboratorio_id != laboratorio_id
        ):
            raise DadosInvalidos(
                "Equipamento não encontrado neste laboratório."
            )

        return equipamento



    
    def vincular_equipamento(
        self,
        token: str,
        *,
        equipamento_id: int,
        bancada_id: int,
        complemento_local: str | None = None
    ) -> Equipamento:

        with self._transacao() as tx:

            # 1. Verifica se o usuário é Chefe.
            chefe = self._exigir_chefe(tx, token)

            # 2. Localiza o equipamento.
            equipamento = self._buscar_equipamento(
                tx,
                equipamento_id,
                chefe.laboratorio_id
            )

            # 3. Valida o identificador da bancada.
            if (
                type(bancada_id) is not int
                or bancada_id <= 0
            ):
                raise DadosInvalidos(
                    "Selecione uma bancada válida."
                )

            # 4. Localiza a bancada.
            bancada = tx.recursos.buscar_bancada(
                bancada_id
            )

            if (
                bancada is None
                or bancada.laboratorio_id
                != chefe.laboratorio_id
            ):
                raise DadosInvalidos(
                    "Bancada não encontrada neste laboratório."
                )

            # 5. Aplica as regras do domínio.
            atualizado = equipamento.vincular_a_bancada(
                bancada,
                complemento_local
            )

            # 6. Registra o contexto da operação.
            tx.contexto(
                chefe.id,
                "Vínculo de equipamento com bancada"
            )

            # 7. Persiste a alteração no PostgreSQL.
            tx.recursos.alterar_local_equipamento(
                chefe.id,
                atualizado
            )

            return atualizado


    
    def desvincular_equipamento(
        self,
        token: str,
        *,
        equipamento_id: int,
        complemento_local: str | None = None
    ) -> Equipamento:

        with self._transacao() as tx:

            # 1. Verifica se o usuário é Chefe.
            chefe = self._exigir_chefe(tx, token)

            # 2. Localiza o equipamento.
            equipamento = self._buscar_equipamento(
                tx,
                equipamento_id,
                chefe.laboratorio_id
            )

            # 3. Verifica se existe vínculo.
            if equipamento.bancada_id is None:
                raise DadosInvalidos(
                    "Este equipamento não está vinculado "
                    "a uma bancada."
                )

            # 4. Recupera a bancada atual.
            bancada = tx.recursos.buscar_bancada(
                equipamento.bancada_id
            )

            if (
                bancada is None
                or bancada.laboratorio_id
                != chefe.laboratorio_id
            ):
                raise DadosInvalidos(
                    "Bancada atual inválida neste laboratório."
                )

            # 5. Localiza a sala da bancada.
            sala = self._buscar_sala(
                tx,
                bancada.sala_id,
                chefe.laboratorio_id
            )

            # 6. Aplica as regras do domínio.
            atualizado = equipamento.desvincular_da_bancada(
                bancada,
                sala,
                complemento_local
            )

            # 7. Registra o contexto da operação.
            tx.contexto(
                chefe.id,
                "Desvínculo de equipamento de bancada"
            )

            # 8. Persiste a alteração.
            tx.recursos.alterar_local_equipamento(
                chefe.id,
                atualizado
            )

            return atualizado



    
    def responsaveis(self, token):
        with self._transacao() as tx:
            chefe = self._exigir_chefe(tx, token)
            return [u for u in tx.usuarios.listar(chefe.laboratorio_id) if isinstance(u, Professor) and u.ativo]

    def consultar_localizacao(self, token, equipamento_id):
        with self._transacao() as tx:
            chefe = self._exigir_chefe(tx, token)
            return self._buscar_equipamento(tx, equipamento_id, chefe.laboratorio_id)

    def alterar_localizacao(self, token, equipamento_id, *, bancada_id=None, sala_direta_id=None, complemento_local):
        with self._transacao() as tx:
            chefe = self._exigir_chefe(tx, token)
            equipamento = self._buscar_equipamento(tx, equipamento_id, chefe.laboratorio_id)
            if (bancada_id is None) == (sala_direta_id is None):
                raise DadosInvalidos("Informe uma bancada ou uma sala, mas não ambas.")
            if bancada_id is not None:
                if type(bancada_id) is not int or bancada_id <= 0:
                    raise DadosInvalidos("Selecione uma bancada válida.")
                bancada = tx.recursos.buscar_bancada(bancada_id)
                if bancada is None or bancada.laboratorio_id != chefe.laboratorio_id:
                    raise DadosInvalidos("Bancada não encontrada neste laboratório.")
                sala = self._buscar_sala(tx, bancada.sala_id, chefe.laboratorio_id)
            else:
                sala = self._buscar_sala(tx, sala_direta_id, chefe.laboratorio_id)
            atualizado = replace(equipamento, bancada_id=bancada_id, sala_direta_id=sala_direta_id,
                                  complemento_local=complemento_local, localizacao=sala.localizacao)
            tx.recursos.alterar_local_equipamento(chefe.id, atualizado)
            return atualizado

    def listar(self, token: str):
        with self._transacao() as tx:
            ator = self._autenticacao.identificar_na_transacao(tx, token)
            if ator is None:
                raise AcessoNegado("Entre novamente para continuar.")

            salas = tx.recursos.listar_salas(
                ator.laboratorio_id
            )

            bancadas = [
                bancada
                for sala in salas
                for bancada in sala.bancadas
            ]

            equipamentos = tx.recursos.listar_equipamentos(
                ator.laboratorio_id
            )

            return salas, bancadas, equipamentos



class ServicoReservas:
    """Coordena reservas autenticadas do laboratório."""

    def __init__(
        self,
        transacao: FabricaTransacao,
        autenticacao: ServicoAutenticacao
    ):
        self._transacao = transacao
        self._autenticacao = autenticacao

    def _identificar(
        self,
        tx: UnidadeTrabalho,
        token: str
    ):
        # Identifica o usuário pela sessão atual.
        ator = self._autenticacao.identificar_na_transacao(
            tx, token
        )

        if ator is None or ator.id is None or not ator.ativo:
            raise AcessoNegado(
                "Entre novamente para continuar."
            )

        # Verifica se o laboratório está ativo.
        laboratorio = tx.laboratorios.buscar_por_id(
            ator.laboratorio_id
        )

        if laboratorio is None or not laboratorio.ativo:
            raise AcessoNegado(
                "Laboratório inativo ou inexistente."
            )

        return ator, laboratorio

    @staticmethod


    def _buscar_recurso(
        tx: UnidadeTrabalho,
        recurso_id: int,
        laboratorio_id: int
    ):
        if type(recurso_id) is not int or recurso_id <= 0:
            raise DadosInvalidos(
                "Informe um recurso válido."
            )

        # Procura primeiro uma sala.
        recurso = tx.recursos.buscar_sala(recurso_id)

        # Se não encontrar, procura uma bancada.
        if recurso is None:
            recurso = tx.recursos.buscar_bancada(recurso_id)

        # Finalmente, procura um equipamento.
        if recurso is None:
            recurso = next(
                (
                    equipamento
                    for equipamento in
                    tx.recursos.listar_equipamentos(laboratorio_id)
                    if equipamento.id == recurso_id
                ),
                None
            )

        # Impede acesso a recursos de outro laboratório.
        if (
            recurso is None
            or recurso.laboratorio_id != laboratorio_id
        ):
            raise DadosInvalidos(
                "Recurso não encontrado neste laboratório."
            )

        return recurso


    
    def listar_recursos(self, token: str):
        """Lista os recursos do laboratório do usuário autenticado."""

        with self._transacao() as tx:
            _, laboratorio = self._identificar(tx, token)

            salas = tx.recursos.listar_salas(
                laboratorio.id
            )

            bancadas = [
                bancada
                for sala in salas
                for bancada in sala.bancadas
            ]

            equipamentos = tx.recursos.listar_equipamentos(
                laboratorio.id
            )

            return salas, bancadas, equipamentos





    @staticmethod
    def _validar_periodo(inicio, fim):
        for valor in (inicio, fim):
            if not isinstance(valor, datetime) or valor.utcoffset() is None:
                raise DadosInvalidos("Informe início e fim com fuso horário.")
        if fim <= inicio:
            raise DadosInvalidos("O fim deve ser posterior ao início.")
        if inicio < datetime.now(timezone.utc):
            raise DadosInvalidos("A reserva deve começar em um horário futuro.")

    def disponibilidade(self, token, inicio, fim):
        self._validar_periodo(inicio, fim)
        with self._transacao() as tx:
            ator, laboratorio = self._identificar(tx, token)
            if laboratorio.duracao_maxima_reserva is not None and fim - inicio > laboratorio.duracao_maxima_reserva:
                raise DadosInvalidos("A duração excede o limite do laboratório.")
            return tx.reservas.disponibilidade(laboratorio.id, ator.id, inicio, fim)

    def reservar(
        self,
        token: str,
        *,
        recurso_id: int,
        inicio: datetime,
        fim: datetime
    ) -> int:
        self._validar_periodo(inicio, fim)
        with self._transacao() as tx:
            # 1. Identifica quem está reservando.
            ator, laboratorio = self._identificar(
                tx, token
            )

            # 2. Localiza o recurso solicitado.
            recurso = self._buscar_recurso(
                tx,
                recurso_id,
                laboratorio.id
            )

            # 3. Cria o objeto de domínio para validação.
            reserva = Reserva(
                usuario_id=ator.id,
                laboratorio_id=laboratorio.id,
                recurso=recurso,
                inicio=inicio,
                fim=fim
            )

            # 4. Verifica a duração máxima configurada.
            if (
                laboratorio.duracao_maxima_reserva is not None
                and reserva.fim - reserva.inicio
                > laboratorio.duracao_maxima_reserva
            ):
                raise DadosInvalidos(
                    "A duração excede o limite do laboratório."
                )

            # 5. Registra o contexto da operação.
            tx.contexto(
                ator.id,
                "Criação de reserva"
            )

            # 6. Solicita a gravação ao repositório.
            return tx.reservas.criar(
                ator.id,
                recurso.id,
                reserva.inicio,
                reserva.fim
            )



    
    def listar(self, token: str) -> list[dict]:
        """Consulta reservas conforme as permissões do usuário."""

        with self._transacao() as tx:
            ator, laboratorio = self._identificar(
                tx, token
            )

            eh_chefe = (
                isinstance(ator, ChefeLaboratorio)
                and ator.id == laboratorio.chefe_usuario_id
            )

            return tx.reservas.listar(
                laboratorio.id,
                ator.id,
                eh_chefe
            )




    def cancelar(
        self,
        token: str,
        *,
        reserva_id: int,
        motivo: str
    ) -> None:

        # 1. Valida os dados recebidos.
        if type(reserva_id) is not int or reserva_id <= 0:
            raise DadosInvalidos(
                "Informe uma reserva válida."
            )

        if (
            not isinstance(motivo, str)
            or not motivo.strip()
        ):
            raise DadosInvalidos(
                "Informe o motivo do cancelamento."
            )

        # 2. Identifica o usuário autenticado.
        with self._transacao() as tx:
            ator, _ = self._identificar(tx, token)
            reserva = tx.reservas.buscar(reserva_id, ator.laboratorio_id)
            if reserva is None:
                raise DadosInvalidos("Reserva não encontrada neste laboratório.")
            if reserva["usuario_id"] != ator.id and not isinstance(ator, ChefeLaboratorio):
                raise AcessoNegado("Somente o titular ou o Chefe pode cancelar esta reserva.")
            if reserva["estado"] != "CONFIRMADA" or reserva["fim"] <= datetime.now(timezone.utc):
                raise DadosInvalidos("Esta reserva já está encerrada.")

            # 3. Registra o contexto da operação.
            tx.contexto(
                ator.id,
                "Cancelamento de reserva"
            )

            # 4. Solicita o cancelamento ao PostgreSQL.
            tx.reservas.cancelar(
                ator.id,
                reserva_id,
                motivo.strip()
            )





class ServicoConfiguracaoInicial:
    """Operações locais de instalação, acessíveis somente pelo terminal do operador."""

    def __init__(self, transacao: FabricaTransacao, senhas: ProtecaoSenha):
        self._transacao = transacao
        self._senhas = senhas

    def criar_chefe(self, laboratorio: str, localizacao: str, dados: DadosCadastro) -> ChefeLaboratorio:
        laboratorio = texto_obrigatorio(laboratorio, "Laboratório")
        localizacao = texto_obrigatorio(localizacao, "Localização", 200)
        senha_hash = self._senhas.gerar_hash(dados.senha)
        with self._transacao() as tx:
            # As FKs adiadas permitem criar Laboratório, Usuário, Professor e Chefe juntos.
            chefe_id = tx.usuarios.reservar_id()
            tx.contexto(None, "Configuração inicial de laboratório e Chefe")
            laboratorio_id = tx.laboratorios.criar(laboratorio, localizacao, chefe_id)
            chefe = ChefeLaboratorio(id=chefe_id, laboratorio_id=laboratorio_id, nome=dados.nome,
                                     email=dados.email, senha_hash=senha_hash,
                                     programa_pos=dados.programa_pos, ramal=dados.ramal)
            return tx.usuarios.salvar(chefe)

    def definir_senha(self, email: str, senha: str) -> None:
        email = normalizar_email(email)
        senha_hash = self._senhas.gerar_hash(senha)
        with self._transacao() as tx:
            usuario = tx.usuarios.buscar_por_email(email)
            if usuario is None:
                raise DadosInvalidos("Usuário não encontrado.")
            tx.contexto(None, "Redefinição de senha pelo operador local")
            tx.usuarios.alterar_senha(usuario.id, senha_hash)
            tx.sessoes.revogar_do_usuario(usuario.id)



class ServicoHistoricoUso:
    """Consulta o histórico respeitando as permissões."""

    def __init__(
        self,
        transacao: FabricaTransacao,
        autenticacao: ServicoAutenticacao
    ):
        self._transacao = transacao
        self._autenticacao = autenticacao

    def listar(
        self,
        token: str,
        *,
        usuario_id: int | None = None,
        recurso_id: int | None = None,
        desde: datetime | None = None,
        ate: datetime | None = None
    ) -> list[HistoricoUso]:

        # 1. Valida os identificadores dos filtros.
        for nome, valor in (
            ("usuário", usuario_id),
            ("recurso", recurso_id)
        ):
            if valor is not None and (
                type(valor) is not int or valor <= 0
            ):
                raise DadosInvalidos(
                    f"Identificador de {nome} inválido."
                )

        # 2. Valida os filtros de data e hora.
        for data in (desde, ate):
            if data is not None and (
                not isinstance(data, datetime)
                or data.tzinfo is None
                or data.utcoffset() is None
            ):
                raise DadosInvalidos(
                    "Informe datas com fuso horário."
                )

        if (
            desde is not None
            and ate is not None
            and desde >= ate
        ):
            raise DadosInvalidos(
                "O final do período deve ser posterior ao início."
            )

        with self._transacao() as tx:

            # 3. Identifica o usuário autenticado.
            ator = (
                self._autenticacao.identificar_na_transacao(
                    tx, token
                )
            )

            if (
                ator is None
                or ator.id is None
                or not ator.ativo
            ):
                raise AcessoNegado(
                    "Entre novamente para continuar."
                )

            # 4. Verifica o laboratório.
            laboratorio = tx.laboratorios.buscar_por_id(
                ator.laboratorio_id
            )

            if (
                laboratorio is None
                or not laboratorio.ativo
            ):
                raise AcessoNegado(
                    "Laboratório inativo ou inexistente."
                )

            # 5. Verifica se é o Chefe responsável.
            eh_chefe = (
                isinstance(ator, ChefeLaboratorio)
                and ator.id == laboratorio.chefe_usuario_id
            )

            # 6. Impede a consulta de reservas alheias.
            if (
                not eh_chefe
                and usuario_id is not None
                and usuario_id != ator.id
            ):
                raise AcessoNegado(
                    "Você só pode consultar o histórico "
                    "das suas próprias reservas."
                )

            # 7. Encaminha a consulta ao repositório.
            return tx.historico.listar(
                laboratorio.id,
                ator.id,
                eh_chefe,
                usuario_id=usuario_id,
                recurso_id=recurso_id,
                desde=desde,
                ate=ate
            )




class ServicoLimitesReserva:
    """Configuração de limites pelo Chefe de Laboratório."""

    def __init__(
        self,
        transacao: FabricaTransacao,
        autenticacao: ServicoAutenticacao
    ):
        self._transacao = transacao
        self._autenticacao = autenticacao

    def _exigir_chefe(
        self,
        tx: UnidadeTrabalho,
        token: str
    ):
        ator = self._autenticacao.identificar_na_transacao(
            tx, token
        )

        if (
            ator is None
            or not ator.ativo
            or not isinstance(ator, ChefeLaboratorio)
        ):
            raise AcessoNegado(
                "Somente o Chefe pode configurar os limites."
            )

        laboratorio = tx.laboratorios.buscar_por_id(
            ator.laboratorio_id
        )

        if (
            laboratorio is None
            or not laboratorio.ativo
            or laboratorio.chefe_usuario_id != ator.id
        ):
            raise AcessoNegado(
                "Chefe não autorizado neste laboratório."
            )

        return ator, laboratorio

    def consultar(self, token: str):
        """Retorna os limites atuais para o Chefe."""

        with self._transacao() as tx:
            _, laboratorio = self._exigir_chefe(
                tx, token
            )

            return laboratorio

    def configurar(
        self,
        token: str,
        *,
        duracao_minutos: int | None,
        quantidade: int | None
    ):
        """Valida e atualiza os limites de reserva."""

        # Validação da duração.
        if duracao_minutos is not None and (
            type(duracao_minutos) is not int
            or duracao_minutos <= 0
        ):
            raise DadosInvalidos(
                "Informe uma duração positiva em minutos."
            )

        # Validação da quantidade.
        if quantidade is not None and (
            type(quantidade) is not int
            or not 0 < quantidade <= 2147483647
        ):
            raise DadosInvalidos(
                "Informe uma quantidade positiva."
            )

        # Converte minutos para timedelta.
        try:
            duracao = (
                timedelta(minutes=duracao_minutos)
                if duracao_minutos is not None
                else None
            )
        except OverflowError as erro:
            raise DadosInvalidos(
                "A duração informada é muito grande."
            ) from erro

        with self._transacao() as tx:
            ator, laboratorio = self._exigir_chefe(
                tx, token
            )

            # Valida os limites no domínio.
            atualizado = laboratorio.configurar_limites(
                duracao,
                quantidade
            )

            # Registra o responsável e o motivo da alteração.
            tx.contexto(
                ator.id,
                "Configuração dos limites de reserva"
            )

            return tx.laboratorios.atualizar_limites(
                laboratorio.id,
                ator.id,
                atualizado.duracao_maxima_reserva,
                atualizado.max_reservas_simultaneas
            )
