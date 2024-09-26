#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0
import os
import pytest

UBUNTU_COMMANDS = [
    "fosslight_dependency -p tests/test_pypi -o tests/result/pypi",
    "fosslight_dependency -p tests/test_multi_pypi_npm -o tests/result/multi_pypi_npm",
    "fosslight_dependency -p tests/test_multi_pypi_npm -o tests/result/multi_pypi_npm -f opossum"
]

DIST_PATH = os.path.join(os.environ.get("TOX_PATH"), "dist", "cli.exe")
INPUT_PATH = os.path.join("tests", "test_pypi")
OUTPUT_PATH = os.path.join("tests", "result", "pypi")

WINDOW_COMMANDS = [f"{DIST_PATH} -p {INPUT_PATH} -o {OUTPUT_PATH}"]


@pytest.mark.ubuntu
def test_ubuntu(run_command):
    for command in UBUNTU_COMMANDS:
        return_code, stdout, stderr = run_command(command)
        assert return_code == 0, f"Command failed: {command}\nstdout: {stdout}\nstderr: {stderr}"


@pytest.mark.windows
def test_windows(run_command):
    for command in WINDOW_COMMANDS:
        return_code, stdout, stderr = run_command(command)
        assert return_code == 0, f"Command failed: {command}\nstdout: {stdout}\nstderr: {stderr}"
