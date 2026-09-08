#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0
import os
import pytest
import subprocess
from tests.pytest.assert_report import assert_dep_sheet_has_min_rows

DIST_PATH = os.path.join(os.environ.get("TOX_PATH", ""), "dist", "cli.exe")


@pytest.mark.parametrize("input_path, output_path, extra_args, expect_excel", [
    ("tests/test_pypi", "tests/result/pypi", "", True),
    ("tests/test_multi_pypi_npm", "tests/result/multi_pypi_npm", "", True),
    ("tests/test_multi_pypi_npm", "tests/result/multi_pypi_npm", "-f opossum", False),
])
@pytest.mark.ubuntu
def test_ubuntu(input_path, output_path, extra_args, expect_excel):
    command = f"fosslight_dependency -p {input_path} -o {output_path} {extra_args}"
    # Discard scanner stdout: under pytest/tox capture, a full pipe can interrupt
    # nested pip/venv setup and yield an empty DEP sheet while exit code stays 0.
    result = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert result.returncode == 0, f"Command failed: {command}\nstderr: {result.stderr}"
    assert any(os.scandir(output_path)), f"Output file does not exist: {output_path}"
    assert_dep_sheet_has_min_rows(output_path, expect_excel=expect_excel)


@pytest.mark.parametrize("input_path, output_path", [
    (os.path.join("tests", "test_pypi"), os.path.join("tests", "result", "pypi"))
])
@pytest.mark.windows
def test_windows(input_path, output_path):
    command = f"{DIST_PATH} -p {input_path} -o {output_path}"
    # Same as ubuntu: avoid capturing nested pip/venv stdout into a pipe that can fill.
    result = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert result.returncode == 0, f"Command failed: {command}\nstderr: {result.stderr}"
    assert any(os.scandir(output_path)), f"Output file does not exist: {output_path}"
    assert_dep_sheet_has_min_rows(output_path)
