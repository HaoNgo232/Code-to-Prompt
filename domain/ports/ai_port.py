from dataclasses import dataclass
from typing import List, Protocol

@dataclass
class LLMMessage:
    role: str
    content: str

@dataclass
class LLMResponse:
    content: str
    token_count: int

class IAIProvider(Protocol):
    def generate(self, messages: List[LLMMessage]) -> LLMResponse:
        ...
