from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from miniclaw.config.settings import settings

_smart_llm = None
_fast_llm = None


def get_llm(provider=None, model=None, temperature=0.7, streaming=False, **kwargs):
    provider = provider or settings.LLM_PROVIDER
    if provider == "ollama":
        return ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=model or settings.OLLAMA_MODEL,
            temperature=temperature,
            **kwargs,
        )
    elif provider == "deepseek":
        return ChatOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            model=model or settings.DEEPSEEK_MODEL,
            temperature=temperature,
            streaming=streaming,
            **kwargs,
        )
    else:
        return ChatOpenAI(
            api_key=settings.effective_api_key,
            base_url=settings.effective_base_url,
            model=model or settings.effective_model,
            temperature=temperature,
            streaming=streaming,
            **kwargs,
        )


def get_smart_llm(**kwargs):
    global _smart_llm
    if _smart_llm is None:
        _smart_llm = get_llm(temperature=0.7, streaming=True, **kwargs)
    return _smart_llm


def get_fast_llm(**kwargs):
    global _fast_llm
    if _fast_llm is None:
        fast_kwargs = {"temperature": 0.3, "streaming": False, **kwargs}
        if settings.LLM_PROVIDER == "ollama":
            fast_kwargs.setdefault("model", settings.OLLAMA_MODEL)
        elif settings.LLM_PROVIDER == "deepseek":
            fast_kwargs.setdefault("model", "deepseek-chat")
        else:
            fast_kwargs.setdefault("model", settings.effective_model)
        _fast_llm = get_llm(**fast_kwargs)
    return _fast_llm


def reset_llm_cache():
    global _smart_llm, _fast_llm
    _smart_llm = None
    _fast_llm = None
