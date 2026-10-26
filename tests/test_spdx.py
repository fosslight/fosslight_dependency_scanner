# Copyright (c) 2026 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import json
import shutil
import subprocess
from copy import deepcopy

import pytest
from spdx_tools.spdx.model import RelationshipType
from spdx_tools.spdx.parser.parse_anything import parse_file
from spdx_tools.spdx.validation.document_validator import validate_full_spdx_document

from fosslight_dependency._package_manager import deduplicate_dep_items
from fosslight_dependency.dependency_item import DependencyItem
from fosslight_dependency.package_manager.Npm import Npm
from fosslight_dependency.run_dependency_scanner import run_dependency_scanner
from fosslight_util.constant import FOSSLIGHT_DEPENDENCY
from fosslight_util.oss_item import OssItem


@pytest.fixture
def npm_reports(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    output = tmp_path / "reports"
    manifest = {"name": "project", "version": "1.0.0", "dependencies": {"parent": "1.0.0"}}
    (project / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
    reports = []
    for license_value in ("MIT", "Apache-2.0"):
        report = {}
        for name, license_name in (("project", "MIT"), ("parent", license_value), ("child", "ISC")):
            report[f"{name}@1.0.0"] = {
                "name": name, "version": "1.0.0", "licenses": license_name,
                "path": str(project / "node_modules" / name), "repository": f"https://example.com/{name}",
            }
        reports.append(report)

    def run_plugin(manager):
        manager.manifest_file_name = ["package.json"]
        for index, report in enumerate(reports):
            report_file = project / f"license-report-{index}.json"
            report_file.write_text(json.dumps(report), encoding="utf-8")
            manager.input_package_list_file.append(str(report_file))
        return True

    original_run = subprocess.run

    def command_output(command, *args, **kwargs):
        if command == "npm ls -a --omit=dev --json -s":
            tree = {
                "name": "project", "version": "1.0.0", "dependencies": {
                    "parent": {"version": "1.0.0", "dependencies": {"child": {"version": "1.0.0"}}},
                },
            }
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(tree), stderr="")
        return original_run(command, *args, **kwargs)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Npm, "_check_network_available", lambda self: False)
    monkeypatch.setattr(Npm, "_network_available", False)
    monkeypatch.setattr(Npm, "run_plugin", run_plugin)
    monkeypatch.setattr(subprocess, "run", command_output)
    return project, output, reports


@pytest.mark.parametrize("format_name, extension", [
    ("spdx-json", ".json"), ("spdx-yaml", ".yaml"), ("spdx-xml", ".xml"), ("spdx-tag", ".tag"),
])
@pytest.mark.parametrize("custom_name", [False, True])
def test_spdx_preserves_real_parser_metadata_and_dependencies(npm_reports, format_name, extension, custom_name):
    project, output, _reports = npm_reports
    target = output / f"custom{extension}" if custom_name else output

    success, scan_item = run_dependency_scanner(
        package_manager="npm", input_dir=str(project), output_dir_file=str(target), formats=[format_name],
    )

    assert success
    assert len(scan_item.file_items[FOSSLIGHT_DEPENDENCY]) == 4
    filenames = list(output.glob(f"*{extension}"))
    assert len(filenames) == 1
    if custom_name:
        assert filenames[0].name == f"custom{extension}"
    else:
        assert filenames[0].name.startswith("fosslight_spdx_dep_")
    document = parse_file(str(filenames[0]))
    assert validate_full_spdx_document(document) == []
    assert document.creation_info.name == "project"
    assert len(document.packages) == 4
    assert not document.files
    assert any(creator.name.startswith("FOSSLIGHT_Dependency - ") for creator in document.creation_info.creators)
    root = next(package for package in document.packages if package.spdx_id == "SPDXRef-ROOT-PACKAGE")
    parents = [package for package in document.packages if package.name == "npm:parent"]
    child = next(package for package in document.packages if package.name == "npm:child")
    assert root.name == "project"
    assert len(parents) == 2
    assert {str(package.license_declared) for package in parents} == {"MIT", "Apache-2.0"}
    for package in document.packages:
        assert package.files_analyzed is False
    for package in parents:
        assert [reference.locator for reference in package.external_references] == ["pkg:npm/parent@1.0.0"]
    assert {
        (relationship.spdx_element_id, relationship.related_spdx_element_id)
        for relationship in document.relationships if relationship.relationship_type == RelationshipType.DEPENDS_ON
    } == {
        *((root.spdx_id, package.spdx_id) for package in parents),
        *((package.spdx_id, child.spdx_id) for package in parents),
    }


@pytest.mark.parametrize("format_name, extension", [
    ("spdx-json", ".json"), ("spdx-yaml", ".yaml"), ("spdx-xml", ".xml"), ("spdx-tag", ".tag"),
])
def test_empty_dependency_results_keep_root_and_creator(npm_reports, format_name, extension):
    project, output, reports = npm_reports
    reports.clear()

    success, scan_item = run_dependency_scanner(
        package_manager="npm", input_dir=str(project), output_dir_file=str(output), formats=[format_name],
    )

    assert success
    assert not scan_item.file_items[FOSSLIGHT_DEPENDENCY]
    filename, = output.glob(f"*{extension}")
    document = parse_file(str(filename))
    assert validate_full_spdx_document(document) == []
    assert [package.spdx_id for package in document.packages] == ["SPDXRef-ROOT-PACKAGE"]
    assert any(creator.name.startswith("FOSSLIGHT_Dependency - ") for creator in document.creation_info.creators)


@pytest.mark.skipif(
    not all(shutil.which(command) for command in ("node", "npm", "license-checker")),
    reason="Node.js, npm and license-checker are required for the external command check",
)
def test_real_npm_commands_write_all_spdx_formats_without_install(tmp_path, monkeypatch):
    project = tmp_path / "offline-project"
    package_dir = project / "node_modules" / "fixture-package"
    package_dir.mkdir(parents=True)
    package = {"name": "fixture-package", "version": "1.0.0", "license": "MIT"}
    (package_dir / "package.json").write_text(json.dumps(package), encoding="utf-8")
    manifest = {
        "name": "offline-project", "version": "1.0.0", "license": "MIT",
        "dependencies": {"fixture-package": "1.0.0"},
    }
    (project / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
    output = tmp_path / "reports"
    monkeypatch.chdir(project)
    monkeypatch.setattr(Npm, "_check_network_available", lambda self: False)
    monkeypatch.setattr(Npm, "_network_available", False)

    success, scan_item = run_dependency_scanner(
        package_manager="npm", input_dir=str(project), output_dir_file=str(output),
        formats=["spdx-json", "spdx-yaml", "spdx-xml", "spdx-tag"],
    )

    assert success
    assert len(scan_item.file_items[FOSSLIGHT_DEPENDENCY]) == 2
    for extension in (".json", ".yaml", ".xml", ".tag"):
        filename, = output.glob(f"*{extension}")
        document = parse_file(str(filename))
        assert validate_full_spdx_document(document) == []
        assert document.creation_info.name == "offline-project"
        assert len(document.packages) == 2
        package = next(package for package in document.packages if package.name == "npm:fixture-package")
        assert package.files_analyzed is False
        assert str(package.license_declared) == "MIT"
        assert [reference.locator for reference in package.external_references] == ["pkg:npm/fixture-package@1.0.0"]
        assert any(
            relationship.spdx_element_id == "SPDXRef-ROOT-PACKAGE"
            and relationship.relationship_type == RelationshipType.DEPENDS_ON
            and relationship.related_spdx_element_id == package.spdx_id
            for relationship in document.relationships
        )


@pytest.mark.parametrize("difference", [
    "source_name_or_path", "file_exclude", "oss_exclude", "download_location", "copyright", "license_texts", "additional_oss",
])
def test_deduplication_preserves_distinct_output_rows(difference):
    original = DependencyItem()
    original.purl = "pkg:npm/example@1.0.0"
    original.depends_on = ["pkg:npm/child@1.0.0"]
    original.oss_items.append(OssItem("example", "1.0.0", "Custom License"))
    variant = deepcopy(original)
    if difference == "source_name_or_path":
        variant.source_name_or_path = "other/package.json"
    elif difference == "file_exclude":
        variant.exclude = True
    elif difference == "oss_exclude":
        variant.oss_items[0].exclude = True
    elif difference == "additional_oss":
        variant.oss_items.append(OssItem("second", "2.0.0", "MIT"))
    elif difference == "license_texts":
        variant.oss_items[0].license_texts["Custom License"] = "Different detected license text."
    else:
        value = "https://example.com/archive" if difference == "download_location" else "Copyright"
        setattr(variant.oss_items[0], difference, value)

    assert deduplicate_dep_items([original, variant, deepcopy(original)]) == [original, variant]


@pytest.mark.parametrize("items", [None, []])
def test_deduplication_preserves_empty_input(items):
    assert deduplicate_dep_items(items) is items
