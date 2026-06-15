from typing import Protocol, Any
from domain.config.app_settings import AppSettings

class ISettingsService(Protocol):
    def load_settings(self) -> AppSettings:
        ...

    def update_setting(self, key: str, value: Any) -> None:
        ...

    def add_instruction_history(self, instruction: str) -> None:
        ...
