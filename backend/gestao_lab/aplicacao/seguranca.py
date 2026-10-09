import hashlib
import hmac
import re
import secrets

from ..dominio.erros import DadosInvalidos


class ProtecaoSenha:
    """PBKDF2 da biblioteca padrão, com salt individual e parâmetros no hash."""

    ITERACOES = 600_000

    def gerar_hash(self, senha: str) -> str:
        if not 12 <= len(senha) <= 128:
            raise DadosInvalidos("A senha deve ter entre 12 e 128 caracteres.")
        salt = secrets.token_bytes(16)
        resumo = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt, self.ITERACOES)
        return f"pbkdf2_sha256${self.ITERACOES}${salt.hex()}${resumo.hex()}"

    def verificar(self, senha: str, senha_hash: str) -> bool:
        try:
            algoritmo, iteracoes, salt, esperado = senha_hash.split("$")
            if algoritmo != "pbkdf2_sha256" or not self.ITERACOES <= int(iteracoes) <= 1_200_000:
                return False
            if len(salt) != 32 or len(esperado) != 64 or len(senha) > 128:
                return False
            resumo = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(salt), int(iteracoes))
            return hmac.compare_digest(resumo, bytes.fromhex(esperado))
        except (ValueError, TypeError):
            return False


class TokensSessao:
    @staticmethod
    def gerar() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def formato_valido(token: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9_-]{43}", token))

    @staticmethod
    def resumir(token: str) -> bytes:
        return hashlib.sha256(token.encode()).digest()
