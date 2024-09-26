#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

UBUNTU_COMMANDS = [
    "fosslight_dependency -p tests/test_gradle/jib -o tests/result/gradle",
    "fosslight_dependency -p tests/test_gradle2 -o tests/result/gradle2"
]


def test_ubuntu(run_command):
    for command in UBUNTU_COMMANDS:
        return_code, stdout, stderr = run_command(command)
        assert return_code == 0, f"Command failed: {command}\nstdout: {stdout}\nstderr: {stderr}"
