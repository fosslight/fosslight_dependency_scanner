#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0
import os.path

UBUNTU_COMMANDS = [
    "fosslight_dependency -p tests/test_android -o tests/result/android -m android"
]

DIST_PATH = os.path.join(os.environ.get("TOX_PATH"), "dist", "cli.exe")
INPUT_PATH = os.path.join("tests", "test_android", "sunflower")
OUTPUT_PATH = os.path.join("tests", "result", "android")

WINDOW_COMMANDS = [f"{DIST_PATH} -p {INPUT_PATH} -o {OUTPUT_PATH}"]


def test_ubuntu(run_command):
    for command in UBUNTU_COMMANDS:
        return_code, stdout, stderr = run_command(command)
        assert return_code == 0, f"Command failed: {command}\nstdout: {stdout}\nstderr: {stderr}"


def test_windows(run_command):
    for command in WINDOW_COMMANDS:
        return_code, stdout, stderr = run_command(command)
        assert return_code == 0, f"Command failed: {command}\nstdout: {stdout}\nstderr: {stderr}"
