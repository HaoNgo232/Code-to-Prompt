from typing import Callable, Optional
from domain.ports.tokenization_port import ITokenizationService
from domain.ports.workspace_scanner import IWorkspaceScanner
from domain.ports.directory_scanner import IDirectoryScanner
from domain.workflow.interfaces.git_port import IGitService
from domain.workflow.interfaces.ast_parser_port import IAstParser
from domain.config.app_settings import AppSettings


class DomainRegistry:
    """
    Registry tinh (Service Locator) o Domain layer.

    Cung cap diem truy cap den cac implementation thuc te (TokenizationService,
    WorkspaceScanner) ma khong lam domain bi phu thuoc nguoc vao cac layer ngoai.
    """

    _tokenization_service: Optional[ITokenizationService] = None
    _workspace_scanner: Optional[IWorkspaceScanner] = None
    _directory_scanner: Optional[IDirectoryScanner] = None
    _git_service: Optional[IGitService] = None
    _ast_parser: Optional[IAstParser] = None
    _settings_provider: Optional[Callable[[], AppSettings]] = None

    @classmethod
    def register_tokenization_service(cls, service: ITokenizationService) -> None:
        cls._tokenization_service = service

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

    @classmethod
    def register_directory_scanner(cls, scanner: IDirectoryScanner) -> None:
        cls._directory_scanner = scanner

    @classmethod
    def directory_scanner(cls) -> IDirectoryScanner:
        if cls._directory_scanner is None:
            raise RuntimeError("IDirectoryScanner is not registered in DomainRegistry")
        return cls._directory_scanner

    @classmethod
    def register_git_service(cls, service: IGitService) -> None:
        cls._git_service = service

    @classmethod
    def git_service(cls) -> IGitService:
        if cls._git_service is None:
            raise RuntimeError("IGitService is not registered in DomainRegistry")
        return cls._git_service

    @classmethod
    def register_ast_parser(cls, parser: IAstParser) -> None:
        cls._ast_parser = parser

    @classmethod
    def ast_parser(cls) -> IAstParser:
        if cls._ast_parser is None:
            raise RuntimeError("IAstParser is not registered in DomainRegistry")
        return cls._ast_parser

    @classmethod
    def register_settings_provider(cls, provider: Callable[[], AppSettings]) -> None:
        cls._settings_provider = provider

    @classmethod
    def settings(cls) -> AppSettings:
        if cls._settings_provider is None:
            return AppSettings()
        return cls._settings_provider()
