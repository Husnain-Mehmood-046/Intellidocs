"""
LLM provider wrapper (Day 5-6).

Why a wrapper?
- The rest of the codebase should not care whether we use OpenAI, Anthropic,
  Groq, or a local Hugging Face model. This module is the single place to swap
  providers, so changing the LLM is a one-file change.
"""

from . import config


def generate(prompt: str) -> str:
    """
    Send a prompt to the configured LLM and return the completion text.

    Supported providers (set via LLM_PROVIDER):
      - groq:       Groq's OpenAI-compatible API (needs GROQ_API_KEY)
      - openai:     openai.ChatCompletion (needs OPENAI_API_KEY)
      - anthropic:  anthropic.Anthropic().messages (needs ANTHROPIC_API_KEY)
      - local:      transformers pipeline (no key, needs a downloaded model)
      - ollama:     Ollama local model serving (needs OLLAMA_BASE_URL)
      - finetuned:  Fine-tuned model via Ollama (needs FINETUNED_MODEL in config)
    """
    provider = config.LLM_PROVIDER

    if provider == "groq":
        return _generate_groq(prompt)
    if provider == "openai":
        return _generate_openai(prompt)
    if provider == "anthropic":
        return _generate_anthropic(prompt)
    if provider == "local":
        return _generate_local(prompt)
    if provider == "ollama":
        return _generate_ollama(prompt)
    if provider == "finetuned":
        return _generate_finetuned(prompt)

    raise NotImplementedError(
        f"LLM provider '{provider}' not implemented. "
        "Choose groq / openai / anthropic / local / ollama / finetuned."
    )


def get_structured_llm(output_schema):
    """
    Return an LLM configured for structured output with the given Pydantic schema.

    Why a separate function?
    - Structured output requires provider-specific setup (e.g., OpenAI's
      `with_structured_output`, Anthropic's tool use, etc.).
    - This function encapsulates that logic so the rest of the codebase just
      calls `get_structured_llm(Answer)` and gets a ready-to-use chain component.
    """
    provider = config.LLM_PROVIDER

    if provider == "groq":
        return _get_structured_groq(output_schema)
    if provider == "openai":
        return _get_structured_openai(output_schema)
    if provider == "anthropic":
        return _get_structured_anthropic(output_schema)
    if provider == "ollama":
        return _get_structured_ollama(output_schema)
    if provider == "finetuned":
        return _get_structured_finetuned(output_schema)
    if provider == "local":
        # Local transformers pipeline doesn't support structured output natively
        # Fall back to prompt-based parsing
        return _get_structured_local(output_schema)

    raise NotImplementedError(
        f"Structured output not implemented for provider '{provider}'."
    )


def _get_structured_groq(output_schema):
    """Get Groq LLM with structured output (uses OpenAI-compatible API)."""
    from langchain_groq import ChatGroq
    
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to ai-service/.env.")
    
    llm = ChatGroq(
        api_key=config.GROQ_API_KEY,
        model=config.GROQ_MODEL,
        temperature=0.0,
    )
    return llm.with_structured_output(output_schema)


def _get_structured_openai(output_schema):
    """Get OpenAI LLM with structured output."""
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI(
        api_key=config.OPENAI_API_KEY,
        model=config.OPENAI_MODEL,
        temperature=0.0,
    )
    return llm.with_structured_output(output_schema)


def _get_structured_anthropic(output_schema):
    """Get Anthropic LLM with structured output (uses tool calling)."""
    from langchain_anthropic import ChatAnthropic
    
    llm = ChatAnthropic(
        api_key=config.ANTHROPIC_API_KEY,
        model=config.ANTHROPIC_MODEL,
        temperature=0.0,
    )
    return llm.with_structured_output(output_schema)


def _get_structured_ollama(output_schema):
    """Get Ollama LLM with structured output."""
    from langchain_ollama import ChatOllama
    
    llm = ChatOllama(
        model=config.OLLAMA_MODEL,
        base_url=config.OLLAMA_BASE_URL,
        temperature=0.0,
    )
    return llm.with_structured_output(output_schema)


def _get_structured_local(output_schema):
    """Fallback for local provider - uses prompt-based parsing."""
    from langchain_core.output_parsers import PydanticOutputParser
    from langchain_huggingface import HuggingFacePipeline
    from transformers import pipeline
    
    parser = PydanticOutputParser(pydantic_object=output_schema)
    
    generator = pipeline("text-generation", model=config.EMBEDDING_MODEL)
    llm = HuggingFacePipeline(pipeline=generator)
    
    # For local models, we can't use with_structured_output, so we return
    # the base LLM and let the caller handle parsing
    return llm


def _generate_groq(prompt: str) -> str:
    """Call Groq's OpenAI-compatible chat completions endpoint."""
    from openai import OpenAI

    if not config.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to ai-service/.env."
        )

    client = OpenAI(
        api_key=config.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )
    response = client.chat.completions.create(
        model=config.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    return response.choices[0].message.content


def _generate_openai(prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    return response.choices[0].message.content


def _generate_anthropic(prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _generate_ollama(prompt: str) -> str:
    """Call Ollama's REST API for local model inference."""
    import requests
    
    if not config.OLLAMA_BASE_URL:
        raise RuntimeError("OLLAMA_BASE_URL is not set. Add it to ai-service/.env.")
    
    response = requests.post(
        f"{config.OLLAMA_BASE_URL}/api/generate",
        json={
            "model": config.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0}
        },
        timeout=120
    )
    response.raise_for_status()
    return response.json().get("response", "")


def _generate_local(prompt: str) -> str:
    from transformers import pipeline

    generator = pipeline("text-generation", model=config.EMBEDDING_MODEL)
    return generator(prompt, max_new_tokens=256)[0]["generated_text"]


def _generate_finetuned(prompt: str) -> str:
    """Call Ollama's REST API for the fine-tuned model."""
    import requests
    
    if not config.OLLAMA_BASE_URL:
        raise RuntimeError("OLLAMA_BASE_URL is not set. Add it to ai-service/.env.")
    
    if not config.FINETUNED_MODEL:
        raise RuntimeError("FINETUNED_MODEL is not set. Add it to ai-service/.env or config.py.")
    
    response = requests.post(
        f"{config.OLLAMA_BASE_URL}/api/generate",
        json={
            "model": config.FINETUNED_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0}
        },
        timeout=120
    )
    response.raise_for_status()
    return response.json().get("response", "")


def _get_structured_finetuned(output_schema):
    """Get fine-tuned Ollama LLM with structured output."""
    from langchain_ollama import ChatOllama
    
    llm = ChatOllama(
        model=config.FINETUNED_MODEL,
        base_url=config.OLLAMA_BASE_URL,
        temperature=0.0,
    )
    return llm.with_structured_output(output_schema)