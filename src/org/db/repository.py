"""Repository abstraction for one or more file-backed Org documents."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

import typer
from org_parser import dump as dump_org_document
from org_parser import loads

from org.config.cli import (
    QueryBuildArgs,
    build_pipeline_stages,
    collect_custom_context_vars,
    normalize_cli_files_for_custom_switches,
    validate_custom_switches,
)
from org.db.errors import (
    DocumentConflictError,
    DocumentMissingError,
    DocumentNotFoundError,
    DocumentParseError,
    DocumentPermissionError,
    HeadingAmbiguousError,
    HeadingNotFoundError,
    RepositoryError,
)
from org.logic.validation import validate_and_parse_keys, validate_global_arguments
from org.query.engine.errors import QueryParseError, QueryRuntimeError
from org.query.runner import run_query


if TYPE_CHECKING:
    from org_parser.document import Document, Heading

    from org.config.app import AppConfig
    from org.logic.tasks import HeadingLocator


logger = logging.getLogger("org")


def load_document_from_text(document_text: str, filename: str | None) -> Document:
    """Parse full document text and preserve original filename when present."""
    try:
        document = loads(document_text)
    except (TypeError, ValueError) as err:
        raise DocumentParseError(filename or "<edited document>", str(err)) from err

    document.filename = "" if filename is None else filename
    return document


def resolve_input_paths(inputs: list[str] | None) -> list[str]:  # noqa: C901
    """Resolve CLI inputs into a list of Org files to process."""
    resolved_files: list[str] = []
    searched_dirs: list[Path] = []
    missing_paths: list[str] = []

    targets = inputs or ["."]
    for raw_path in targets:
        path = Path(raw_path)
        if not path.exists():
            missing_paths.append(raw_path)
            continue

        if path.is_dir():
            searched_dirs.append(path)
            for file_path in sorted(path.glob("*.org")):
                if file_path.exists():
                    resolved_files.append(str(file_path))
                else:
                    missing_paths.append(str(file_path))
            continue

        if path.is_file():
            resolved_files.append(str(path))
            continue

        raise typer.BadParameter(f"Path '{raw_path}' is not a file or directory")

    for raw_path in missing_paths:
        logger.info("Warning: file '%s' not found", raw_path)

    if not resolved_files:
        if missing_paths:
            missing_list = ", ".join(missing_paths)
            raise typer.BadParameter(f"All input paths are missing: {missing_list}")
        if searched_dirs:
            searched_list = ", ".join(str(path) for path in searched_dirs)
            raise typer.BadParameter(f"No .org files found in: {searched_list}")
        raise typer.BadParameter("No .org files found")

    return resolved_files


def _merge_state_order(existing: list[str], discovered: list[str]) -> list[str]:
    """Merge discovered states into existing list while preserving order."""
    merged = list(existing)
    seen = set(merged)
    for state in discovered:
        if state in seen:
            continue
        merged.append(state)
        seen.add(state)
    return merged


def _normalize_org_text(contents: str) -> str:
    """Normalize parser-incompatible time values before parse."""
    return contents.replace("24:00", "00:00")


def _prepend_todo_config(contents: str, todo_states: list[str], done_states: list[str]) -> str:
    """Prepend TODO keyword configuration to file contents."""
    todo_config = f"#+TODO: {' '.join(todo_states)} | {' '.join(done_states)}\n\n"
    return todo_config + contents


def _canonical_path(path: str) -> str:
    """Return canonical path key for repository tracking."""
    return str(Path(path).expanduser().resolve(strict=False))


@dataclass
class TrackedDocument:
    """One repository-tracked file-backed Org document."""

    path: str
    document: Document
    loaded_mtime: float
    injected_todo_keyword: bool

    @property
    def is_dirty(self) -> bool:
        """Return whether the tracked document has in-memory modifications."""
        return bool(self.document.dirty)

    def stat_mtime(self) -> float:
        """Return current filesystem mtime for the tracked file."""
        path = Path(self.path)
        try:
            return path.stat().st_mtime
        except FileNotFoundError as err:
            raise DocumentMissingError(self.path) from err
        except PermissionError as err:
            raise DocumentPermissionError(self.path) from err

    def has_external_changes(self) -> bool:
        """Return whether the tracked file changed since it was loaded."""
        return self.stat_mtime() > self.loaded_mtime


@dataclass(frozen=True)
class RepositoryQueryPlan:
    """Prepared repository query plan for command execution."""

    files: list[str]
    stages: list[str]
    context: dict[str, object]
    todo_states: list[str]
    done_states: list[str]


class RootDataLoadArgs(Protocol):
    """Protocol for loading root nodes without filters or enrichment."""

    files: list[str] | None
    todo_states: str
    done_states: str
    width: int | None


class RepositoryQueryArgs(QueryBuildArgs, Protocol):
    """Protocol for repository-backed query pipeline arguments."""

    files: list[str] | None
    todo_states: str
    done_states: str
    width: int | None


class SlicedDataLoadArgs(Protocol):
    """Protocol for args that support query slicing."""

    offset: int
    max_results: int


class OrgRepository:
    """Repository for file-backed Org documents with conflict-aware persistence."""

    def __init__(
        self,
        files: list[str],
        todo_states: list[str],
        done_states: list[str],
    ) -> None:
        """Load and track the requested Org files."""
        self._configured_todo_states = list(todo_states)
        self._configured_done_states = list(done_states)
        self._documents_by_path: dict[str, TrackedDocument] = {}
        for file_path in files:
            tracked = self._load_tracked_document(file_path)
            self._documents_by_path[_canonical_path(tracked.path)] = tracked
        self._refresh_state_cache()

    @property
    def documents(self) -> list[Document]:
        """Return currently tracked parsed documents."""
        return [tracked.document for tracked in self._documents_by_path.values()]

    @property
    def todo_states(self) -> list[str]:
        """Return cached merged TODO states."""
        return list(self._todo_states)

    @property
    def done_states(self) -> list[str]:
        """Return cached merged DONE states."""
        return list(self._done_states)

    @classmethod
    def from_args(cls, args: RootDataLoadArgs) -> OrgRepository:
        """Build a repository directly from shared CLI file/state arguments."""
        todo_states = validate_and_parse_keys(args.todo_states, "--todo-states")
        done_states = validate_and_parse_keys(args.done_states, "--done-states")
        files = resolve_input_paths(args.files)
        return cls(files, todo_states, done_states)

    def _refresh_state_cache(self) -> None:
        """Refresh cached merged TODO and DONE states."""
        todo_states = list(self._configured_todo_states)
        done_states = list(self._configured_done_states)
        for tracked in self._documents_by_path.values():
            todo_states = _merge_state_order(todo_states, list(tracked.document.todo_states))
            done_states = _merge_state_order(done_states, list(tracked.document.done_states))
        self._todo_states = todo_states
        self._done_states = done_states

    def _load_document_from_path(self, path: str) -> tuple[Document, bool]:
        """Load one Org document from disk with normalized parse input."""
        file_path = Path(path)
        try:
            logger.info("Processing %s...", path)
            contents = file_path.read_text(encoding="utf-8")
        except FileNotFoundError as err:
            raise DocumentNotFoundError(path) from err
        except PermissionError as err:
            raise DocumentPermissionError(path) from err

        injected_todo_keyword = bool(self._configured_todo_states or self._configured_done_states)
        if injected_todo_keyword:
            contents = _prepend_todo_config(
                contents,
                self._configured_todo_states,
                self._configured_done_states,
            )

        try:
            document = loads(_normalize_org_text(contents), filename=path)
        except (TypeError, ValueError) as err:
            raise DocumentParseError(path, str(err)) from err
        document.filename = path
        return document, injected_todo_keyword

    def _load_tracked_document(self, path: str) -> TrackedDocument:
        """Load one tracked Org document from disk."""
        document, injected_todo_keyword = self._load_document_from_path(path)
        try:
            loaded_mtime = Path(path).expanduser().stat().st_mtime
        except FileNotFoundError as err:
            raise DocumentNotFoundError(path) from err
        except PermissionError as err:
            raise DocumentPermissionError(path) from err
        return TrackedDocument(
            path=path,
            document=document,
            loaded_mtime=loaded_mtime,
            injected_todo_keyword=injected_todo_keyword,
        )

    def _strip_injected_todo_keyword(self, tracked: TrackedDocument) -> None:
        """Remove repository-injected TODO keyword before writing back to disk."""
        if not tracked.injected_todo_keyword:
            return
        expected_value = (
            f"{' '.join(self._configured_todo_states)} | {' '.join(self._configured_done_states)}"
        )
        for index, keyword in enumerate(list(tracked.document.keywords)):
            if keyword.key.upper() != "TODO":
                continue
            if str(keyword.value).strip() != expected_value:
                continue
            del tracked.document.keywords[index]
            return

    def _ensure_tracked_document(self, path: str) -> TrackedDocument:
        """Return tracked document for path, loading it when needed."""
        canonical_path = _canonical_path(path)
        tracked = self._documents_by_path.get(canonical_path)
        if tracked is None:
            tracked = self._load_tracked_document(path)
            self._documents_by_path[canonical_path] = tracked
            self._refresh_state_cache()
        return tracked

    def _replace_tracked_document(self, tracked: TrackedDocument) -> None:
        """Replace tracked document state and refresh caches."""
        self._documents_by_path[_canonical_path(tracked.path)] = tracked
        self._refresh_state_cache()

    def refresh(self) -> None:
        """Refresh tracked documents for read access.

        Clean externally modified files are automatically reloaded. Dirty externally modified
        files raise an explicit conflict error.
        """
        for tracked in list(self._documents_by_path.values()):
            if not tracked.has_external_changes():
                continue
            if tracked.is_dirty:
                raise DocumentConflictError(tracked.path)
            self.reload_document(tracked.path)

    def get_document(self, path: str) -> Document:
        """Return one tracked document after refresh checks."""
        self.refresh()
        return self._ensure_tracked_document(path).document

    def reload_document(self, path: str, *, force: bool = False) -> Document:
        """Reload one tracked document from disk."""
        tracked = self._ensure_tracked_document(path)
        if tracked.is_dirty and not force:
            raise DocumentConflictError(tracked.path)
        reloaded = self._load_tracked_document(tracked.path)
        self._replace_tracked_document(reloaded)
        return reloaded.document

    def reload_all(self, *, force: bool = False) -> None:
        """Reload all tracked documents from disk."""
        for tracked in list(self._documents_by_path.values()):
            self.reload_document(tracked.path, force=force)

    def save_document(self, path: str, *, force: bool = False) -> Document:
        """Persist one tracked document back to disk and reload it."""
        tracked = self._ensure_tracked_document(path)
        if tracked.has_external_changes() and not force:
            raise DocumentConflictError(tracked.path)
        self._strip_injected_todo_keyword(tracked)
        try:
            dump_org_document(tracked.document, tracked.path)
        except PermissionError as err:
            raise DocumentPermissionError(tracked.path) from err
        return self.reload_document(tracked.path, force=True)

    def save_dirty(self, *, force: bool = False) -> list[Document]:
        """Persist all dirty tracked documents and reload them."""
        saved_documents: list[Document] = []
        for tracked in list(self._documents_by_path.values()):
            if not tracked.is_dirty:
                continue
            saved_documents.append(self.save_document(tracked.path, force=force))
        return saved_documents

    def save_documents(self, documents: list[Document], *, force: bool = False) -> list[Document]:
        """Persist the provided tracked documents and reload them."""
        unique_paths = list(
            dict.fromkeys(
                (document.filename or "" for document in documents if document.filename),
            ),
        )
        return [self.save_document(path, force=force) for path in unique_paths]

    def query(self, query_stages: list[str], context: dict[str, object]) -> list[object]:
        """Run a query against all tracked documents after refresh checks."""
        self.refresh()
        return run_query(self.documents, query_stages, context)

    def heading_by_id(self, heading_id: str) -> Heading | None:
        """Return first tracked heading with the requested ID."""
        self.refresh()
        for document in self.documents:
            heading = document.heading_by_id(heading_id)
            if heading is not None:
                return heading
        return None

    def resolve_heading(self, locator: HeadingLocator) -> Heading | None:
        """Resolve a previously captured heading locator."""
        self.refresh()
        if locator.filename:
            try:
                document = self.get_document(locator.filename)
            except DocumentNotFoundError:
                return None
        else:
            return None
        if locator.heading_id is not None:
            resolved = document.heading_by_id(locator.heading_id)
            if resolved is not None:
                return resolved
        return document.heading_by_title(locator.title)

    def resolve_parent_heading(self, path: str, selector: str) -> Heading:
        """Resolve one parent heading by ID first, then by title within one document."""
        document = self.get_document(path)
        heading = document.heading_by_id(selector)
        if heading is not None:
            return heading
        matches = [node for node in list(document) if node.title_text.strip() == selector]
        if len(matches) > 1:
            raise HeadingAmbiguousError(
                f"--parent is ambiguous, multiple headings with title '{selector}'",
            )
        if len(matches) == 1:
            return matches[0]
        raise HeadingNotFoundError(f"--parent '{selector}' was not found")

    def move_heading_between_documents(
        self,
        heading: Heading,
        destination_document: Document,
        *,
        parent_heading: Heading | None = None,
    ) -> None:
        """Move one heading subtree to another tracked document while preserving identity."""
        source_parent = heading.parent
        if source_parent is None:
            raise HeadingNotFoundError("Unable to move heading without a parent node")
        source_parent.children.remove(heading)
        if parent_heading is None:
            destination_document.children.append(heading)
        else:
            parent_heading.children.append(heading)
        heading.document = destination_document
        for descendant in _iter_descendants(heading):
            descendant.document = destination_document


def _iter_descendants(heading: Heading) -> list[Heading]:
    """Return heading descendants as a flat list."""
    descendants: list[Heading] = []
    for child in heading.children:
        descendants.append(child)
        descendants.extend(_iter_descendants(child))
    return descendants


def cli_error_from_repository_error(err: Exception) -> Exception:
    """Convert repository and query errors to CLI-friendly parameter errors."""
    if isinstance(err, QueryParseError | QueryRuntimeError):
        return typer.BadParameter(str(err))
    if isinstance(err, RepositoryError):
        return typer.BadParameter(str(err))
    return err


def build_repository_query_plan(
    args: RepositoryQueryArgs,
    config: AppConfig,
    argv: list[str] | None = None,
    *,
    include_ordering: bool,
) -> RepositoryQueryPlan:
    """Build a repository-backed query plan from CLI arguments."""
    active_argv = sys.argv if argv is None else argv
    validate_custom_switches(config, active_argv, include_ordering)

    normalized_files = normalize_cli_files_for_custom_switches(config, args.files)
    args.files = normalized_files

    todo_states, done_states = validate_global_arguments(args)
    files = resolve_input_paths(normalized_files)
    include_slice = include_ordering and hasattr(args, "offset") and hasattr(args, "max_results")
    stages = [".[]", *build_pipeline_stages(config, args, active_argv, include_ordering)]
    context_vars: dict[str, object] = {
        "todo_states": todo_states,
        "done_states": done_states,
    }
    context_vars.update(
        collect_custom_context_vars(active_argv, normalized_files, include_ordering),
    )
    if include_slice:
        sliced_args = cast("SlicedDataLoadArgs", args)
        context_vars["offset"] = sliced_args.offset
        context_vars["limit"] = sliced_args.max_results

    logger.info("Query context: %s", context_vars)
    return RepositoryQueryPlan(
        files=files,
        stages=stages,
        context=context_vars,
        todo_states=todo_states,
        done_states=done_states,
    )


def build_root_repository(args: RootDataLoadArgs) -> OrgRepository:
    """Build a repository for commands that only need direct file/state inputs."""
    return OrgRepository.from_args(args)
