"""Erros de domínio e integração sem detalhes de credenciais/provedor."""


class NotFoundError(Exception):
    pass


class AccessDeniedError(Exception):
    pass


class ConflictError(Exception):
    pass


class DossierSelectionError(ConflictError):
    """Fixed public diagnostic; never exposes arbitrary exception text."""
    code = "dossier_missing_evidence"
    detail = "Um depoimento precisa acompanhar seu vestígio na acusação."

    def __init__(self):
        super().__init__(self.detail)


class StorageUnavailableError(Exception):
    pass


LLM_PUBLIC_DETAILS = {
    "llm_unavailable": "O serviço de diálogo está temporariamente indisponível.",
    "llm_credentials_missing": "O serviço de diálogo está sem autenticação configurada no servidor.",
    "llm_credentials_unavailable": "A autenticação do serviço de diálogo precisa ser renovada no servidor.",
    "llm_authentication_failed": "O serviço de diálogo recusou a autenticação do servidor.",
    "llm_rate_limited": "O serviço de diálogo atingiu o limite de uso. Aguarde antes de tentar novamente.",
    "llm_timeout": "O serviço de diálogo demorou além do limite para responder.",
    "llm_invalid_response": "O personagem não retornou uma resposta válida desta vez.",
    "llm_response_truncated": "A resposta do personagem foi interrompida antes de terminar.",
    "llm_model_unavailable": "O modelo de diálogo configurado está indisponível no servidor.",
}


class LLMUnavailableError(Exception):
    def __init__(self, message: str, *, code: str = "llm_unavailable"):
        super().__init__(message)
        # Somente códigos conhecidos podem atravessar a fronteira HTTP/logs.
        self.code = code if code in LLM_PUBLIC_DETAILS else "llm_unavailable"


INTERACTION_DETAILS = {
    "npc_away": "O personagem saiu deste local. Feche a conversa e procure-o no mapa.",
    "npc_travelling": "O personagem está em deslocamento. Aguarde a chegada e aproxime-se novamente.",
    "npc_too_far": "Você está longe do personagem. Feche a conversa e aproxime-se novamente.",
    "npc_unavailable": "O personagem não está disponível para conversar agora.",
    "npc_detained": "O personagem está sob custódia do delegado.",
}


class InteractionUnavailableError(AccessDeniedError):
    def __init__(self, code):
        self.code = code if code in INTERACTION_DETAILS else "npc_unavailable"
        super().__init__(INTERACTION_DETAILS[self.code])
