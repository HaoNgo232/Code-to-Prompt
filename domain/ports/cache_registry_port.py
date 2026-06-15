from typing import Protocol, List, Dict

class ICacheRegistry(Protocol):
    def get_stats(self) -> Dict[str, int]:
        ...

    def get_registered_names(self) -> List[str]:
        ...

    def invalidate_for_workspace(self) -> None:
        ...
