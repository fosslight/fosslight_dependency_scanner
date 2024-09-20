#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

GRADLE_COMMANDS = [
    "fosslight_dependency -p tests/test_npm1 -o tests/result/npm1",
    "fosslight_dependency -p tests/test_npm2 -o tests/result/npm2 -m npm"
]


def test_npm_get_dependency(run_command):
    for command in GRADLE_COMMANDS:
        return_code, stdout, stderr = run_command(command)
        assert return_code == 0, f"Command failed: {command}\nstdout: {stdout}\nstderr: {stderr}"
