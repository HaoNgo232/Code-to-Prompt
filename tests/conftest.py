import pytest
from pathlib import Path
from domain.ports.registry import DomainRegistry
from domain.ports.directory_scanner import IDirectoryScanner
from domain.workflow.interfaces.git_port import IGitService
from domain.workflow.interfaces.ast_parser_port import IAstParser
from domain.smart_context.tree_item import TreeItem


class DummyDirectoryScanner(IDirectoryScanner):
    def scan_directory(self, root_path: Path) -> TreeItem:
        return TreeItem(label="root", path=str(root_path), is_dir=True)


class DummyGitService(IGitService):
    def get_diffs(self, root_path, base_ref=None):
        return None

    def get_logs(self, root_path, max_commits=10):
        return None


class DummyAstParser(IAstParser):
    def parse_file(self, file_path):
        return {"symbols": []}


@pytest.fixture(autouse=True, scope="session")
def setup_dummy_domain_ports():
    # Only register if not already registered to avoid overwriting production container setup
    try:
        DomainRegistry.directory_scanner()
    except RuntimeError:
        DomainRegistry.register_directory_scanner(DummyDirectoryScanner())

    try:
        DomainRegistry.git_service()
    except RuntimeError:
        DomainRegistry.register_git_service(DummyGitService())

    try:
        DomainRegistry.ast_parser()
    except RuntimeError:
        DomainRegistry.register_ast_parser(DummyAstParser())
