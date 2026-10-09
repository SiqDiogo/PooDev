from dataclasses import replace
from types import TracebackType
from typing import Self

import psycopg
from psycopg.rows import dict_row

from ..dominio.erros import CadastroDuplicado, DadosInvalidos, FalhaPersistencia
from ..dominio.repositorios import RepositorioLaboratorios, RepositorioSessoes, RepositorioUsuarios, Sessao, UnidadeTrabalho
from ..dominio.usuarios import Aluno, ChefeLaboratorio, Professor, Usuario


CONSULTA_USUARIOS = """
SELECT u.id, u.nome, u.email, u.senha_hash, u.laboratorio_id, u.ativo,
       p.programa_pos, p.ramal, a.matricula, a.tipo, a.orientador_usuario_id,
       c.usuario_id AS chefe_id
FROM gestao_lab.usuario u
LEFT JOIN gestao_lab.professor p ON p.usuario_id = u.id
LEFT JOIN gestao_lab.aluno a ON a.usuario_id = u.id
LEFT JOIN gestao_lab.chefe_laboratorio c ON c.usuario_id = u.id
"""


def reconstruir_usuario(row: dict) -> Usuario:
    base = {chave: row[chave] for chave in ("id", "nome", "email", "senha_hash", "laboratorio_id", "ativo")}
    if row["matricula"] is not None:
        return Aluno(**base, matricula=row["matricula"], tipo=row["tipo"], orientador_id=row["orientador_usuario_id"])
    classe = ChefeLaboratorio if row["chefe_id"] is not None else Professor
    return classe(**base, programa_pos=row["programa_pos"], ramal=row["ramal"])


class UsuariosPostgres(RepositorioUsuarios):
    def __init__(self, conexao):
        self._conexao = conexao

    def buscar_por_email(self, email):
        row = self._conexao.execute(CONSULTA_USUARIOS + " WHERE u.email = %s", (email,)).fetchone()
        return reconstruir_usuario(row) if row else None

    def buscar_por_id(self, usuario_id):
        row = self._conexao.execute(CONSULTA_USUARIOS + " WHERE u.id = %s", (usuario_id,)).fetchone()
        return reconstruir_usuario(row) if row else None

    def listar(self, laboratorio_id):
        rows = self._conexao.execute(CONSULTA_USUARIOS + " WHERE u.laboratorio_id = %s ORDER BY u.nome, u.id", (laboratorio_id,))
        return [reconstruir_usuario(row) for row in rows]

    def reservar_id(self):
        return self._conexao.execute("SELECT nextval(pg_get_serial_sequence('gestao_lab.usuario', 'id')) AS id").fetchone()["id"]

    def salvar(self, usuario):
        # Um mesmo ID liga a tabela base a Aluno ou Professor e, quando necessário, Chefe.
        usuario_id = usuario.id if usuario.id is not None else self.reservar_id()
        self._conexao.execute("""
            INSERT INTO gestao_lab.usuario(id, laboratorio_id, nome, email, senha_hash, ativo)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (usuario_id, usuario.laboratorio_id, usuario.nome, usuario.email, usuario.senha_hash, usuario.ativo))
        if isinstance(usuario, Professor):
            self._conexao.execute("""
                INSERT INTO gestao_lab.professor(usuario_id, laboratorio_id, programa_pos, ramal)
                VALUES (%s, %s, %s, %s)
            """, (usuario_id, usuario.laboratorio_id, usuario.programa_pos, usuario.ramal))
        if isinstance(usuario, Aluno):
            self._conexao.execute("""
                INSERT INTO gestao_lab.aluno(usuario_id, laboratorio_id, matricula, tipo, orientador_usuario_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (usuario_id, usuario.laboratorio_id, usuario.matricula, usuario.tipo.value, usuario.orientador_id))
        if isinstance(usuario, ChefeLaboratorio):
            self._conexao.execute("""
                INSERT INTO gestao_lab.chefe_laboratorio(usuario_id, laboratorio_id) VALUES (%s, %s)
            """, (usuario_id, usuario.laboratorio_id))
        return replace(usuario, id=usuario_id)

    def alterar_senha(self, usuario_id, senha_hash):
        self._conexao.execute("UPDATE gestao_lab.usuario SET senha_hash = %s WHERE id = %s", (senha_hash, usuario_id))


class LaboratoriosPostgres(RepositorioLaboratorios):
    def __init__(self, conexao):
        self._conexao = conexao

    def esta_ativo(self, laboratorio_id):
        row = self._conexao.execute("SELECT ativo FROM gestao_lab.laboratorio WHERE id = %s", (laboratorio_id,)).fetchone()
        return bool(row and row["ativo"])

    def criar(self, nome, localizacao, chefe_id):
        return self._conexao.execute("""
            INSERT INTO gestao_lab.laboratorio(nome, localizacao, chefe_usuario_id)
            VALUES (%s, %s, %s) RETURNING id
        """, (nome, localizacao, chefe_id)).fetchone()["id"]


class SessoesPostgres(RepositorioSessoes):
    def __init__(self, conexao):
        self._conexao = conexao

    def criar(self, usuario_id, token_hash, expira_em):
        self._conexao.execute("""
            INSERT INTO gestao_lab.sessao_usuario(usuario_id, token_hash, expira_em) VALUES (%s, %s, %s)
        """, (usuario_id, token_hash, expira_em))

    def buscar(self, token_hash):
        row = self._conexao.execute("""
            SELECT usuario_id, expira_em, revogado_em FROM gestao_lab.sessao_usuario WHERE token_hash = %s
        """, (token_hash,)).fetchone()
        return Sessao(**row) if row else None

    def revogar(self, token_hash):
        self._conexao.execute("""
            UPDATE gestao_lab.sessao_usuario SET revogado_em = clock_timestamp()
            WHERE token_hash = %s AND revogado_em IS NULL
        """, (token_hash,))

    def revogar_do_usuario(self, usuario_id):
        self._conexao.execute("""
            UPDATE gestao_lab.sessao_usuario SET revogado_em = clock_timestamp()
            WHERE usuario_id = %s AND revogado_em IS NULL
        """, (usuario_id,))


def traduzir_erro(erro: psycopg.Error) -> Exception:
    if erro.sqlstate == "23505":
        if erro.diag.constraint_name == "aluno_matricula_key":
            return CadastroDuplicado("Já existe um aluno com essa matrícula.")
        return CadastroDuplicado("Já existe um cadastro com esse e-mail ou identificador.")
    if erro.sqlstate in {"23503", "23514"}:
        return DadosInvalidos("Os dados não respeitam os vínculos ou regras do cadastro.")
    return FalhaPersistencia("Não foi possível concluir a operação no PostgreSQL. Verifique a conexão e a instalação do schema.")


class UnidadeTrabalhoPostgres(UnidadeTrabalho):
    def __init__(self, database_url: str):
        self._database_url = database_url
        self._conexao = None

    def __enter__(self) -> Self:
        try:
            self._conexao = psycopg.connect(self._database_url, row_factory=dict_row, cursor_factory=psycopg.ClientCursor, connect_timeout=5,
                                           options="-c search_path=gestao_lab,public -c lock_timeout=5000 -c statement_timeout=15000")
            self._conexao.isolation_level = psycopg.IsolationLevel.READ_COMMITTED
        except psycopg.Error as erro:
            if self._conexao is not None:
                self._conexao.close()
            raise traduzir_erro(erro) from erro
        self.usuarios = UsuariosPostgres(self._conexao)
        self.laboratorios = LaboratoriosPostgres(self._conexao)
        self.sessoes = SessoesPostgres(self._conexao)
        return self

    def contexto(self, ator_id, motivo):
        self._conexao.execute("SELECT gestao_lab.contexto_operacao(%s, %s)", (ator_id, motivo))

    def __exit__(self, tipo, erro, traceback) -> bool:
        try:
            if erro is None:
                self._conexao.commit()
            else:
                self._conexao.rollback()
        except psycopg.Error as falha:
            self._conexao.rollback()
            raise traduzir_erro(falha) from falha
        finally:
            self._conexao.close()
        if isinstance(erro, psycopg.Error):
            raise traduzir_erro(erro) from erro
        return False
