#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0
import os
import pytest
import subprocess
from tests.pytest.assert_report import assert_dep_sheet_has_min_rows
from fosslight_dependency.package_manager.Nuget import Nuget

UBUNTU_COMMANDS = [
    "fosslight_dependency -p tests/test_nuget -o tests/result/nuget1",
    "fosslight_dependency -p tests/test_nuget2 -o tests/result/nuget2"
]

DIST_PATH = os.path.join(os.environ.get("TOX_PATH", ""), "dist", "cli.exe")


@pytest.mark.parametrize("input_path, output_path", [
    ("tests/test_nuget", "tests/result/nuget1"),
    ("tests/test_nuget2", "tests/result/nuget2")
])
@pytest.mark.ubuntu
def test_ubuntu(input_path, output_path):
    command = f"fosslight_dependency -p {input_path} -o {output_path}"
    result = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert result.returncode == 0, f"Command failed: {command}\nstderr: {result.stderr}"
    assert any(os.scandir(output_path)), f"Output file does not exist: {output_path}"
    assert_dep_sheet_has_min_rows(output_path)


@pytest.mark.parametrize("input_path, output_path", [
    (os.path.join("tests", "test_nuget"), os.path.join("tests", "result", "nuget1")),
    (os.path.join("tests", "test_nuget2"), os.path.join("tests", "result", "nuget2"))
])
@pytest.mark.windows
def test_windows(input_path, output_path):
    command = f"{DIST_PATH} -p {input_path} -o {output_path}"
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, f"Command failed: {command}\nstderr: {result.stderr}"
    assert any(os.scandir(output_path)), f"Output file does not exist: {output_path}"
    assert_dep_sheet_has_min_rows(output_path)


@pytest.mark.ubuntu
@pytest.mark.windows
def test_parse_skips_directory_packages_props_with_absolute_path(tmp_path, monkeypatch):
    # In the central package management flow, Directory.Packages.props is one of the input
    # files but is not parsed itself. With an absolute path it used to reach the
    # project.assets.json parser and raise JSONDecodeError, aborting the whole scan.
    props = tmp_path / "Directory.Packages.props"
    props.write_text(
        '<Project><ItemGroup><PackageVersion Include="Newtonsoft.Json" Version="13.0.1" />'
        '</ItemGroup></Project>', encoding="utf8")
    monkeypatch.chdir(tmp_path)

    nuget = Nuget(str(tmp_path), str(tmp_path))
    nuget.parse_oss_information(str(props))

    assert nuget.dep_items == []
