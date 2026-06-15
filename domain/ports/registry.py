from typing import Optional
from domain.ports.tokenization_port import ITokenizationService
from domain.ports.workspace_scanner import IWorkspaceScanner


class DomainRegistry:
    """
    Registry tinh (Service Locator) o Domain layer.

    Cung cap diem truy cap den cac implementation thuc te (TokenizationService,
    WorkspaceScanner) ma khong lam domain bi phu thuoc nguoc vao cac layer ngoai.
    """

    _tokenization_service: Optional[ITokenizationService] = None
    _workspace_scanner: Optional[IWorkspaceScanner] = None

    @classmethod
    def register_tokenization_service(cls, service: ITokenizationService) -> None:
        cls._tokenization_service = service

        # Backward compatibility for old encoder_registry wrapper
        try:
            from infrastructure.adapters import encoder_registry

            encoder_registry._tokenization_service = service
        except ImportError:
            pass

    @classmethod
    def tokenization_service(cls) -> ITokenizationService:
        if cls._tokenization_service is None:
            raise RuntimeError(
                "ITokenizationService is not registered in DomainRegistry"
            )
        return cls._tokenization_service

    @classmethod
    def register_workspace_scanner(cls, scanner: IWorkspaceScanner) -> None:
        cls._workspace_scanner = scanner

    @classmethod
    def workspace_scanner(cls) -> IWorkspaceScanner:
        if cls._workspace_scanner is None:
            raise RuntimeError("IWorkspaceScanner is not registered in DomainRegistry")
        return cls._workspace_scanner
