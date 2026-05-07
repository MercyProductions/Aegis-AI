from __future__ import annotations

import re
import textwrap

from .project_scaffold_targets import title_from_name as scaffold_title_from_name


def python_game_file_analyzer_template(project_name: str) -> dict[str, str]:
    package_name = _python_package_name(project_name)
    title = _title_from_name(project_name)
    analyzer_py = _strip(
        """
        from __future__ import annotations

        import hashlib
        import json
        import math
        import string
        from dataclasses import asdict, dataclass
        from pathlib import Path
        from typing import Iterable


        SIGNATURES: tuple[tuple[bytes, str], ...] = (
            (b"\\x89PNG\\r\\n\\x1a\\n", "png-image"),
            (b"DDS ", "directdraw-surface"),
            (b"RIFF", "riff-container"),
            (b"OggS", "ogg-audio"),
            (b"PK\\x03\\x04", "zip-or-packed-archive"),
            (b"MZ", "portable-executable"),
            (b"\\x7fELF", "elf-binary"),
            (b"SQLite format 3\\x00", "sqlite-database"),
            (b"{", "json-or-text"),
        )


        @dataclass(frozen=True)
        class FileAnalysis:
            path: str
            size: int
            sha256: str
            extension: str
            detected_format: str
            entropy: float
            first_bytes_hex: str
            strings: list[str]

            def to_dict(self) -> dict[str, object]:
                return asdict(self)


        def shannon_entropy(data: bytes) -> float:
            if not data:
                return 0.0
            counts = [0] * 256
            for byte in data:
                counts[byte] += 1
            entropy = 0.0
            length = len(data)
            for count in counts:
                if count:
                    probability = count / length
                    entropy -= probability * math.log2(probability)
            return round(entropy, 4)


        def extract_strings(data: bytes, *, minimum: int = 4, limit: int = 40) -> list[str]:
            printable = set(string.printable.encode("ascii"))
            found: list[str] = []
            current = bytearray()
            for byte in data:
                if byte in printable and byte not in b"\\r\\n\\t\\x0b\\x0c":
                    current.append(byte)
                    continue
                if len(current) >= minimum:
                    found.append(current.decode("ascii", errors="replace"))
                    if len(found) >= limit:
                        return found
                current.clear()
            if len(current) >= minimum and len(found) < limit:
                found.append(current.decode("ascii", errors="replace"))
            return found


        def detect_format(data: bytes, path: Path) -> str:
            for magic, label in SIGNATURES:
                if data.startswith(magic):
                    if label == "riff-container" and len(data) >= 12:
                        subtype = data[8:12].decode("ascii", errors="replace").strip()
                        return f"riff-{subtype.lower() or 'container'}"
                    return label
            extension_map = {
                ".pak": "game-package",
                ".wad": "wad-archive",
                ".bundle": "asset-bundle",
                ".bank": "audio-bank",
                ".uasset": "unreal-asset",
                ".unity3d": "unity-asset-bundle",
                ".dat": "data-blob",
                ".bin": "binary-blob",
            }
            return extension_map.get(path.suffix.lower(), "unknown")


        def analyze_file(path: str | Path) -> FileAnalysis:
            file_path = Path(path)
            data = file_path.read_bytes()
            return FileAnalysis(
                path=str(file_path),
                size=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                extension=file_path.suffix.lower(),
                detected_format=detect_format(data, file_path),
                entropy=shannon_entropy(data),
                first_bytes_hex=data[:32].hex(" "),
                strings=extract_strings(data),
            )


        def iter_files(root: str | Path) -> Iterable[Path]:
            root_path = Path(root)
            if root_path.is_file():
                yield root_path
                return
            for path in sorted(root_path.rglob("*")):
                if path.is_file():
                    yield path


        def analyze_tree(root: str | Path, *, max_files: int = 500) -> dict[str, object]:
            root_path = Path(root)
            files = [analyze_file(path).to_dict() for path in list(iter_files(root_path))[:max_files]]
            formats: dict[str, int] = {}
            for file in files:
                detected = str(file["detected_format"])
                formats[detected] = formats.get(detected, 0) + 1
            return {
                "root": str(root_path),
                "file_count": len(files),
                "formats": formats,
                "files": files,
            }


        def to_json_report(payload: dict[str, object]) -> str:
            return json.dumps(payload, indent=2, sort_keys=True)
        """
    )
    cli_py = _strip(
        """
        from __future__ import annotations

        import argparse
        from pathlib import Path

        from .analyzer import analyze_tree, to_json_report


        def build_parser() -> argparse.ArgumentParser:
            parser = argparse.ArgumentParser(description="Analyze owned or authorized game files and asset folders.")
            parser.add_argument("target", help="File or folder to analyze.")
            parser.add_argument("--json", dest="json_path", help="Optional path for a JSON report.")
            parser.add_argument("--max-files", type=int, default=500, help="Maximum files to scan in a folder.")
            return parser


        def main(argv: list[str] | None = None) -> int:
            args = build_parser().parse_args(argv)
            report = analyze_tree(args.target, max_files=args.max_files)
            output = to_json_report(report)
            print(output)
            if args.json_path:
                Path(args.json_path).write_text(output + "\\n", encoding="utf-8")
            return 0


        if __name__ == "__main__":
            raise SystemExit(main())
        """
    )
    test_py = _strip(
        """
        from pathlib import Path
        import tempfile
        import unittest

        from __PACKAGE__.analyzer import analyze_file, analyze_tree


        ROOT = Path(__file__).resolve().parents[1]


        class AnalyzerTests(unittest.TestCase):
            def test_sample_asset_extracts_strings_and_hash(self) -> None:
                result = analyze_file(ROOT / "samples" / "sample_asset.bin")

                self.assertEqual(result.extension, ".bin")
                self.assertEqual(result.detected_format, "binary-blob")
                self.assertEqual(len(result.sha256), 64)
                self.assertIn("AEGIS_SAMPLE_ASSET", result.strings)

            def test_tree_report_counts_formats(self) -> None:
                with tempfile.TemporaryDirectory() as tempdir:
                    root = Path(tempdir)
                    (root / "texture.dds").write_bytes(b"DDS " + bytes(range(16)))
                    (root / "bundle.pak").write_bytes(b"PACKED_ASSET_TABLE")

                    report = analyze_tree(root)

                self.assertEqual(report["file_count"], 2)
                self.assertEqual(report["formats"]["directdraw-surface"], 1)
                self.assertEqual(report["formats"]["game-package"], 1)


        if __name__ == "__main__":
            unittest.main()
        """
    ).replace("__PACKAGE__", package_name)
    build_py = _strip(
        f"""
        from __future__ import annotations

        import compileall
        import subprocess
        import sys
        from pathlib import Path


        ROOT = Path(__file__).resolve().parent


        def run(command: list[str]) -> int:
            print("Running:", " ".join(command))
            completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
            if completed.stdout:
                print(completed.stdout, end="")
            if completed.stderr:
                print(completed.stderr, end="", file=sys.stderr)
            return completed.returncode


        def main() -> int:
            if not compileall.compile_dir(str(ROOT / "{package_name}"), quiet=1):
                return 1

            code = run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
            if code != 0:
                return code

            report_path = ROOT / "analysis-report.json"
            code = run([
                sys.executable,
                "-m",
                "{package_name}.cli",
                "samples",
                "--json",
                str(report_path),
            ])
            if code != 0:
                return code
            if not report_path.exists():
                print("Expected analysis report was not written.", file=sys.stderr)
                return 2
            print("Game file analyzer validation passed")
            return 0


        if __name__ == "__main__":
            raise SystemExit(main())
        """
    )
    return {
        f"{package_name}/__init__.py": "__all__ = [\"analyzer\"]\n",
        f"{package_name}/analyzer.py": analyzer_py,
        f"{package_name}/cli.py": cli_py,
        "tests/test_analyzer.py": test_py,
        "samples/sample_asset.bin": "AEGIS_SAMPLE_ASSET\nmesh=training_cube\ntexture=debug_grid\n",
        "build.py": build_py,
        ".gitignore": _strip(
            """
            __pycache__
            .pytest_cache
            analysis-report.json
            *.pyc
            """
        ),
        "README.md": _strip(
            f"""
            # {title}

            Dependency-free Python toolkit for analyzing owned or authorized game files,
            asset bundles, binary blobs, and custom file formats.

            ## Capabilities

            - Magic-byte and extension based format guesses.
            - SHA-256 hashing, size, first-byte previews, printable string extraction, and entropy.
            - Folder reports for asset-pack and file-format triage.
            - JSON output for follow-up tooling.

            ## Validate

            ```powershell
            python build.py
            ```

            ## Run

            ```powershell
            python -m {package_name}.cli samples --json analysis-report.json
            ```
            """
        ),
    }

def python_sln_refactor_tool_template(project_name: str) -> dict[str, str]:
    package_name = _python_package_name(project_name)
    title = _title_from_name(project_name)
    sln_py = _strip(
        r"""
        from __future__ import annotations

        import json
        import re
        import shutil
        import xml.etree.ElementTree as ET
        from dataclasses import dataclass
        from pathlib import Path
        from pathlib import PureWindowsPath


        PROJECT_RE = re.compile(
            r'^\s*Project\("(?P<type_guid>[^"]+)"\) = "(?P<name>[^"]+)", "(?P<path>[^"]+)", "(?P<guid>[^"]+)"$',
            re.MULTILINE,
        )


        @dataclass(frozen=True)
        class SolutionProject:
            type_guid: str
            name: str
            path: str
            guid: str
            source_solution: str = ""


        @dataclass(frozen=True)
        class SolutionDocument:
            path: Path
            projects: list[SolutionProject]


        @dataclass(frozen=True)
        class MaterializeReport:
            output_solution: str
            project_count: int
            copied_projects: int
            included_references: int
            missing_projects: list[str]

            def to_json(self) -> str:
                return json.dumps(
                    {
                        "output_solution": self.output_solution,
                        "project_count": self.project_count,
                        "copied_projects": self.copied_projects,
                        "included_references": self.included_references,
                        "missing_projects": self.missing_projects,
                    },
                    indent=2,
                    sort_keys=True,
                )


        @dataclass(frozen=True)
        class VcxProjectAnalysis:
            path: str
            name: str
            root_namespace: str
            configuration_types: list[str]
            platform_toolsets: list[str]
            imports: list[str]
            property_sheets: list[str]
            project_references: list[str]
            include_directories: list[str]
            library_directories: list[str]
            additional_dependencies: list[str]
            source_files: list[str]
            header_files: list[str]
            resource_files: list[str]
            unresolved_macros: list[str]

            def to_dict(self) -> dict[str, object]:
                return {
                    "path": self.path,
                    "name": self.name,
                    "root_namespace": self.root_namespace,
                    "configuration_types": self.configuration_types,
                    "platform_toolsets": self.platform_toolsets,
                    "imports": self.imports,
                    "property_sheets": self.property_sheets,
                    "project_references": self.project_references,
                    "include_directories": self.include_directories,
                    "library_directories": self.library_directories,
                    "additional_dependencies": self.additional_dependencies,
                    "source_files": self.source_files,
                    "header_files": self.header_files,
                    "resource_files": self.resource_files,
                    "unresolved_macros": self.unresolved_macros,
                }

            def to_json(self) -> str:
                return json.dumps(self.to_dict(), indent=2, sort_keys=True)


        @dataclass(frozen=True)
        class SolutionGraph:
            path: str
            project_count: int
            edges: dict[str, list[str]]
            build_order: list[str]
            cycles: list[list[str]]
            missing_references: list[str]

            def to_dict(self) -> dict[str, object]:
                return {
                    "path": self.path,
                    "project_count": self.project_count,
                    "edges": self.edges,
                    "build_order": self.build_order,
                    "cycles": self.cycles,
                    "missing_references": self.missing_references,
                }

            def to_json(self) -> str:
                return json.dumps(self.to_dict(), indent=2, sort_keys=True)


        def parse_projects(text: str, *, source_solution: str | Path = "") -> list[SolutionProject]:
            source = str(source_solution) if source_solution else ""
            return [
                SolutionProject(
                    type_guid=match.group("type_guid"),
                    name=match.group("name"),
                    path=match.group("path"),
                    guid=match.group("guid"),
                    source_solution=source,
                )
                for match in PROJECT_RE.finditer(text)
            ]


        def read_solution(path: str | Path) -> list[SolutionProject]:
            return read_solution_document(path).projects


        def read_solution_document(path: str | Path) -> SolutionDocument:
            solution = Path(path).resolve()
            text = solution.read_text(encoding="utf-8", errors="replace")
            return SolutionDocument(path=solution, projects=parse_projects(text, source_solution=solution))


        def _solution_relative_path(value: str) -> Path:
            parsed = PureWindowsPath(value)
            if parsed.is_absolute() or parsed.drive:
                raise ValueError(f"solution project path must be relative: {value}")
            parts = [part for part in parsed.parts if part not in ("", "\\", "/")]
            if not parts or any(part == ".." for part in parts):
                raise ValueError(f"solution project path escapes the workspace: {value}")
            return Path(*parts)


        def _project_file_path(base: Path, project: SolutionProject) -> Path:
            return base / _solution_relative_path(project.path)


        def _project_absolute_path(project: SolutionProject) -> Path | None:
            if not project.source_solution:
                return None
            return _project_file_path(Path(project.source_solution).parent, project).resolve()


        def _dedupe_projects(projects: list[SolutionProject]) -> list[SolutionProject]:
            unique: dict[str, SolutionProject] = {}
            for project in projects:
                unique.setdefault(project.guid.upper(), project)
            return list(unique.values())


        def render_solution(projects: list[SolutionProject], *, solution_guid: str = "{00000000-0000-0000-0000-000000000001}") -> str:
            unique = _dedupe_projects(projects)

            lines = [
                "Microsoft Visual Studio Solution File, Format Version 12.00",
                "# Visual Studio Version 17",
                "VisualStudioVersion = 17.0.31903.59",
                "MinimumVisualStudioVersion = 10.0.40219.1",
            ]
            for project in unique:
                lines.append(f'Project("{project.type_guid}") = "{project.name}", "{project.path}", "{project.guid}"')
                lines.append("EndProject")
            lines.extend(
                [
                    "Global",
                    "\tGlobalSection(SolutionConfigurationPlatforms) = preSolution",
                    "\t\tDebug|x64 = Debug|x64",
                    "\t\tRelease|x64 = Release|x64",
                    "\tEndGlobalSection",
                    "\tGlobalSection(ProjectConfigurationPlatforms) = postSolution",
                ]
            )
            for project in unique:
                guid = project.guid
                lines.extend(
                    [
                        f"\t\t{guid}.Debug|x64.ActiveCfg = Debug|x64",
                        f"\t\t{guid}.Debug|x64.Build.0 = Debug|x64",
                        f"\t\t{guid}.Release|x64.ActiveCfg = Release|x64",
                        f"\t\t{guid}.Release|x64.Build.0 = Release|x64",
                    ]
                )
            lines.extend(
                [
                    "\tEndGlobalSection",
                    "\tGlobalSection(SolutionProperties) = preSolution",
                    "\t\tHideSolutionNode = FALSE",
                    "\tEndGlobalSection",
                    "\tGlobalSection(ExtensibilityGlobals) = postSolution",
                    f"\t\tSolutionGuid = {solution_guid}",
                    "\tEndGlobalSection",
                    "EndGlobal",
                    "",
                ]
            )
            return "\n".join(lines)


        def merge_solutions(paths: list[str | Path]) -> str:
            projects: list[SolutionProject] = []
            for path in paths:
                projects.extend(read_solution(path))
            return render_solution(projects)


        def split_solution(path: str | Path, project_names: list[str]) -> str:
            wanted = {name.lower() for name in project_names}
            projects = [project for project in read_solution(path) if project.name.lower() in wanted]
            if not projects:
                raise ValueError("no matching projects found in solution")
            return render_solution(projects)


        def _resolve_project_reference(project_file: Path, reference: str) -> Path:
            parsed = PureWindowsPath(reference)
            if parsed.is_absolute() or parsed.drive:
                return Path(str(parsed)).resolve()
            return (project_file.parent / Path(*parsed.parts)).resolve()


        def _expand_project_references(projects: list[SolutionProject], document: SolutionDocument) -> list[SolutionProject]:
            by_path: dict[Path, SolutionProject] = {}
            for candidate in document.projects:
                absolute = _project_absolute_path(candidate)
                if absolute is not None:
                    by_path[absolute] = candidate

            expanded: list[SolutionProject] = []
            seen_guids: set[str] = set()
            queue = list(projects)
            while queue:
                project = queue.pop(0)
                guid = project.guid.upper()
                if guid in seen_guids:
                    continue
                seen_guids.add(guid)
                expanded.append(project)

                project_file = _project_absolute_path(project)
                if project_file is None or project_file.suffix.lower() != ".vcxproj" or not project_file.exists():
                    continue
                for reference in analyze_vcxproj(project_file).project_references:
                    referenced_file = _resolve_project_reference(project_file, reference)
                    referenced = by_path.get(referenced_file)
                    if referenced is not None and referenced.guid.upper() not in seen_guids:
                        queue.append(referenced)
            return expanded


        def _copy_project_folder(project: SolutionProject, output_dir: Path) -> tuple[bool, str]:
            if not project.source_solution:
                return False, f"{project.name}: missing source solution"

            source_solution = Path(project.source_solution)
            source_project = _project_file_path(source_solution.parent, project)
            destination_project = _project_file_path(output_dir, project)
            if not source_project.exists():
                return False, f"{project.name}: missing {source_project}"

            destination_project.parent.mkdir(parents=True, exist_ok=True)
            if source_project.parent == source_solution.parent:
                shutil.copy2(source_project, destination_project)
                return True, str(destination_project)

            shutil.copytree(source_project.parent, destination_project.parent, dirs_exist_ok=True)
            return True, str(destination_project)


        def materialize_merge(
            paths: list[str | Path],
            out_solution: str | Path,
            *,
            copy_projects: bool = False,
            include_references: bool = False,
        ) -> MaterializeReport:
            output = Path(out_solution)
            output.parent.mkdir(parents=True, exist_ok=True)
            projects: list[SolutionProject] = []
            reference_count = 0
            for path in paths:
                document = read_solution_document(path)
                base_projects = document.projects
                expanded = _expand_project_references(base_projects, document) if include_references else base_projects
                reference_count += max(0, len(_dedupe_projects(expanded)) - len(_dedupe_projects(base_projects)))
                projects.extend(expanded)

            unique = _dedupe_projects(projects)
            output.write_text(render_solution(unique), encoding="utf-8")
            copied = 0
            missing: list[str] = []
            if copy_projects:
                for project in unique:
                    ok, message = _copy_project_folder(project, output.parent)
                    if ok:
                        copied += 1
                    else:
                        missing.append(message)
            return MaterializeReport(str(output), len(unique), copied, reference_count, missing)


        def materialize_split(
            path: str | Path,
            project_names: list[str],
            out_solution: str | Path,
            *,
            copy_projects: bool = False,
            include_references: bool = False,
        ) -> MaterializeReport:
            document = read_solution_document(path)
            wanted = {name.lower() for name in project_names}
            projects = [project for project in document.projects if project.name.lower() in wanted]
            if not projects:
                raise ValueError("no matching projects found in solution")
            base_count = len(_dedupe_projects(projects))
            if include_references:
                projects = _expand_project_references(projects, document)
            reference_count = max(0, len(_dedupe_projects(projects)) - base_count)

            output = Path(out_solution)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(render_solution(projects), encoding="utf-8")
            copied = 0
            missing: list[str] = []
            if copy_projects:
                for project in projects:
                    ok, message = _copy_project_folder(project, output.parent)
                    if ok:
                        copied += 1
                    else:
                        missing.append(message)
            return MaterializeReport(str(output), len(_dedupe_projects(projects)), copied, reference_count, missing)


        def _xml_local_name(tag: str) -> str:
            return tag.rsplit("}", 1)[-1] if "}" in tag else tag


        def _node_texts(root: ET.Element, name: str) -> list[str]:
            values: list[str] = []
            for node in root.iter():
                if _xml_local_name(node.tag) != name:
                    continue
                text = (node.text or "").strip()
                if text:
                    values.append(text)
            return _dedupe_text(values)


        def _node_includes(root: ET.Element, name: str) -> list[str]:
            values: list[str] = []
            for node in root.iter():
                if _xml_local_name(node.tag) != name:
                    continue
                include = (node.attrib.get("Include") or "").strip()
                if include:
                    values.append(include)
            return _dedupe_text(values)


        def _split_msbuild_list(values: list[str]) -> list[str]:
            parts: list[str] = []
            for value in values:
                for part in value.split(";"):
                    part = part.strip()
                    if not part or part.startswith("%("):
                        continue
                    parts.append(part)
            return _dedupe_text(parts)


        def _dedupe_text(values: list[str]) -> list[str]:
            result: list[str] = []
            seen: set[str] = set()
            for value in values:
                if value in seen:
                    continue
                seen.add(value)
                result.append(value)
            return result


        def _macro_values(values: list[str]) -> list[str]:
            macros: list[str] = []
            for value in values:
                macros.extend(re.findall(r"\$\([^)]+\)", value))
            return _dedupe_text(macros)


        def analyze_vcxproj(path: str | Path) -> VcxProjectAnalysis:
            project = Path(path).resolve()
            tree = ET.parse(project)
            root = tree.getroot()

            imports: list[str] = []
            property_sheets: list[str] = []
            for node in root.iter():
                if _xml_local_name(node.tag) != "Import":
                    continue
                value = (node.attrib.get("Project") or "").strip()
                if not value:
                    continue
                imports.append(value)
                parent_label = (node.attrib.get("Label") or "").strip().lower()
                if "props" in value.lower() or parent_label == "propertysheets":
                    property_sheets.append(value)

            include_directories = _split_msbuild_list(_node_texts(root, "AdditionalIncludeDirectories"))
            library_directories = _split_msbuild_list(_node_texts(root, "AdditionalLibraryDirectories"))
            additional_dependencies = _split_msbuild_list(_node_texts(root, "AdditionalDependencies"))
            source_files = _node_includes(root, "ClCompile")
            header_files = _node_includes(root, "ClInclude")
            resource_files = _node_includes(root, "ResourceCompile")
            project_references = _node_includes(root, "ProjectReference")
            configuration_types = _node_texts(root, "ConfigurationType")
            platform_toolsets = _node_texts(root, "PlatformToolset")
            root_namespaces = _node_texts(root, "RootNamespace")
            macro_source = (
                imports
                + property_sheets
                + project_references
                + include_directories
                + library_directories
                + additional_dependencies
                + source_files
                + header_files
                + resource_files
            )

            return VcxProjectAnalysis(
                path=str(project),
                name=project.stem,
                root_namespace=root_namespaces[0] if root_namespaces else "",
                configuration_types=configuration_types,
                platform_toolsets=platform_toolsets,
                imports=_dedupe_text(imports),
                property_sheets=_dedupe_text(property_sheets),
                project_references=project_references,
                include_directories=include_directories,
                library_directories=library_directories,
                additional_dependencies=additional_dependencies,
                source_files=source_files,
                header_files=header_files,
                resource_files=resource_files,
                unresolved_macros=_macro_values(macro_source),
            )


        def analyze_workspace(path: str | Path) -> list[VcxProjectAnalysis]:
            target = Path(path).resolve()
            if target.suffix.lower() == ".vcxproj":
                return [analyze_vcxproj(target)]
            if target.suffix.lower() == ".sln":
                document = read_solution_document(target)
                analyses: list[VcxProjectAnalysis] = []
                for project in document.projects:
                    project_path = _project_file_path(document.path.parent, project)
                    if project_path.suffix.lower() == ".vcxproj" and project_path.exists():
                        analyses.append(analyze_vcxproj(project_path))
                return analyses
            return [analyze_vcxproj(item) for item in sorted(target.rglob("*.vcxproj"))]


        def build_solution_graph(path: str | Path) -> SolutionGraph:
            document = read_solution_document(path)
            by_path: dict[Path, SolutionProject] = {}
            for project in document.projects:
                absolute = _project_absolute_path(project)
                if absolute is not None:
                    by_path[absolute] = project

            edges: dict[str, list[str]] = {project.name: [] for project in document.projects}
            missing_references: list[str] = []
            for project in document.projects:
                project_file = _project_absolute_path(project)
                if project_file is None or project_file.suffix.lower() != ".vcxproj":
                    continue
                if not project_file.exists():
                    missing_references.append(f"{project.name}: missing project file {project_file}")
                    continue
                for reference in analyze_vcxproj(project_file).project_references:
                    referenced_file = _resolve_project_reference(project_file, reference)
                    referenced = by_path.get(referenced_file)
                    if referenced is None:
                        missing_references.append(f"{project.name}: missing reference {reference}")
                        continue
                    edges[project.name].append(referenced.name)

            edges = {name: _dedupe_text(references) for name, references in edges.items()}
            state: dict[str, str] = {}
            stack: list[str] = []
            cycles: list[list[str]] = []
            build_order: list[str] = []

            def visit(name: str) -> None:
                status = state.get(name)
                if status == "visiting":
                    if name in stack:
                        cycles.append(stack[stack.index(name):] + [name])
                    return
                if status == "visited":
                    return

                state[name] = "visiting"
                stack.append(name)
                for dependency in edges.get(name, []):
                    if dependency in edges:
                        visit(dependency)
                stack.pop()
                state[name] = "visited"
                if name not in build_order:
                    build_order.append(name)

            for project in document.projects:
                visit(project.name)

            return SolutionGraph(
                path=str(document.path),
                project_count=len(document.projects),
                edges=edges,
                build_order=build_order,
                cycles=cycles,
                missing_references=_dedupe_text(missing_references),
            )
        """
    )
    cli_py = _strip(
        r"""
        from __future__ import annotations

        import argparse

        from .sln import analyze_workspace, build_solution_graph, materialize_merge, materialize_split, read_solution


        def build_parser() -> argparse.ArgumentParser:
            parser = argparse.ArgumentParser(description="Inspect, merge, or split Visual Studio solution files.")
            sub = parser.add_subparsers(dest="command", required=True)

            inspect = sub.add_parser("inspect")
            inspect.add_argument("solution")

            analyze = sub.add_parser("analyze")
            analyze.add_argument("path")

            graph = sub.add_parser("graph")
            graph.add_argument("solution")

            build_order = sub.add_parser("build-order")
            build_order.add_argument("solution")

            merge = sub.add_parser("merge")
            merge.add_argument("solutions", nargs="+")
            merge.add_argument("--out", required=True)
            merge.add_argument("--copy-projects", action="store_true")
            merge.add_argument("--include-references", action="store_true")

            split = sub.add_parser("split")
            split.add_argument("solution")
            split.add_argument("--project", action="append", required=True)
            split.add_argument("--out", required=True)
            split.add_argument("--copy-projects", action="store_true")
            split.add_argument("--include-references", action="store_true")
            return parser


        def main(argv: list[str] | None = None) -> int:
            args = build_parser().parse_args(argv)
            if args.command == "inspect":
                projects = read_solution(args.solution)
                for project in projects:
                    print(f"{project.name}\\t{project.path}\\t{project.guid}")
                return 0
            if args.command == "analyze":
                for analysis in analyze_workspace(args.path):
                    print(analysis.to_json())
                return 0
            if args.command == "graph":
                print(build_solution_graph(args.solution).to_json())
                return 0
            if args.command == "build-order":
                graph = build_solution_graph(args.solution)
                for name in graph.build_order:
                    print(name)
                return 0
            if args.command == "merge":
                report = materialize_merge(
                    args.solutions,
                    args.out,
                    copy_projects=args.copy_projects,
                    include_references=args.include_references,
                )
                print(report.to_json())
                return 0
            if args.command == "split":
                report = materialize_split(
                    args.solution,
                    args.project,
                    args.out,
                    copy_projects=args.copy_projects,
                    include_references=args.include_references,
                )
                print(report.to_json())
                return 0
            return 2


        if __name__ == "__main__":
            raise SystemExit(main())
        """
    )
    test_py = _strip(
        r"""
        from pathlib import Path
        import tempfile
        import unittest

        from __PACKAGE__.sln import analyze_workspace, build_solution_graph, materialize_merge, materialize_split, merge_solutions, parse_projects, split_solution


        ROOT = Path(__file__).resolve().parents[1]


        class SolutionRefactorTests(unittest.TestCase):
            def test_parse_and_merge_solutions(self) -> None:
                one = ROOT / "samples" / "AppOne.sln"
                two = ROOT / "samples" / "AppTwo.sln"

                merged = merge_solutions([one, two])
                projects = parse_projects(merged)

                self.assertEqual([project.name for project in projects], ["AppOne", "Shared", "AppTwo"])
                self.assertIn("AppOne\\AppOne.vcxproj", merged)
                self.assertIn("Shared\\Shared.vcxproj", merged)
                self.assertIn("AppTwo\\AppTwo.vcxproj", merged)

            def test_split_solution_by_project_name(self) -> None:
                one = ROOT / "samples" / "AppOne.sln"

                with tempfile.TemporaryDirectory() as tempdir:
                    target = Path(tempdir) / "OnlyAppOne.sln"
                    target.write_text(split_solution(one, ["AppOne"]), encoding="utf-8")
                    text = target.read_text(encoding="utf-8")

                self.assertIn("AppOne", text)
                self.assertNotIn("MissingProject", text)

            def test_materialize_merge_and_split_copy_project_folders(self) -> None:
                one = ROOT / "samples" / "AppOne.sln"
                two = ROOT / "samples" / "AppTwo.sln"

                with tempfile.TemporaryDirectory() as tempdir:
                    merged = Path(tempdir) / "merged" / "Merged.sln"
                    split = Path(tempdir) / "split" / "OnlyAppTwo.sln"

                    merge_report = materialize_merge([one, two], merged, copy_projects=True, include_references=True)
                    split_report = materialize_split(merged, ["AppTwo"], split, copy_projects=True)

                    self.assertEqual(merge_report.project_count, 3)
                    self.assertEqual(merge_report.copied_projects, 3)
                    self.assertEqual(split_report.project_count, 1)
                    self.assertEqual(split_report.copied_projects, 1)
                    self.assertTrue((merged.parent / "AppOne" / "AppOne.vcxproj").exists())
                    self.assertTrue((merged.parent / "Shared" / "Shared.vcxproj").exists())
                    self.assertTrue((merged.parent / "AppTwo" / "AppTwo.vcxproj").exists())
                    self.assertTrue((split.parent / "AppTwo" / "AppTwo.vcxproj").exists())

            def test_split_can_include_referenced_projects(self) -> None:
                one = ROOT / "samples" / "AppOne.sln"

                with tempfile.TemporaryDirectory() as tempdir:
                    split = Path(tempdir) / "split" / "AppOneWithRefs.sln"

                    report = materialize_split(one, ["AppOne"], split, copy_projects=True, include_references=True)
                    text = split.read_text(encoding="utf-8")

                    self.assertEqual(report.project_count, 2)
                    self.assertEqual(report.included_references, 1)
                    self.assertEqual(report.copied_projects, 2)
                    self.assertIn("AppOne", text)
                    self.assertIn("Shared", text)
                    self.assertTrue((split.parent / "AppOne" / "AppOne.vcxproj").exists())
                    self.assertTrue((split.parent / "Shared" / "Shared.vcxproj").exists())

            def test_solution_graph_orders_project_references_first(self) -> None:
                one = ROOT / "samples" / "AppOne.sln"

                graph = build_solution_graph(one)

                self.assertEqual(graph.project_count, 2)
                self.assertEqual(graph.edges["AppOne"], ["Shared"])
                self.assertLess(graph.build_order.index("Shared"), graph.build_order.index("AppOne"))
                self.assertEqual(graph.cycles, [])
                self.assertEqual(graph.missing_references, [])

            def test_analyze_solution_native_project_metadata(self) -> None:
                one = ROOT / "samples" / "AppOne.sln"

                analyses = analyze_workspace(one)

                self.assertEqual(len(analyses), 2)
                analysis = next(item for item in analyses if item.name == "AppOne")
                self.assertEqual(analysis.root_namespace, "AppOne")
                self.assertIn("Application", analysis.configuration_types)
                self.assertIn("v143", analysis.platform_toolsets)
                self.assertIn("src\\main.cpp", analysis.source_files)
                self.assertIn("include\\app.h", analysis.header_files)
                self.assertIn("include", analysis.include_directories)
                self.assertIn("d3d11.lib", analysis.additional_dependencies)
                self.assertIn("..\\Shared\\Shared.vcxproj", analysis.project_references)
                self.assertIn("$(ProjectDir)", analysis.unresolved_macros)


        if __name__ == "__main__":
            unittest.main()
        """
    ).replace("__PACKAGE__", package_name)
    sample_one = _strip(
        """
        Microsoft Visual Studio Solution File, Format Version 12.00
        # Visual Studio Version 17
        Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "AppOne", "AppOne\\AppOne.vcxproj", "{11111111-1111-1111-1111-111111111111}"
        EndProject
        Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "Shared", "Shared\\Shared.vcxproj", "{33333333-3333-3333-3333-333333333333}"
        EndProject
        Global
        EndGlobal
        """
    )
    sample_two = _strip(
        """
        Microsoft Visual Studio Solution File, Format Version 12.00
        # Visual Studio Version 17
        Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "AppTwo", "AppTwo\\AppTwo.vcxproj", "{22222222-2222-2222-2222-222222222222}"
        EndProject
        Global
        EndGlobal
        """
    )
    sample_vcxproj = _strip(
        """
        <?xml version="1.0" encoding="utf-8"?>
        <Project DefaultTargets="Build" ToolsVersion="17.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
          <ItemGroup Label="ProjectConfigurations">
            <ProjectConfiguration Include="Debug|x64"><Configuration>Debug</Configuration><Platform>x64</Platform></ProjectConfiguration>
            <ProjectConfiguration Include="Release|x64"><Configuration>Release</Configuration><Platform>x64</Platform></ProjectConfiguration>
          </ItemGroup>
          <PropertyGroup Label="Globals">
            <ProjectGuid>{PROJECT_GUID}</ProjectGuid>
            <Keyword>Win32Proj</Keyword>
            <RootNamespace>SampleNativeProject</RootNamespace>
          </PropertyGroup>
          <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.Default.props" />
          <PropertyGroup Label="Configuration">
            <ConfigurationType>Application</ConfigurationType>
            <PlatformToolset>v143</PlatformToolset>
          </PropertyGroup>
          <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.props" />
          <ImportGroup Label="PropertySheets">
            <Import Project="$(UserRootDir)\\Microsoft.Cpp.$(Platform).user.props" />
            <Import Project="build\\shared.props" />
          </ImportGroup>
          <ItemDefinitionGroup>
            <ClCompile>
              <AdditionalIncludeDirectories>include;$(ProjectDir)generated;%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
            </ClCompile>
            <Link>
              <AdditionalLibraryDirectories>lib;$(OutDir);%(AdditionalLibraryDirectories)</AdditionalLibraryDirectories>
              <AdditionalDependencies>user32.lib;d3d11.lib;%(AdditionalDependencies)</AdditionalDependencies>
            </Link>
          </ItemDefinitionGroup>
          <ItemGroup>
            <ClCompile Include="src\\main.cpp" />
            <ClInclude Include="include\\app.h" />
            {PROJECT_REFERENCE}
          </ItemGroup>
          <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.targets" />
        </Project>
        """
    )
    sample_cpp = _strip(
        """
        #include <iostream>

        int main()
        {
            std::cout << "sample native project" << std::endl;
            return 0;
        }
        """
    )
    build_py = _strip(
        fr"""
        from __future__ import annotations

        import compileall
        import subprocess
        import sys
        from pathlib import Path


        ROOT = Path(__file__).resolve().parent


        def run(command: list[str]) -> int:
            print("Running:", " ".join(command))
            completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
            if completed.stdout:
                print(completed.stdout, end="")
            if completed.stderr:
                print(completed.stderr, end="", file=sys.stderr)
            return completed.returncode


        def main() -> int:
            if not compileall.compile_dir(str(ROOT / "{package_name}"), quiet=1):
                return 1
            code = run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
            if code != 0:
                return code
            merged = ROOT / "merged" / "merged.sln"
            split = ROOT / "split" / "split.sln"
            code = run([sys.executable, "-m", "{package_name}.cli", "merge", "samples/AppOne.sln", "samples/AppTwo.sln", "--out", str(merged), "--copy-projects"])
            if code != 0:
                return code
            with_refs = ROOT / "split" / "app_one_with_refs.sln"
            code = run([sys.executable, "-m", "{package_name}.cli", "split", "samples/AppOne.sln", "--project", "AppOne", "--out", str(with_refs), "--copy-projects", "--include-references"])
            if code != 0:
                return code
            code = run([sys.executable, "-m", "{package_name}.cli", "split", str(merged), "--project", "AppTwo", "--out", str(split), "--copy-projects"])
            if code != 0:
                return code
            code = run([sys.executable, "-m", "{package_name}.cli", "analyze", "samples/AppOne.sln"])
            if code != 0:
                return code
            code = run([sys.executable, "-m", "{package_name}.cli", "graph", "samples/AppOne.sln"])
            if code != 0:
                return code
            code = run([sys.executable, "-m", "{package_name}.cli", "build-order", "samples/AppOne.sln"])
            if code != 0:
                return code
            if "AppTwo" not in split.read_text(encoding="utf-8"):
                print("Expected split solution output was not generated.", file=sys.stderr)
                return 2
            if not (merged.parent / "AppOne" / "AppOne.vcxproj").exists():
                print("Merged workspace did not copy AppOne.vcxproj.", file=sys.stderr)
                return 3
            if not (merged.parent / "AppTwo" / "AppTwo.vcxproj").exists():
                print("Merged workspace did not copy AppTwo.vcxproj.", file=sys.stderr)
                return 4
            if not (split.parent / "AppTwo" / "AppTwo.vcxproj").exists():
                print("Split workspace did not copy AppTwo.vcxproj.", file=sys.stderr)
                return 5
            if not (with_refs.parent / "Shared" / "Shared.vcxproj").exists():
                print("Reference-aware split did not copy Shared.vcxproj.", file=sys.stderr)
                return 6
            if "d3d11.lib" not in (ROOT / "samples" / "AppOne" / "AppOne.vcxproj").read_text(encoding="utf-8"):
                print("Sample project dependency metadata was not generated.", file=sys.stderr)
                return 7
            print("Visual Studio solution refactor validation passed")
            return 0


        if __name__ == "__main__":
            raise SystemExit(main())
        """
    )
    return {
        f"{package_name}/__init__.py": "__all__ = [\"sln\"]\n",
        f"{package_name}/sln.py": sln_py,
        f"{package_name}/cli.py": cli_py,
        "tests/test_sln.py": test_py,
        "samples/AppOne.sln": sample_one,
        "samples/AppTwo.sln": sample_two,
        "samples/AppOne/AppOne.vcxproj": (
            sample_vcxproj
            .replace("SampleNativeProject", "AppOne")
            .replace("{PROJECT_GUID}", "{11111111-1111-1111-1111-111111111111}")
            .replace("{PROJECT_REFERENCE}", '<ProjectReference Include="..\\Shared\\Shared.vcxproj"><Project>{33333333-3333-3333-3333-333333333333}</Project></ProjectReference>')
        ),
        "samples/AppOne/src/main.cpp": sample_cpp.replace("sample native project", "AppOne"),
        "samples/AppOne/include/app.h": "#pragma once\nconst char* app_name();\n",
        "samples/AppTwo/AppTwo.vcxproj": (
            sample_vcxproj
            .replace("SampleNativeProject", "AppTwo")
            .replace("{PROJECT_GUID}", "{22222222-2222-2222-2222-222222222222}")
            .replace("{PROJECT_REFERENCE}", "")
        ),
        "samples/AppTwo/src/main.cpp": sample_cpp.replace("sample native project", "AppTwo"),
        "samples/AppTwo/include/app.h": "#pragma once\nconst char* app_name();\n",
        "samples/Shared/Shared.vcxproj": (
            sample_vcxproj
            .replace("SampleNativeProject", "Shared")
            .replace("{PROJECT_GUID}", "{33333333-3333-3333-3333-333333333333}")
            .replace("{PROJECT_REFERENCE}", "")
        ),
        "samples/Shared/src/main.cpp": sample_cpp.replace("sample native project", "Shared"),
        "samples/Shared/include/app.h": "#pragma once\nconst char* shared_name();\n",
        "build.py": build_py,
        ".gitignore": _strip(
            """
            __pycache__
            .pytest_cache
            merged
            split
            *.pyc
            """
        ),
        "README.md": _strip(
            f"""
            # {title}

            Dependency-free Visual Studio solution refactor tool for combining `.sln`
            files, splitting projects into standalone solutions, copying referenced `.vcxproj`
            folders into a new output workspace, and inspecting project paths.

            ## Validate

            ```powershell
            python build.py
            ```

            ## Examples

            ```powershell
            python -m {package_name}.cli inspect samples/AppOne.sln
            python -m {package_name}.cli analyze samples/AppOne.sln
            python -m {package_name}.cli graph samples/AppOne.sln
            python -m {package_name}.cli build-order samples/AppOne.sln
            python -m {package_name}.cli merge samples/AppOne.sln samples/AppTwo.sln --out merged/merged.sln --copy-projects --include-references
            python -m {package_name}.cli split merged/merged.sln --project AppTwo --out split/split.sln --copy-projects
            python -m {package_name}.cli split samples/AppOne.sln --project AppOne --out split/app_one_with_refs.sln --copy-projects --include-references
            ```
            """
        ),
    }


def _python_package_name(project_name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", project_name.replace("-", "_")).strip("_").lower()
    if not cleaned:
        return "aegis_app"
    if cleaned[0].isdigit():
        cleaned = f"app_{cleaned}"
    return cleaned


def _strip(value: str) -> str:
    return textwrap.dedent(value).strip() + "\n"


def _title_from_name(project_name: str) -> str:
    return scaffold_title_from_name(project_name)
