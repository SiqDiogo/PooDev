from ..dominio.chaves import CondicaoChave, identificador
from ..dominio.erros import AcessoNegado, DadosInvalidos
from ..dominio.usuarios import texto_obrigatorio


class ServicoChaves:
    def __init__(self, transacao, autenticacao):
        self._transacao = transacao
        self._autenticacao = autenticacao

    def _ator(self, tx, token):
        ator = self._autenticacao.identificar_na_transacao(tx, token)
        if ator is None:
            raise AcessoNegado("Entre novamente para continuar.")
        return ator

    def _copia(self, tx, ator, chave_id, *, gerir=False):
        copia = tx.chaves.buscar(identificador(chave_id), ator.laboratorio_id)
        if copia is None:
            raise DadosInvalidos("Cópia não encontrada neste laboratório.")
        if gerir:
            copia.destino.exigir_gestor(ator)
        return copia

    @staticmethod
    def _destinatario(tx, ator, usuario_id):
        if usuario_id is not None:
            usuario = tx.usuarios.buscar_por_id(identificador(usuario_id))
            if usuario is None or not usuario.ativo or usuario.laboratorio_id != ator.laboratorio_id:
                raise DadosInvalidos("Designe a cópia a um usuário ativo do mesmo laboratório.")

    def painel(self, token):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            destinos = [d for d in tx.chaves.destinos(ator.laboratorio_id) if d.pode_gerenciar(ator)]
            copias = [c for c in tx.chaves.listar(ator.laboratorio_id)
                      if c.destino.pode_gerenciar(ator) or c.designada_para in (None, ator.id) or c.portador_id == ator.id]
            emprestimos = [e for e in tx.chaves.emprestimos(ator.laboratorio_id)
                          if e.usuario_id == ator.id or e.destino.pode_gerenciar(ator)]
            return copias, destinos, emprestimos

    def dados_cadastro(self, token):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            destinos = [d for d in tx.chaves.destinos(ator.laboratorio_id) if d.pode_gerenciar(ator)]
            if not destinos:
                raise AcessoNegado("Cadastre um local sob sua responsabilidade ou solicite o cadastro da chave ao responsável.")
            usuarios = [u for u in tx.usuarios.listar(ator.laboratorio_id) if u.ativo]
            return destinos, usuarios

    def cadastrar(self, token, *, codigo_copia, destino_id, designada_para=None):
        codigo = texto_obrigatorio(codigo_copia, "Código da cópia", 80)
        identificador(destino_id)
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            destino = next((d for d in tx.chaves.destinos(ator.laboratorio_id) if d.id == destino_id), None)
            if destino is None:
                raise DadosInvalidos("Selecione uma sala ou bancada deste laboratório.")
            destino.exigir_gestor(ator)
            self._destinatario(tx, ator, designada_para)
            tx.contexto(ator.id, "Cadastro e designação de cópia de chave")
            chave_id = tx.chaves.criar(codigo, destino, ator.id, designada_para)
            return self._copia(tx, ator, chave_id)

    def consultar_gestao(self, token, chave_id):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            copia = self._copia(tx, ator, chave_id, gerir=True)
            usuarios = [u for u in tx.usuarios.listar(ator.laboratorio_id) if u.ativo]
            return copia, usuarios

    def designar(self, token, chave_id, designada_para=None):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            copia = self._copia(tx, ator, chave_id, gerir=True)
            self._destinatario(tx, ator, designada_para)
            tx.contexto(ator.id, "Alteração da designação de cópia de chave")
            tx.chaves.designar(copia.id, ator.id, designada_para)

    def opcoes_retirada(self, token, chave_id):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            copia = self._copia(tx, ator, chave_id, gerir=True)
            if copia.estado != "DISPONIVEL":
                raise DadosInvalidos("Esta cópia não está disponível para retirada.")
            return copia, tx.chaves.reservas_autorizadas(copia)

    def retirar(self, token, chave_id, reserva_id):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            copia = self._copia(tx, ator, chave_id, gerir=True)
            reserva = tx.reservas.buscar(identificador(reserva_id), ator.laboratorio_id)
            if reserva is None:
                raise DadosInvalidos("Reserva não encontrada neste laboratório.")
            # O portador é o dono da reserva; o entregador vem da sessão.
            # As funções SQL repetem a validação sob lock durante a gravação.
            return tx.chaves.retirar(reserva["usuario_id"], reserva["id"], copia.id, ator.id)

    def consultar_devolucao(self, token, emprestimo_id):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            emprestimo = tx.chaves.buscar_emprestimo(identificador(emprestimo_id), ator.laboratorio_id)
            if emprestimo is None:
                raise DadosInvalidos("Empréstimo não encontrado neste laboratório.")
            emprestimo.destino.exigir_gestor(ator)
            if emprestimo.devolucao_em is not None:
                raise DadosInvalidos("Este empréstimo já foi devolvido.")
            return emprestimo

    def devolver(self, token, emprestimo_id):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            emprestimo = tx.chaves.buscar_emprestimo(identificador(emprestimo_id), ator.laboratorio_id)
            if emprestimo is None:
                raise DadosInvalidos("Empréstimo não encontrado neste laboratório.")
            emprestimo.destino.exigir_gestor(ator)
            tx.chaves.devolver(emprestimo.id, ator.id)

    def registrar_ocorrencia(self, token, chave_id, *, condicao, descricao):
        try:
            condicao = CondicaoChave(condicao)
        except (ValueError, TypeError) as erro:
            raise DadosInvalidos("Selecione uma condição válida para a chave.") from erro
        descricao = texto_obrigatorio(descricao, "Descrição da ocorrência", 500)
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            copia = self._copia(tx, ator, chave_id, gerir=True)
            tx.chaves.registrar_ocorrencia(ator.id, copia.id, condicao.value, descricao)

