"""CCL LLM augmentation layer — model-agnostic compliance enhancement."""
from ccl.llm.adapter import LLMAdapter, LLMResponse, create_adapter
from ccl.llm.augmentor import LLMAugmentor

__all__ = ["LLMAdapter", "LLMResponse", "LLMAugmentor", "create_adapter"]
