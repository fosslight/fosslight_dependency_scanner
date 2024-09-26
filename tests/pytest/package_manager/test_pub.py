#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0
import os.path

UBUNTU_COMMANDS = [
    "fosslight_dependency -p tests/test_pub -o tests/result/pub",
    "fosslight_dependency -p tests/test_exclude -e requirements.txt -o tests/result/exclude"
]

DIST_PATH = os.path.join(os.path.abspath(os.sep), "dist", "cli.exe")
INPUT_PATH = os.path.join("tests", "test_pub")
OUTPUT_PATH = os.path.join("tests", "result", "pub")
INPUT_PATH2 = os.path.join("tests", "test_exclude")
OUTPUT_PATH2 = os.path.join("tests", "result", "exclude")

WINDOW_COMMANDS = [
    f"{DIST_PATH} -p {INPUT_PATH} -o {OUTPUT_PATH}",
    f"{DIST_PATH} -p {INPUT_PATH} -o {OUTPUT_PATH} -f opossum",
    f"{DIST_PATH} -p {INPUT_PATH} -e requirements.txt -o {OUTPUT_PATH}"
]


def test_ubuntu(run_command):
    for command in UBUNTU_COMMANDS:
        return_code, stdout, stderr = run_command(command)
        assert return_code == 0, f"Command failed: {command}\nstdout: {stdout}\nstderr: {stderr}"


def test_windows(run_command):
    for command in WINDOW_COMMANDS:
        return_code, stdout, stderr = run_command(command)
        assert return_code == 0, f"Command failed: {command}\nstdout: {stdout}\nstderr: {stderr}"
