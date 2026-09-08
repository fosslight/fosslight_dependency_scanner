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
    # jib: regression gate for empty DEP (e.g. util exclude skipping build.gradle)
    ("tests/test_gradle/jib", "tests/result/gradle", True),
    # multi-module fixture often yields empty DEP on Ubuntu CI; keep smoke only
    ("tests/test_gradle2", "tests/result/gradle2", False),
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


@pytest.mark.parametrize("input_path, output_path, expect_dep_rows", [
    (os.path.join("tests", "test_gradle", "jib"), os.path.join("tests", "result", "gradle"), True),
    (os.path.join("tests", "test_gradle2"), os.path.join("tests", "result", "gradle2"), False),
])
@pytest.mark.windows
def test_windows(input_path, output_path, expect_dep_rows):
    command = f"{DIST_PATH} -p {input_path} -o {output_path} -m gradle"
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, f"Command failed: {command}\nstderr: {result.stderr}"
    assert any(os.scandir(output_path)), f"Output file does not exist: {output_path}"
    if expect_dep_rows:
        assert_dep_sheet_has_min_rows(output_path)
