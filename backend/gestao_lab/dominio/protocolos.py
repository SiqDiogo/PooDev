from dataclasses import dataclass
from datetime import datetime

from .erros import DadosInvalidos
from .usuarios import texto_obrigatorio


LIMITE_PDF_BYTES = 5 * 1024 * 1024


def validar_documento_pdf(titulo: str, nome_arquivo: str, conteudo: bytes) -> tuple[str, str]:
    """Valida o anexo sem modificar seus bytes, preservados para download."""
    if not isinstance(titulo, str):
        raise DadosInvalidos("Informe o título do protocolo.")
    titulo = texto_obrigatorio(titulo, "Título do protocolo", 180)
    if not isinstance(nome_arquivo, str) or not nome_arquivo:
        raise DadosInvalidos("Selecione um arquivo PDF.")
    # O nome é informativo e nunca será usado como caminho no servidor.
    if (len(nome_arquivo) > 180 or nome_arquivo in {".", ".."}
            or any(c in nome_arquivo for c in "/\\\r\n\x00")
            or not nome_arquivo.lower().endswith(".pdf")):
        raise DadosInvalidos("O arquivo deve ter um nome válido terminado em .pdf.")
    if not isinstance(conteudo, bytes) or not 5 < len(conteudo) <= LIMITE_PDF_BYTES:
        raise DadosInvalidos("O PDF deve ter até 5 MB e não pode estar vazio.")
    if not conteudo.startswith(b"%PDF-"):
        raise DadosInvalidos("O arquivo selecionado não é um PDF válido.")
    return titulo, nome_arquivo


@dataclass(frozen=True)
class VinculoEquipamento:
    equipamento_id: int
    nome: str
    patrimonio: str


@dataclass(frozen=True)
class Protocolo:
    id: int
    laboratorio_id: int
    titulo: str
    nome_arquivo: str
    autor_id: int
    autor_nome: str
    estado: str
    criado_em: datetime
    assinado_em: datetime | None
    validado_em: datetime | None
    vinculos: tuple[VinculoEquipamento, ...] = ()

    @property
    def assinado(self) -> bool:
        return self.assinado_em is not None

    @property
    def validado(self) -> bool:
        return self.estado == "VALIDADO"
