import os

from rfe.adapters.llm.openai_compat import OpenAICompatProvider
from rfe.api.app import build_app

provider = OpenAICompatProvider.from_env(
    base_url=os.environ.get("RFE_LLM_BASE_URL", "http://localhost:11434/v1"),
    api_key=os.environ.get("RFE_LLM_API_KEY", ""),
    model=os.environ.get("RFE_LLM_MODEL", "llama3"),
)
app = build_app(model_provider=provider)
