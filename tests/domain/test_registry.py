from domain.ports.registry import DomainRegistry
from domain.ports.directory_scanner import IDirectoryScanner
from domain.workflow.interfaces.git_port import IGitService
from domain.workflow.interfaces.ast_parser_port import IAstParser
from domain.config.app_settings import AppSettings
from domain.smart_context.tree_item import TreeItem
from pathlib import Path


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


def test_registry_new_ports():
    # 1. Directory scanner
    scanner = DummyDirectoryScanner()
    DomainRegistry.register_directory_scanner(scanner)
    assert DomainRegistry.directory_scanner() == scanner

    # 2. Git service
    git = DummyGitService()
    DomainRegistry.register_git_service(git)
    assert DomainRegistry.git_service() == git

    # 3. AST parser
    parser = DummyAstParser()
    DomainRegistry.register_ast_parser(parser)
    assert DomainRegistry.ast_parser() == parser

    # 4. Settings Provider
    DomainRegistry.register_settings_provider(
        lambda: AppSettings(output_language="Japanese")
    )
    assert DomainRegistry.settings().output_language == "Japanese"
