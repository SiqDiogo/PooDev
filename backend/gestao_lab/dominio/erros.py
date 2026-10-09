class ErroAplicacao(Exception):
    """Erro que pode ser explicado ao usuário sem expor detalhes do banco."""


class DadosInvalidos(ErroAplicacao):
    pass


class AcessoNegado(ErroAplicacao):
    pass


class CredenciaisInvalidas(ErroAplicacao):
    pass


class CadastroDuplicado(ErroAplicacao):
    pass


class FalhaPersistencia(ErroAplicacao):
    pass
