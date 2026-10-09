from dataclasses import dataclass, field
import os
import secrets

from ..dominio.erros import DadosInvalidos


@dataclass(frozen=True)
class Configuracao:
    database_url: str = field(repr=False)
    segredo_csrf: bytes = field(repr=False)
    porta: int = 8000
    horas_sessao: int = 8

    @classmethod
    def do_ambiente(cls):
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            raise DadosInvalidos("Defina DATABASE_URL para o PostgreSQL antes de executar.")
        try:
            porta = int(os.environ.get("APP_PORT", "8000"))
            horas = int(os.environ.get("SESSION_HOURS", "8"))
        except ValueError as erro:
            raise DadosInvalidos("APP_PORT e SESSION_HOURS devem ser números inteiros.") from erro
        if not 1 <= porta <= 65535 or not 1 <= horas <= 24:
            raise DadosInvalidos("Porta inválida ou duração da sessão fora de 1 a 24 horas.")
        segredo = os.environ.get("APP_SECRET", "")
        if segredo and len(segredo) < 32:
            raise DadosInvalidos("APP_SECRET deve ter pelo menos 32 caracteres.")
        return cls(url, segredo.encode() if segredo else secrets.token_bytes(32), porta, horas)
