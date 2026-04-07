"""OpenAI LLM factory."""

from langchain_openai import ChatOpenAI

from backend.config import settings


def _is_configured(value: str | None) -> bool:
    if not value:
        return False
    token = value.strip()
    if not token:
        return False
    return token.lower() not in {"dummy-key", "your-api-key-here"}


def _resolve_key(explicit_api_key: str) -> str:
    if _is_configured(explicit_api_key) and explicit_api_key.startswith("sk-"):
        return explicit_api_key
    return settings.OPENAI_API_KEY


def get_chat_llm(scope: str = "default", temperature: float = 0.0):
    """
    Create an OpenAI LangChain chat model.

    scope:
      - default:    used by orchestrator/intake/etc
      - retrieval:  retrieval agent (reads RETRIEVAL_LLM_* settings)
      - policy:     policy agent (reads POLICY_LLM_* settings)
    """
    if scope == "retrieval":
        model = settings.RETRIEVAL_LLM_MODEL or settings.LLM_MODEL or settings.OPENAI_MODEL
        api_key = settings.RETRIEVAL_LLM_API_KEY or settings.LLM_API_KEY
    elif scope == "policy":
        model = settings.POLICY_LLM_MODEL or settings.LLM_MODEL or settings.OPENAI_MODEL
        api_key = settings.POLICY_LLM_API_KEY or settings.LLM_API_KEY
    else:
        model = settings.LLM_MODEL or settings.OPENAI_MODEL
        api_key = settings.LLM_API_KEY

    resolved_key = _resolve_key(api_key)
    if not _is_configured(resolved_key):
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    return ChatOpenAI(
        model=model,
        api_key=resolved_key,
        temperature=temperature,
    )
