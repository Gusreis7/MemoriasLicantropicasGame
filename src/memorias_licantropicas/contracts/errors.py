"""Erros de domínio e integração sem detalhes de credenciais/provedor."""


class NotFoundError(Exception):
    pass


class AccessDeniedError(Exception):
    pass


class ConflictError(Exception):
    pass


class StorageUnavailableError(Exception):
    pass


class LLMUnavailableError(Exception):
    pass
