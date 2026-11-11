from ..dominio.protocolos import Protocolo, VinculoEquipamento
from ..dominio.repositorios import RepositorioProtocolos


class ProtocolosPostgres(RepositorioProtocolos):
    """Persistência das versões originais em bytea, sem transformação do PDF."""

    _BASE = """
        SELECT p.id, p.laboratorio_id, p.titulo, p.nome_arquivo,
               p.autor_id, u.nome AS autor_nome, p.estado::text AS estado,
               p.criado_em, p.assinado_em, p.validado_em
        FROM gestao_lab.protocolo p
        JOIN gestao_lab.usuario u ON u.id = p.autor_id
    """

    def __init__(self, conexao):
        self._conexao = conexao

    @staticmethod
    def _modelo(linha, vinculos=()):
        return Protocolo(**linha, vinculos=tuple(vinculos))

    def listar(self, laboratorio_id):
        linhas = self._conexao.execute(
            self._BASE + """
            WHERE p.laboratorio_id = %s
            ORDER BY p.criado_em DESC, p.id DESC
            LIMIT 200
            """, (laboratorio_id,)
        ).fetchall()
        return [self._modelo(linha) for linha in linhas]

    def buscar(self, protocolo_id, laboratorio_id):
        linha = self._conexao.execute(
            self._BASE + " WHERE p.id = %s AND p.laboratorio_id = %s",
            (protocolo_id, laboratorio_id)
        ).fetchone()
        if linha is None:
            return None
        associados = self._conexao.execute("""
            SELECT pe.equipamento_id, r.nome, e.numero_patrimonio AS patrimonio
            FROM gestao_lab.protocolo_equipamento pe
            JOIN gestao_lab.equipamento e ON e.recurso_id = pe.equipamento_id
            JOIN gestao_lab.recurso r ON r.id = pe.equipamento_id
            WHERE pe.protocolo_id = %s AND pe.laboratorio_id = %s
            ORDER BY r.nome, e.numero_patrimonio
        """, (protocolo_id, laboratorio_id)).fetchall()
        return self._modelo(linha, (VinculoEquipamento(**r) for r in associados))

    def criar(self, laboratorio_id, autor_id, titulo, nome_arquivo, pdf_original):
        resultado = self._conexao.execute("""
            INSERT INTO gestao_lab.protocolo (
                laboratorio_id, titulo, autor_id, nome_arquivo, pdf_original
            ) VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (laboratorio_id, titulo, autor_id, nome_arquivo, pdf_original))
        return resultado.fetchone()["id"]

    def assinar(self, autor_id, protocolo_id):
        self._conexao.execute(
            "SELECT gestao_lab.assinar_protocolo(%s, %s)",
            (autor_id, protocolo_id)
        )

    def validar(self, chefe_id, protocolo_id):
        self._conexao.execute(
            "SELECT gestao_lab.validar_protocolo(%s, %s)",
            (chefe_id, protocolo_id)
        )

    def vincular(self, protocolo_id, equipamento_id, laboratorio_id, chefe_id):
        self._conexao.execute("""
            INSERT INTO gestao_lab.protocolo_equipamento (
                protocolo_id, equipamento_id, laboratorio_id, vinculado_por
            ) VALUES (%s, %s, %s, %s)
            ON CONFLICT (protocolo_id, equipamento_id) DO NOTHING
        """, (protocolo_id, equipamento_id, laboratorio_id, chefe_id))

    def arquivo(self, protocolo_id, laboratorio_id):
        linha = self._conexao.execute("""
            SELECT nome_arquivo, pdf_original
            FROM gestao_lab.protocolo
            WHERE id = %s AND laboratorio_id = %s
        """, (protocolo_id, laboratorio_id)).fetchone()
        return (linha["nome_arquivo"], bytes(linha["pdf_original"])) if linha else None
