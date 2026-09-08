#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0
import os
import pytest
import subprocess
from tests.pytest.assert_report import assert_dep_sheet_has_min_rows

DIST_PATH = os.path.join(os.environ.get("TOX_PATH", ""), "dist", "cli.exe")


@pytest.mark.parametrize("input_path, output_path, expect_dep_rows", [
    # CI installs Flutter SDK and runs `flutter pub get` before tox.
    ("tests/test_pub", "tests/result/pub", True),
    ("tests/test_exclude -e requirements.txt", "tests/result/exclude", True),
])
@pytest.mark.ubuntu
def test_ubuntu(input_path, output_path, expect_dep_rows):
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
    if expect_dep_rows:
        assert_dep_sheet_has_min_rows(output_path)


@pytest.mark.parametrize(
    "input_path, output_path, extra_args, expect_dep_rows, expect_excel",
    [
        (os.path.join("tests", "test_pub"), os.path.join("tests", "result", "pub"),
         "", True, True),
        (os.path.join("tests", "test_pub"), os.path.join("tests", "result", "pub"),
         "-f opossum", False, False),
        (os.path.join("tests", "test_exclude") + " -e requirements.txt",
         os.path.join("tests", "result", "exclude"), "", True, True),
    ],
)
@pytest.mark.windows
def test_windows(input_path, output_path, extra_args, expect_dep_rows, expect_excel):
    command = f"{DIST_PATH} -p {input_path} -o {output_path} {extra_args}"
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, f"Command failed: {command}\nstderr: {result.stderr}"
    assert any(os.scandir(output_path)), f"Output file does not exist: {output_path}"
    if expect_dep_rows:
        assert_dep_sheet_has_min_rows(output_path, expect_excel=expect_excel)
    elif not expect_excel:
        assert_dep_sheet_has_min_rows(output_path, expect_excel=False)


@pytest.mark.macos
def test_macos_pub():
    """Requires Flutter SDK and `flutter pub get` in tests/test_pub."""
    input_path = "tests/test_pub"
    output_path = "tests/result/pub"
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
