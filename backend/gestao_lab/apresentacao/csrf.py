import hashlib
import hmac
import secrets
import time


class ProtecaoCSRF:
    def __init__(self, segredo: bytes):
        self._segredo = segredo

    def _assinar(self, valor: str) -> str:
        return hmac.new(self._segredo, valor.encode(), hashlib.sha256).hexdigest()

    def emitir_login(self) -> str:
        valor = f"{secrets.token_urlsafe(32)}.{int(time.time())}"
        return f"{valor}.{self._assinar('login:' + valor)}"

    def validar_login(self, cookie: str, campo: str) -> bool:
        if not cookie or not cookie.isascii() or not campo.isascii() or not hmac.compare_digest(cookie, campo):
            return False
        try:
            nonce, instante, assinatura = cookie.split(".")
            idade = time.time() - int(instante)
            return (len(nonce) == 43 and 0 <= idade <= 900
                    and hmac.compare_digest(assinatura, self._assinar(f"login:{nonce}.{instante}")))
        except ValueError:
            return False

    def para_sessao(self, token: str) -> str:
        return self._assinar("sessao:" + token)

    def validar_sessao(self, token: str, campo: str) -> bool:
        return bool(token and campo.isascii() and hmac.compare_digest(self.para_sessao(token), campo))
