"""Provider-aware LLM factory for OpenAI/Gemini."""

from backend.config import settings


def _is_configured(value: str | None) -> bool:
    if not value:
        return False
    token = value.strip()
    if not token:
        return False
    return token.lower() not in {"dummy-key", "your-api-key-here", "your-google-api-key-here"}


def _pick_provider(provider: str, model: str, api_key: str) -> str:
    normalized = (provider or "auto").strip().lower()
    if normalized in {"openai", "gemini"}:
        return normalized

    model_lower = (model or "").lower()
    if "gemini" in model_lower:
        return "gemini"
    if model_lower.startswith(("gpt", "o1", "o3", "o4")):
        return "openai"

    if _is_configured(api_key):
        if api_key.startswith("sk-"):
            return "openai"
        if api_key.startswith("AIza"):
            return "gemini"

    if _is_configured(settings.OPENAI_API_KEY):
        return "openai"
    if _is_configured(settings.GOOGLE_API_KEY):
        return "gemini"

    raise RuntimeError(
        "No LLM provider configured. Set AI_PROVIDER or provide OPENAI_API_KEY/GOOGLE_API_KEY."
    )


def _resolved_key_for(provider: str, explicit_api_key: str) -> str:
    if provider == "gemini":
        if _is_configured(explicit_api_key) and not explicit_api_key.startswith("sk-"):
            return explicit_api_key
        return settings.GOOGLE_API_KEY
    if _is_configured(explicit_api_key) and explicit_api_key.startswith("sk-"):
        return explicit_api_key
    return settings.OPENAI_API_KEY


def get_chat_llm(scope: str = "default", temperature: float = 0.0):
    """
    Create a provider-specific LangChain chat model.

    scope:
      - default: used by orchestrator/intake/etc
      - retrieval: used by retrieval agent (can override provider/model/key)
    """
    if scope == "retrieval":
        provider = settings.RETRIEVAL_LLM_PROVIDER or settings.AI_PROVIDER
        model = (
            settings.RETRIEVAL_LLM_MODEL
            or settings.LLM_MODEL
            or settings.OPENAI_MODEL
            or settings.GEMINI_MODEL
        )
        api_key = settings.RETRIEVAL_LLM_API_KEY or settings.LLM_API_KEY
    else:
        provider = settings.AI_PROVIDER
        model = settings.LLM_MODEL or settings.OPENAI_MODEL or settings.GEMINI_MODEL
        api_key = settings.LLM_API_KEY

    chosen = _pick_provider(provider, model, api_key)
    chosen_key = _resolved_key_for(chosen, api_key)
    if not _is_configured(chosen_key):
        fallback = "openai" if chosen == "gemini" else "gemini"
        fallback_key = _resolved_key_for(fallback, api_key)
        if _is_configured(fallback_key):
            chosen = fallback

    if chosen == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        resolved_model = model if "gemini" in (model or "").lower() else settings.GEMINI_MODEL
        resolved_key = _resolved_key_for("gemini", api_key)
        if not _is_configured(resolved_key):
            raise RuntimeError("Gemini provider selected but GOOGLE_API_KEY is not configured.")
        return ChatGoogleGenerativeAI(
            model=resolved_model,
            google_api_key=resolved_key,
            temperature=temperature,
        )

    from langchain_openai import ChatOpenAI

    if model and "gemini" not in model.lower():
        resolved_model = model
    else:
        resolved_model = settings.OPENAI_MODEL
    resolved_key = _resolved_key_for("openai", api_key)
    if not _is_configured(resolved_key):
        raise RuntimeError("OpenAI provider selected but OPENAI_API_KEY is not configured.")
    return ChatOpenAI(
        model=resolved_model,
        api_key=resolved_key,
        temperature=temperature,
    )
