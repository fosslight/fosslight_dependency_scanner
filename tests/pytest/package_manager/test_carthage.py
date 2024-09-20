#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

COMMANDS = [
    "fosslight_dependency -p tests/test_carthage -o tests/result/carthage -m carthage"
]


def test_carthage_get_dependency(run_command):
    for command in COMMANDS:
        return_code, stdout, stderr = run_command(command)
        assert return_code == 0, f"Command failed: {command}\nstdout: {stdout}\nstderr: {stderr}"
