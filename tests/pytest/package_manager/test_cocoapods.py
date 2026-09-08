#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0
import os
import pytest
import subprocess
from tests.pytest.assert_report import assert_dep_sheet_has_min_rows

COCOAPODS_PROJECT = "tests/test_cocoapods/cocoapods-tips/JWSCocoapodsTips"
COCOAPODS_OUTPUT = "tests/result/cocoapods"


@pytest.mark.parametrize("input_path, output_path, extra_args", [
    ("tests/test_cocoapods", "tests/result/cocoapods", "-m cocoapods")
])
@pytest.mark.ubuntu
def test_ubuntu(input_path, output_path, extra_args):
    # CocoaPods needs macOS (Xcode + `pod install`). Ubuntu is smoke-only.
    command = f"fosslight_dependency -p {input_path} -o {output_path} {extra_args}"
    result = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert result.returncode == 0, f"Command failed: {command}\nstderr: {result.stderr}"
    assert any(os.scandir(output_path)), f"Output file does not exist: {output_path}"


@pytest.mark.macos
def test_macos_cocoapods():
    """Requires CI to run `pod install` in COCOAPODS_PROJECT first."""
    assert os.path.isdir(os.path.join(COCOAPODS_PROJECT, "Pods")), (
        f"Pods/ missing under {COCOAPODS_PROJECT}; run pod install before this test"
    )
    command = f"fosslight_dependency -p {COCOAPODS_PROJECT} -o {COCOAPODS_OUTPUT} -m cocoapods"
    result = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert result.returncode == 0, f"Command failed: {command}\nstderr: {result.stderr}"
    assert any(os.scandir(COCOAPODS_OUTPUT)), f"Output file does not exist: {COCOAPODS_OUTPUT}"
    assert_dep_sheet_has_min_rows(COCOAPODS_OUTPUT)
