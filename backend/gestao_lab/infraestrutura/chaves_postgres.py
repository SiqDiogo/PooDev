from ..dominio.chaves import CopiaChave, DestinoChave, EmprestimoChave, ReservaAutorizada
from ..dominio.repositorios import RepositorioChaves
from ..dominio.historico import HistoricoUso


DESTINO_COLUNAS = """
    r.id AS destino_id, r.laboratorio_id, r.nome AS destino_nome,
    r.tipo::text AS destino_tipo, r.responsavel_usuario_id AS responsavel_id,
    concat_ws(' / ', v.sala_localizacao, v.sala_identificacao, v.bancada_identificacao) AS local
"""


def reconstruir_destino(linha):
    return DestinoChave(id=linha["destino_id"], laboratorio_id=linha["laboratorio_id"],
                        nome=linha["destino_nome"], tipo=linha["destino_tipo"],
                        local=linha["local"], responsavel_id=linha["responsavel_id"])


class ChavesPostgres(RepositorioChaves):
    def __init__(self, conexao):
        self._conexao = conexao

    def destinos(self, laboratorio_id):
        linhas = self._conexao.execute(f"""
            SELECT {DESTINO_COLUNAS} FROM gestao_lab.recurso r
            JOIN gestao_lab.vw_local_recurso v ON v.recurso_id=r.id
            WHERE r.laboratorio_id=%s AND r.tipo IN ('SALA','BANCADA') ORDER BY r.tipo, r.nome, r.id
        """, (laboratorio_id,)).fetchall()
        return [reconstruir_destino(linha) for linha in linhas]

    _COPIAS = f"""
        SELECT c.id, c.codigo_copia, c.estado, c.condicao::text AS condicao,
               c.designada_para, d.nome AS designada_nome,
               c.portador_usuario_id AS portador_id, p.nome AS portador_nome,
               c.emprestimo_aberto_id, {DESTINO_COLUNAS}
        FROM gestao_lab.vw_chave_estado c
        JOIN gestao_lab.recurso r ON r.id=coalesce(c.sala_id,c.bancada_id)
        JOIN gestao_lab.vw_local_recurso v ON v.recurso_id=r.id
        LEFT JOIN gestao_lab.usuario d ON d.id=c.designada_para
        LEFT JOIN gestao_lab.usuario p ON p.id=c.portador_usuario_id
    """

    @staticmethod
    def _copia(linha):
        return CopiaChave(**{k: linha[k] for k in (
            "id", "codigo_copia", "estado", "condicao", "designada_para", "designada_nome",
            "portador_id", "portador_nome", "emprestimo_aberto_id")}, destino=reconstruir_destino(linha))

    def listar(self, laboratorio_id):
        linhas = self._conexao.execute(self._COPIAS + " WHERE c.laboratorio_id=%s ORDER BY c.codigo_copia,c.id", (laboratorio_id,)).fetchall()
        return [self._copia(linha) for linha in linhas]

    def buscar(self, chave_id, laboratorio_id):
        linha = self._conexao.execute(self._COPIAS + " WHERE c.id=%s AND c.laboratorio_id=%s", (chave_id, laboratorio_id)).fetchone()
        return self._copia(linha) if linha else None

    def criar(self, codigo, destino, ator_id, designada_para):
        return self._conexao.execute("""
            INSERT INTO gestao_lab.chave(laboratorio_id,codigo_copia,sala_id,bancada_id,designada_por,designada_para)
            VALUES (%s,%s,%s,%s,%s,%s) RETURNING id
        """, (destino.laboratorio_id, codigo, destino.id if destino.tipo == "SALA" else None,
              destino.id if destino.tipo == "BANCADA" else None, ator_id, designada_para)).fetchone()["id"]

    def designar(self, chave_id, ator_id, designada_para):
        self._conexao.execute("UPDATE gestao_lab.chave SET designada_por=%s,designada_para=%s WHERE id=%s",
                              (ator_id, designada_para, chave_id))

    def reservas_autorizadas(self, copia):
        linhas = self._conexao.execute("""
            SELECT r.id, u.nome AS usuario_nome, p.nome AS recurso_nome, r.inicio, r.fim
            FROM gestao_lab.reserva r
            JOIN gestao_lab.usuario u ON u.id=r.usuario_id
            JOIN gestao_lab.recurso p ON p.id=r.recurso_principal_id
            WHERE r.laboratorio_id=%s AND r.estado='CONFIRMADA' AND r.fim>clock_timestamp() AND u.ativo
              AND (%s::bigint IS NULL OR r.usuario_id=%s)
              AND EXISTS (SELECT 1 FROM gestao_lab.reserva_recurso rr
                  CROSS JOIN LATERAL gestao_lab.recursos_ancestrais(rr.recurso_id) a
                  WHERE rr.reserva_id=r.id AND a.recurso_id=%s)
            ORDER BY r.inicio, r.id
        """, (copia.destino.laboratorio_id, copia.designada_para, copia.designada_para, copia.destino.id)).fetchall()
        return [ReservaAutorizada(**linha) for linha in linhas]

    _EMPRESTIMOS = f"""
        SELECT e.id, e.chave_id, c.codigo_copia, e.usuario_id, u.nome AS usuario_nome, e.reserva_id,
               e.retirada_em, t.nome AS entregue_nome, e.devolucao_em, d.nome AS recebido_nome, {DESTINO_COLUNAS}
        FROM gestao_lab.emprestimo_chave e
        JOIN gestao_lab.chave c ON c.id=e.chave_id
        JOIN gestao_lab.recurso r ON r.id=coalesce(c.sala_id,c.bancada_id)
        JOIN gestao_lab.vw_local_recurso v ON v.recurso_id=r.id
        JOIN gestao_lab.usuario u ON u.id=e.usuario_id
        JOIN gestao_lab.usuario t ON t.id=e.entregue_por
        LEFT JOIN gestao_lab.usuario d ON d.id=e.recebido_por
    """

    @staticmethod
    def _emprestimo(linha):
        return EmprestimoChave(**{k: linha[k] for k in (
            "id", "chave_id", "codigo_copia", "usuario_id", "usuario_nome", "reserva_id",
            "retirada_em", "entregue_nome", "devolucao_em", "recebido_nome")}, destino=reconstruir_destino(linha))

    def emprestimos(self, laboratorio_id):
        linhas = self._conexao.execute(self._EMPRESTIMOS + " WHERE e.laboratorio_id=%s ORDER BY e.retirada_em DESC,e.id DESC", (laboratorio_id,)).fetchall()
        return [self._emprestimo(linha) for linha in linhas]

    def buscar_emprestimo(self, emprestimo_id, laboratorio_id):
        linha = self._conexao.execute(self._EMPRESTIMOS + " WHERE e.id=%s AND e.laboratorio_id=%s", (emprestimo_id, laboratorio_id)).fetchone()
        return self._emprestimo(linha) if linha else None

    def retirar(self, usuario_id, reserva_id, chave_id, ator_id):
        return self._conexao.execute("SELECT gestao_lab.retirar_chave(%s,%s,%s,%s) AS id",
                                      (usuario_id, reserva_id, chave_id, ator_id)).fetchone()["id"]

    def devolver(self, emprestimo_id, ator_id):
        self._conexao.execute("SELECT gestao_lab.devolver_chave(%s,%s)", (emprestimo_id, ator_id))

    def registrar_ocorrencia(self, ator_id, chave_id, condicao, descricao):
        self._conexao.execute("SELECT gestao_lab.registrar_ocorrencia_chave(%s,%s,%s,%s)", (ator_id, chave_id, condicao, descricao))


class ConsultaHistoricoSemana4:
    def __init__(self, conexao):
        self._conexao = conexao

    def listar(self, laboratorio_id, *, usuario_id=None, recurso_id=None, inicio=None, fim=None):
        consulta = """
            SELECT h.*, coalesce(a.nome,'Sistema') AS ator_nome,
                   coalesce(ur.nome,ue.nome,ud.nome,'—') AS usuario_nome,
                   ua.nome AS designada_anterior, ud.nome AS designada_atual,
                   coalesce(r.id,ec.reserva_id) AS reserva_id,
                   coalesce(rec.nome,'Configuração do laboratório') AS recurso_nome,
                   c.codigo_copia
            FROM gestao_lab.historico_uso h
            LEFT JOIN gestao_lab.usuario a ON a.id=h.ator_id
            LEFT JOIN gestao_lab.reserva r ON h.tabela='reserva' AND r.id::text=h.registro_id
            LEFT JOIN gestao_lab.emprestimo_chave ec ON h.tabela='emprestimo_chave' AND ec.id::text=h.registro_id
            LEFT JOIN gestao_lab.ocorrencia_chave oc ON h.tabela='ocorrencia_chave' AND oc.id::text=h.registro_id
            LEFT JOIN gestao_lab.chave c ON c.id=CASE WHEN h.tabela='chave' THEN h.registro_id::bigint
                ELSE coalesce(ec.chave_id,oc.chave_id) END
            LEFT JOIN gestao_lab.equipamento eq ON h.tabela='equipamento' AND eq.recurso_id::text=h.registro_id
            LEFT JOIN gestao_lab.recurso rec ON rec.id=coalesce(r.recurso_principal_id,c.sala_id,c.bancada_id,eq.recurso_id)
            LEFT JOIN gestao_lab.usuario ur ON ur.id=r.usuario_id
            LEFT JOIN gestao_lab.usuario ue ON ue.id=ec.usuario_id
            LEFT JOIN gestao_lab.usuario ud ON h.tabela='chave' AND ud.id=(h.depois->>'designada_para')::bigint
            LEFT JOIN gestao_lab.usuario ua ON h.tabela='chave' AND ua.id=(h.antes->>'designada_para')::bigint
            WHERE h.laboratorio_id=%s AND (
                h.tabela IN ('reserva','emprestimo_chave','ocorrencia_chave')
                OR h.tabela='chave' AND (h.acao='INSERT' OR h.antes->'designada_para' IS DISTINCT FROM h.depois->'designada_para')
                OR h.tabela='equipamento' AND h.acao='UPDATE' AND
                   (h.antes->'bancada_id',h.antes->'sala_direta_id',h.antes->'complemento_local') IS DISTINCT FROM
                   (h.depois->'bancada_id',h.depois->'sala_direta_id',h.depois->'complemento_local')
                OR h.tabela='laboratorio' AND h.acao='UPDATE' AND
                   (h.antes->'duracao_maxima_reserva',h.antes->'max_reservas_simultaneas') IS DISTINCT FROM
                   (h.depois->'duracao_maxima_reserva',h.depois->'max_reservas_simultaneas'))
        """
        parametros = [laboratorio_id]
        if usuario_id is not None:
            consulta += """
                AND (h.ator_id=%s OR r.usuario_id=%s OR ec.usuario_id=%s
                     OR h.tabela='chave' AND (%s IN ((h.antes->>'designada_para')::bigint,(h.depois->>'designada_para')::bigint))
                     OR oc.id IS NOT NULL AND EXISTS (SELECT 1 FROM gestao_lab.emprestimo_chave eh
                         WHERE eh.chave_id=oc.chave_id AND eh.usuario_id=%s AND eh.retirada_em<=oc.criado_em
                           AND (eh.devolucao_em IS NULL OR eh.devolucao_em>=oc.criado_em))
                     OR eq.recurso_id IS NOT NULL AND EXISTS (SELECT 1 FROM gestao_lab.reserva rh
                         JOIN gestao_lab.reserva_recurso rrh ON rrh.reserva_id=rh.id
                         WHERE rh.usuario_id=%s AND rrh.recurso_id=eq.recurso_id AND rh.criado_em<=h.registrado_em))
            """
            parametros.extend([usuario_id] * 6)
        if recurso_id is not None:
            consulta += """
                AND (EXISTS (SELECT 1 FROM gestao_lab.reserva_recurso rr WHERE rr.reserva_id=r.id AND rr.recurso_id=%s)
                     OR EXISTS (SELECT 1 FROM gestao_lab.reserva_recurso rr WHERE rr.reserva_id=ec.reserva_id AND rr.recurso_id=%s)
                     OR c.id IS NOT NULL AND EXISTS (SELECT 1 FROM gestao_lab.recursos_ancestrais(coalesce(c.sala_id,c.bancada_id)) ca WHERE ca.recurso_id=%s)
                     OR eq.recurso_id IS NOT NULL AND %s=ANY(ARRAY[eq.recurso_id,
                         (h.antes->>'bancada_id')::bigint,(h.depois->>'bancada_id')::bigint,
                         (h.antes->>'sala_direta_id')::bigint,(h.depois->>'sala_direta_id')::bigint,
                         (SELECT sala_id FROM gestao_lab.bancada WHERE recurso_id=(h.antes->>'bancada_id')::bigint),
                         (SELECT sala_id FROM gestao_lab.bancada WHERE recurso_id=(h.depois->>'bancada_id')::bigint)]))
            """
            parametros.extend([recurso_id] * 4)
        if inicio is not None:
            consulta += " AND h.registrado_em>=%s"
            parametros.append(inicio)
        if fim is not None:
            consulta += " AND h.registrado_em<%s"
            parametros.append(fim)
        linhas = self._conexao.execute(consulta + " ORDER BY h.registrado_em DESC,h.id DESC LIMIT 100", parametros).fetchall()
        locais = {r["recurso_id"]: r["local"] for r in self._conexao.execute("""
            SELECT recurso_id, concat_ws(' / ',sala_localizacao,sala_identificacao,bancada_identificacao) AS local
            FROM gestao_lab.vw_local_recurso WHERE laboratorio_id=%s
        """, (laboratorio_id,)).fetchall()}
        return [self._evento(linha, locais) for linha in linhas]

    @staticmethod
    def _evento(linha, locais):
        antes, depois = linha["antes"] or {}, linha["depois"] or {}
        tabela = linha["tabela"]
        detalhes = ""
        if tabela == "reserva":
            acao = {"CONFIRMADA": "Reserva confirmada", "CANCELADA": "Reserva cancelada", "CONCLUIDA": "Reserva concluída"}[depois["estado"]]
            detalhes = f'Reserva #{linha["reserva_id"]}'
        elif tabela == "emprestimo_chave":
            acao = "Retirada de chave" if linha["acao"] == "INSERT" else "Devolução de chave"
            detalhes = f'{linha["codigo_copia"]} — Reserva #{linha["reserva_id"]}'
        elif tabela == "ocorrencia_chave":
            acao = "Ocorrência de chave"
            detalhes = f'{linha["codigo_copia"]} — {depois["condicao"]}: {depois["descricao"]}'
        elif tabela == "chave":
            acao = "Cópia cadastrada" if linha["acao"] == "INSERT" else "Designação de chave"
            detalhes = f'{linha["codigo_copia"]} — {linha["designada_anterior"] or "Compartilhada"} → {linha["designada_atual"] or "Compartilhada"}'
        elif tabela == "equipamento":
            acao = "Localização alterada"
            def local(dados):
                destino = dados.get("bancada_id") or dados.get("sala_direta_id")
                return f'{locais.get(destino, "Local anterior")}/{dados.get("complemento_local", "")}'
            detalhes = f'{local(antes)} → {local(depois)}'
        else:
            acao = "Limites de reserva alterados"
            detalhes = f'Duração: {depois.get("duracao_maxima_reserva") or "sem limite"}; simultâneas: {depois.get("max_reservas_simultaneas") or "sem limite"}'
        return HistoricoUso(**{k: linha[k] for k in ("id", "laboratorio_id", "tabela", "registro_id", "acao", "registrado_em", "ator_id", "motivo", "antes", "depois")},
            ator_nome=linha["ator_nome"], recurso_nome=linha["recurso_nome"], usuario_nome=linha["usuario_nome"], descricao=f"{acao} — {detalhes}")
