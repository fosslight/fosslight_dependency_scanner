#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0
import os
import pytest
import subprocess


@pytest.mark.parametrize("input_path, output_path, extra_args", [
    ("tests/test_npm1", "tests/result/npm1", ""),
    ("tests/test_npm2", "tests/result/npm2", "-m npm")
])
@pytest.mark.ubuntu
def test_ubuntu(input_path, output_path, extra_args):
    command = f"fosslight_dependency -p {input_path} -o {output_path} {extra_args}"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    assert result.returncode == 0, f"Command failed: {command}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    assert any(os.scandir(output_path)), f"Output file does not exist: {output_path}"
