#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import plistlib
import platform
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parent
DEVICE_SUPPORT_ROOT = REPO_ROOT / "DeviceSupport"
PLACEHOLDER_ROOT = DEVICE_SUPPORT_ROOT / "placeholders"
README_PATH = REPO_ROOT / "README.md"
DEVICE_SUPPORT_RELATIVE = Path("Platforms/iPhoneOS.platform/DeviceSupport")
SUPPORT_TABLE_START = "<!-- support-table:start -->"
SUPPORT_TABLE_END = "<!-- support-table:end -->"
DEFAULT_PLACEHOLDER_START_MAJOR = 17
DEFAULT_PLACEHOLDER_END_MAJOR = 26
VERSION_PATTERN = re.compile(r"^(?P<version>\d+(?:\.\d+)?)")
XCODE_APP_PATTERN = re.compile(r"^Xcode(?:[._ -].+)?\.app$", re.IGNORECASE)


class DeploymentError(RuntimeError):
    """Base error for deployment and maintenance commands."""


class RepositoryLayoutError(DeploymentError):
    """Raised when the repository layout is missing required directories."""


class XcodeDiscoveryError(DeploymentError):
    """Raised when the script cannot find a usable Xcode installation."""


class ReadmeOutOfDateError(DeploymentError):
    """Raised when README.md differs from the generated support matrix."""


@dataclass
class SupportVersion:
    version: str
    archives: list[Path] = field(default_factory=list)
    extracted_directories: list[Path] = field(default_factory=list)
    placeholder_directories: list[Path] = field(default_factory=list)

    @property
    def artifact_count(self) -> int:
        return len(self.archives) + len(self.extracted_directories)

    @property
    def status(self) -> str:
        return "Available" if self.artifact_count else "Placeholder"

    @property
    def notes(self) -> str:
        if self.artifact_count:
            archive_count = len(self.archives)
            directory_count = len(self.extracted_directories)
            fragments: list[str] = []
            if archive_count:
                suffix = "s" if archive_count != 1 else ""
                fragments.append(f"{archive_count} archive{suffix}")
            if directory_count:
                suffix = "ies" if directory_count != 1 else "y"
                fragments.append(f"{directory_count} extracted director{suffix}")
            return ", ".join(fragments)
        return "Reserved placeholder awaiting a contributed DeviceSupport bundle"

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "status": self.status,
            "artifact_count": self.artifact_count,
            "archives": [str(path) for path in sorted(self.archives)],
            "extracted_directories": [str(path) for path in sorted(self.extracted_directories)],
            "placeholder_directories": [str(path) for path in sorted(self.placeholder_directories)],
            "notes": self.notes,
        }


@dataclass(frozen=True)
class XcodeInstallation:
    source: str
    app_path: Path | None
    developer_dir: Path
    device_support_dir: Path
    display_name: str
    version: str | None
    is_beta: bool

    @property
    def is_ready(self) -> bool:
        return self.device_support_dir.is_dir()

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "app_path": str(self.app_path) if self.app_path else None,
            "developer_dir": str(self.developer_dir),
            "device_support_dir": str(self.device_support_dir),
            "display_name": self.display_name,
            "version": self.version,
            "is_beta": self.is_beta,
            "is_ready": self.is_ready,
        }


@dataclass(frozen=True)
class ArchivePlan:
    archive_path: Path
    display_name: str
    version: str
    root_entries: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "archive_path": str(self.archive_path),
            "display_name": self.display_name,
            "version": self.version,
            "root_entries": list(self.root_entries),
        }


def read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def extract_version(label: str) -> str | None:
    match = VERSION_PATTERN.match(label.strip())
    return match.group("version") if match else None


def version_sort_key(version: str | None) -> tuple[int, ...]:
    if not version:
        return (0,)
    return tuple(int(part) for part in version.split("."))


def ensure_repository_layout(device_support_root: Path) -> None:
    if not device_support_root.is_dir():
        raise RepositoryLayoutError(
            f"DeviceSupport root was not found at '{device_support_root}'. "
            "Make sure you run this script from the repository checkout."
        )


def support_record_for(inventory: dict[str, SupportVersion], version: str) -> SupportVersion:
    if version not in inventory:
        inventory[version] = SupportVersion(version=version)
    return inventory[version]


def scan_support_inventory(
    device_support_root: Path = DEVICE_SUPPORT_ROOT,
    placeholder_root: Path = PLACEHOLDER_ROOT,
) -> list[SupportVersion]:
    ensure_repository_layout(device_support_root)
    inventory: dict[str, SupportVersion] = {}

    for entry in sorted(device_support_root.iterdir(), key=lambda path: path.name.lower()):
        if entry == placeholder_root:
            continue
        if entry.is_file() and entry.suffix.lower() == ".zip":
            version = extract_version(entry.stem)
            if version:
                support_record_for(inventory, version).archives.append(entry)
        elif entry.is_dir():
            version = extract_version(entry.name)
            if version:
                support_record_for(inventory, version).extracted_directories.append(entry)

    if placeholder_root.is_dir():
        for entry in sorted(placeholder_root.iterdir(), key=lambda path: path.name.lower()):
            if not entry.is_dir():
                continue
            version = extract_version(entry.name)
            if version:
                support_record_for(inventory, version).placeholder_directories.append(entry)

    return sorted(inventory.values(), key=lambda item: version_sort_key(item.version))


def render_support_table(inventory: list[SupportVersion]) -> str:
    actual_versions = [item.version for item in inventory if item.artifact_count]
    placeholder_versions = [item.version for item in inventory if item.placeholder_directories]

    latest_actual = actual_versions[-1] if actual_versions else "N/A"
    furthest_placeholder = placeholder_versions[-1] if placeholder_versions else "N/A"

    lines = [
        f"> Latest verified support archive in this repository: **iOS {latest_actual}**.",
        f"> Placeholder directories are reserved through **iOS {furthest_placeholder}**.",
        "",
        "| iOS Version | Status | Artifacts | Notes |",
        "| --- | --- | ---: | --- |",
    ]

    for item in inventory:
        lines.append(
            f"| {item.version} | {item.status} | {item.artifact_count} | {item.notes} |"
        )

    return "\n".join(lines)


def replace_marked_block(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start_index = text.find(start_marker)
    end_index = text.find(end_marker)
    if start_index == -1 or end_index == -1 or end_index < start_index:
        raise ReadmeOutOfDateError(
            "README markers were not found. Expected "
            f"'{start_marker}' and '{end_marker}'."
        )

    block_start = start_index + len(start_marker)
    updated = f"{text[:block_start]}\n{replacement.rstrip()}\n{text[end_index:]}"
    return updated


def sync_readme(
    readme_path: Path = README_PATH,
    device_support_root: Path = DEVICE_SUPPORT_ROOT,
    placeholder_root: Path = PLACEHOLDER_ROOT,
    check_only: bool = False,
) -> bool:
    if not readme_path.is_file():
        raise FileNotFoundError(f"README file not found: '{readme_path}'")

    inventory = scan_support_inventory(device_support_root=device_support_root, placeholder_root=placeholder_root)
    generated_block = render_support_table(inventory)
    original = read_text(readme_path)
    updated = replace_marked_block(original, SUPPORT_TABLE_START, SUPPORT_TABLE_END, generated_block)

    if original == updated:
        return False
    if check_only:
        raise ReadmeOutOfDateError(
            f"README support matrix is out of date. Run 'python deploy.py sync-readme --readme {readme_path}'."
        )

    write_text(readme_path, updated)
    return True


def placeholder_file_contents(version: str) -> str:
    return "\n".join(
        [
            f"# iOS {version} Placeholder",
            "",
            "This directory reserves the future iOS version slot for HDRvision.",
            "",
            f"No verified DeviceSupport bundle for iOS {version} is stored in this repository yet.",
            "When a contributor uploads a tested archive, place the .zip file in DeviceSupport/ and keep this",
            "placeholder as historical scaffolding or remove it if the team prefers a clean future-version tree.",
            "",
            "Maintained by HDRvision. Automated via Codex. Validated on GitHub Actions macOS runners.",
            "",
        ]
    )


def placeholder_index_contents(start_major: int, end_major: int) -> str:
    versions = ", ".join(f"iOS {major}.0" for major in range(start_major, end_major + 1))
    return "\n".join(
        [
            "# Future Version Placeholders",
            "",
            "This directory keeps forward-looking placeholders so contributors can see which iOS major versions",
            "still need verified DeviceSupport archives.",
            "",
            f"Reserved versions: {versions}.",
            "",
        ]
    )


def ensure_placeholder_versions(
    placeholder_root: Path = PLACEHOLDER_ROOT,
    start_major: int = DEFAULT_PLACEHOLDER_START_MAJOR,
    end_major: int = DEFAULT_PLACEHOLDER_END_MAJOR,
    check_only: bool = False,
) -> list[Path]:
    if end_major < start_major:
        raise DeploymentError("--end-major must be greater than or equal to --start-major.")

    planned_paths: list[Path] = []
    paths_to_write: dict[Path, str] = {
        placeholder_root / "README.md": placeholder_index_contents(start_major, end_major)
    }

    for major in range(start_major, end_major + 1):
        version = f"{major}.0"
        target_path = placeholder_root / version / "PLACEHOLDER.md"
        planned_paths.append(target_path)
        paths_to_write[target_path] = placeholder_file_contents(version)

    missing_or_stale = [
        path
        for path, content in paths_to_write.items()
        if not path.is_file() or read_text(path) != content
    ]

    if check_only and missing_or_stale:
        raise DeploymentError(
            "Placeholder directories are missing or stale. "
            f"Run 'python deploy.py ensure-placeholders --start-major {start_major} --end-major {end_major}'."
        )

    if not check_only:
        for path, content in paths_to_write.items():
            write_text(path, content)

    return planned_paths


def read_xcode_version(app_path: Path) -> tuple[str | None, bool]:
    info_plist_path = app_path / "Contents" / "Info.plist"
    if not info_plist_path.is_file():
        return None, "beta" in app_path.name.lower()

    try:
        with info_plist_path.open("rb") as handle:
            info = plistlib.load(handle)
    except (plistlib.InvalidFileException, OSError):
        return None, "beta" in app_path.name.lower()

    bundle_name = str(info.get("CFBundleName", "")).lower()
    version = info.get("CFBundleShortVersionString") or info.get("CFBundleVersion")
    is_beta = "beta" in app_path.name.lower() or "beta" in bundle_name
    return str(version) if version else None, is_beta


def installation_from_app(app_path: Path, source: str) -> XcodeInstallation:
    version, is_beta = read_xcode_version(app_path)
    developer_dir = app_path / "Contents" / "Developer"
    return XcodeInstallation(
        source=source,
        app_path=app_path,
        developer_dir=developer_dir,
        device_support_dir=developer_dir / DEVICE_SUPPORT_RELATIVE,
        display_name=app_path.name,
        version=version,
        is_beta=is_beta,
    )


def installation_from_developer_dir(developer_dir: Path, source: str) -> XcodeInstallation:
    app_path: Path | None = None
    if developer_dir.name == "Developer" and developer_dir.parent.name == "Contents":
        possible_app = developer_dir.parent.parent
        if possible_app.suffix.lower() == ".app":
            app_path = possible_app

    if app_path:
        version, is_beta = read_xcode_version(app_path)
        display_name = app_path.name
    else:
        version = None
        is_beta = False
        display_name = developer_dir.name

    return XcodeInstallation(
        source=source,
        app_path=app_path,
        developer_dir=developer_dir,
        device_support_dir=developer_dir / DEVICE_SUPPORT_RELATIVE,
        display_name=display_name,
        version=version,
        is_beta=is_beta,
    )


def installation_from_device_support_dir(device_support_dir: Path, source: str) -> XcodeInstallation:
    developer_dir = device_support_dir.parents[2]
    return installation_from_developer_dir(developer_dir=developer_dir, source=source)


def normalize_installation_target(raw_target: Path, source: str) -> XcodeInstallation:
    target = raw_target.expanduser().resolve(strict=False)
    if not target.exists():
        raise FileNotFoundError(f"Path not found: '{target}'")

    if target.is_dir() and target.suffix.lower() == ".app":
        return installation_from_app(target, source=source)

    if target.is_dir() and target.name == "Developer" and target.parent.name == "Contents":
        return installation_from_developer_dir(target, source=source)

    if (
        target.is_dir()
        and target.name == "DeviceSupport"
        and target.parent.name == "iPhoneOS.platform"
        and len(target.parents) >= 3
    ):
        return installation_from_device_support_dir(target, source=source)

    if (target / "Contents" / "Developer").is_dir():
        return installation_from_app(target, source=source)

    if (target / DEVICE_SUPPORT_RELATIVE).is_dir():
        return installation_from_developer_dir(target, source=source)

    raise XcodeDiscoveryError(
        "Target must point to an Xcode .app bundle, a Contents/Developer directory, "
        "or a Platforms/iPhoneOS.platform/DeviceSupport directory."
    )


def discover_selected_developer_dir() -> Path | None:
    try:
        result = subprocess.run(
            ["xcode-select", "-p"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None

    if result.returncode != 0:
        return None

    output = result.stdout.strip()
    return Path(output) if output else None


def iter_scanned_xcode_apps() -> Iterable[Path]:
    search_roots = [Path("/Applications"), Path.home() / "Applications"]
    candidates: list[Path] = []

    for root in search_roots:
        if not root.is_dir():
            continue
        for entry in root.iterdir():
            if entry.is_dir() and XCODE_APP_PATTERN.match(entry.name):
                candidates.append(entry)

    def sort_key(app_path: Path) -> tuple[tuple[int, ...], int, int, str]:
        version, is_beta = read_xcode_version(app_path)
        return (
            version_sort_key(version),
            1 if app_path.name == "Xcode.app" else 0,
            1 if not is_beta else 0,
            app_path.name.lower(),
        )

    return sorted(candidates, key=sort_key, reverse=True)


def discover_xcode_installations() -> list[XcodeInstallation]:
    discovered: list[XcodeInstallation] = []
    seen: set[Path] = set()

    def add(candidate: XcodeInstallation) -> None:
        key = candidate.developer_dir.resolve(strict=False)
        if key not in seen:
            seen.add(key)
            discovered.append(candidate)

    developer_dir_from_env = os.environ.get("DEVELOPER_DIR")
    if developer_dir_from_env:
        try:
            add(normalize_installation_target(Path(developer_dir_from_env), source="DEVELOPER_DIR"))
        except (DeploymentError, FileNotFoundError):
            pass

    selected_developer_dir = discover_selected_developer_dir()
    if selected_developer_dir:
        try:
            add(normalize_installation_target(selected_developer_dir, source="xcode-select"))
        except (DeploymentError, FileNotFoundError):
            pass

    for app_path in iter_scanned_xcode_apps():
        try:
            add(normalize_installation_target(app_path, source="scan"))
        except (DeploymentError, FileNotFoundError):
            continue

    return discovered


def choose_xcode_installation(target: Path | None) -> XcodeInstallation:
    if target is not None:
        candidate = normalize_installation_target(target, source="explicit")
        if not candidate.device_support_dir.is_dir():
            raise XcodeDiscoveryError(
                f"Xcode target was found, but the iPhoneOS DeviceSupport directory does not exist at "
                f"'{candidate.device_support_dir}'."
            )
        return candidate

    if platform.system() != "Darwin":
        raise XcodeDiscoveryError(
            "Automatic Xcode discovery only works on macOS. "
            "Pass --target when validating against a mock Xcode bundle on another platform."
        )

    candidates = discover_xcode_installations()
    ready_candidates = [candidate for candidate in candidates if candidate.is_ready]
    if ready_candidates:
        return ready_candidates[0]

    if candidates:
        details = "\n".join(
            f"  - {candidate.display_name}: expected DeviceSupport at {candidate.device_support_dir}"
            for candidate in candidates
        )
        raise XcodeDiscoveryError(
            "Xcode-like paths were found, but none exposed an iPhoneOS DeviceSupport directory:\n"
            f"{details}"
        )

    raise XcodeDiscoveryError(
        "No Xcode installation was found. Set DEVELOPER_DIR, run xcode-select, or pass --target."
    )


def archive_root_entries(archive_path: Path) -> tuple[str, ...]:
    roots: set[str] = set()
    with zipfile.ZipFile(archive_path, "r") as archive:
        for member in archive.namelist():
            parts = PurePosixPath(member).parts
            if not parts:
                continue
            root = parts[0]
            if root == "__MACOSX":
                continue
            roots.add(root)

    if not roots:
        roots.add(archive_path.stem)

    return tuple(sorted(roots))


def iter_archives(
    device_support_root: Path = DEVICE_SUPPORT_ROOT,
    version_filter: str | None = None,
) -> list[ArchivePlan]:
    ensure_repository_layout(device_support_root)
    archives: list[ArchivePlan] = []

    for entry in sorted(device_support_root.iterdir(), key=lambda path: path.name.lower()):
        if not (entry.is_file() and entry.suffix.lower() == ".zip"):
            continue
        version = extract_version(entry.stem)
        if not version:
            continue
        if version_filter and version_filter not in entry.stem:
            continue
        archives.append(
            ArchivePlan(
                archive_path=entry,
                display_name=entry.stem,
                version=version,
                root_entries=archive_root_entries(entry),
            )
        )

    archives.sort(key=lambda archive: (version_sort_key(archive.version), archive.display_name))
    return archives


def build_install_plan(
    installation: XcodeInstallation,
    device_support_root: Path = DEVICE_SUPPORT_ROOT,
    version_filter: str | None = None,
) -> tuple[list[ArchivePlan], list[ArchivePlan]]:
    try:
        existing_entries = {entry.name for entry in installation.device_support_dir.iterdir()}
    except PermissionError as exc:
        raise PermissionError(
            f"Permission denied while reading '{installation.device_support_dir}'. "
            "Run the script with elevated privileges if your Xcode.app is protected."
        ) from exc

    matched_archives = iter_archives(device_support_root=device_support_root, version_filter=version_filter)
    pending_archives = [
        archive
        for archive in matched_archives
        if not all(root in existing_entries for root in archive.root_entries)
    ]
    return matched_archives, pending_archives


def ensure_within_directory(base_directory: Path, candidate_path: Path) -> None:
    base_resolved = base_directory.resolve(strict=False)
    candidate_resolved = candidate_path.resolve(strict=False)
    try:
        candidate_resolved.relative_to(base_resolved)
    except ValueError as exc:
        raise DeploymentError(
            f"Archive entry would escape the target directory: '{candidate_path}'."
        ) from exc


def extract_archive(archive: ArchivePlan, target_directory: Path) -> None:
    try:
        with zipfile.ZipFile(archive.archive_path, "r") as handle:
            for member in handle.infolist():
                destination = target_directory / member.filename
                ensure_within_directory(target_directory, destination)
            handle.extractall(target_directory)
    except PermissionError as exc:
        raise PermissionError(
            f"Permission denied while extracting '{archive.archive_path.name}' into '{target_directory}'. "
            "Run the script with elevated privileges if your Xcode.app is protected."
        ) from exc


def execute_install_plan(pending_archives: list[ArchivePlan], target_directory: Path, dry_run: bool) -> None:
    if dry_run:
        return
    for archive in pending_archives:
        extract_archive(archive, target_directory)


def build_install_report(
    installation: XcodeInstallation,
    matched_archives: list[ArchivePlan],
    pending_archives: list[ArchivePlan],
    dry_run: bool,
    archive_root: Path,
) -> dict[str, object]:
    return {
        "operation": "install",
        "dry_run": dry_run,
        "selected_xcode": installation.to_dict(),
        "archive_root": str(archive_root),
        "archive_count": len(matched_archives),
        "matching_archives": [archive.to_dict() for archive in matched_archives],
        "pending_archive_count": len(pending_archives),
        "pending_archives": [archive.to_dict() for archive in pending_archives],
    }


def print_install_report(report: dict[str, object]) -> None:
    selected_xcode = report["selected_xcode"]
    assert isinstance(selected_xcode, dict)

    print(
        f"Selected Xcode: {selected_xcode['display_name']} "
        f"({selected_xcode.get('version') or 'unknown version'})"
    )
    print(f"Discovery source: {selected_xcode['source']}")
    print(f"Developer directory: {selected_xcode['developer_dir']}")
    print(f"DeviceSupport directory: {selected_xcode['device_support_dir']}")
    print(f"Matching archives: {report['archive_count']}")
    print(f"Pending archives: {report['pending_archive_count']}")

    pending_archives = report["pending_archives"]
    assert isinstance(pending_archives, list)
    if pending_archives:
        print("")
        print("Archives queued for installation:")
        for archive in pending_archives:
            assert isinstance(archive, dict)
            print(f"  - {archive['display_name']}.zip")
    else:
        print("")
        print("No new archives need to be installed.")

    if report["dry_run"]:
        print("")
        print("Dry run complete. No files were written.")


def render_inventory_report(inventory: list[SupportVersion], as_json: bool) -> None:
    if as_json:
        payload = {
            "versions": [item.to_dict() for item in inventory],
            "latest_actual_version": next(
                (item.version for item in reversed(inventory) if item.artifact_count),
                None,
            ),
            "furthest_placeholder_version": next(
                (item.version for item in reversed(inventory) if item.placeholder_directories),
                None,
            ),
        }
        print(json.dumps(payload, indent=2))
        return

    print(render_support_table(inventory))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Install iOS DeviceSupport archives into Xcode, generate placeholder directories, "
            "and keep README.md synchronized with the repository inventory."
        )
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("install", "inventory", "sync-readme", "ensure-placeholders"),
        default="install",
        help="Operation to run. Defaults to 'install'.",
    )
    parser.add_argument(
        "-t",
        "--target",
        type=Path,
        default=None,
        help="Path to an Xcode .app, Contents/Developer, or DeviceSupport directory.",
    )
    parser.add_argument(
        "-v",
        "--version",
        type=str,
        default=None,
        help="Only use archives whose names contain this version filter.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect Xcode and plan archive installation without extracting any files.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human-readable output.",
    )
    parser.add_argument(
        "--device-support-root",
        type=Path,
        default=DEVICE_SUPPORT_ROOT,
        help="Override the repository DeviceSupport root.",
    )
    parser.add_argument(
        "--placeholder-root",
        type=Path,
        default=PLACEHOLDER_ROOT,
        help="Override the placeholder directory root.",
    )
    parser.add_argument(
        "--readme",
        type=Path,
        default=README_PATH,
        help="README file to update or verify.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify generated files are current without modifying them.",
    )
    parser.add_argument(
        "--start-major",
        type=int,
        default=DEFAULT_PLACEHOLDER_START_MAJOR,
        help="Starting iOS major version for placeholder generation.",
    )
    parser.add_argument(
        "--end-major",
        type=int,
        default=DEFAULT_PLACEHOLDER_END_MAJOR,
        help="Ending iOS major version for placeholder generation.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "inventory":
            inventory = scan_support_inventory(
                device_support_root=args.device_support_root,
                placeholder_root=args.placeholder_root,
            )
            render_inventory_report(inventory, as_json=args.json)
            return 0

        if args.command == "sync-readme":
            changed = sync_readme(
                readme_path=args.readme,
                device_support_root=args.device_support_root,
                placeholder_root=args.placeholder_root,
                check_only=args.check,
            )
            if args.json:
                print(
                    json.dumps(
                        {
                            "operation": "sync-readme",
                            "changed": changed,
                            "readme": str(args.readme),
                            "check_only": args.check,
                        },
                        indent=2,
                    )
                )
            elif changed:
                print(f"Updated README support matrix in {args.readme}.")
            else:
                print(f"README support matrix is already current in {args.readme}.")
            return 0

        if args.command == "ensure-placeholders":
            created_or_verified = ensure_placeholder_versions(
                placeholder_root=args.placeholder_root,
                start_major=args.start_major,
                end_major=args.end_major,
                check_only=args.check,
            )
            if args.json:
                print(
                    json.dumps(
                        {
                            "operation": "ensure-placeholders",
                            "check_only": args.check,
                            "placeholder_root": str(args.placeholder_root),
                            "paths": [str(path) for path in created_or_verified],
                        },
                        indent=2,
                    )
                )
            else:
                action = "Verified" if args.check else "Ensured"
                print(
                    f"{action} placeholder directories for iOS {args.start_major}.0 "
                    f"through iOS {args.end_major}.0 in {args.placeholder_root}."
                )
            return 0

        if args.check:
            parser.error("--check is only valid with 'sync-readme' or 'ensure-placeholders'.")

        installation = choose_xcode_installation(args.target)
        matched_archives, pending_archives = build_install_plan(
            installation=installation,
            device_support_root=args.device_support_root,
            version_filter=args.version,
        )
        execute_install_plan(
            pending_archives=pending_archives,
            target_directory=installation.device_support_dir,
            dry_run=args.dry_run,
        )
        report = build_install_report(
            installation=installation,
            matched_archives=matched_archives,
            pending_archives=pending_archives,
            dry_run=args.dry_run,
            archive_root=args.device_support_root,
        )
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_install_report(report)
        return 0
    except (DeploymentError, FileNotFoundError, PermissionError, zipfile.BadZipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
