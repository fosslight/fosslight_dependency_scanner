#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2024 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0
import os
import pytest
import subprocess

DIST_PATH = os.path.join(os.environ.get("TOX_PATH", ""), "dist", "cli.exe")


@pytest.mark.parametrize("input_path, output_path", [
    ("tests/test_cargo", "tests/result/cargo")
])
@pytest.mark.ubuntu
def test_ubuntu(input_path, output_path):
    command = f"fosslight_dependency -p {input_path} -o {output_path}"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    assert result.returncode == 0, f"Command failed: {command}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    assert any(os.scandir(output_path)), f"Output file does not exist: {output_path}"


@pytest.mark.parametrize("input_path, output_path", [
    (os.path.join("tests", "test_cargo"), os.path.join("tests", "result", "cargo"))
])
@pytest.mark.windows
def test_windows(input_path, output_path):
    command = f"{DIST_PATH} -p {input_path} -o {output_path}"
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, f"Command failed: {command}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    assert any(os.scandir(output_path)), f"Output file does not exist: {output_path}"
