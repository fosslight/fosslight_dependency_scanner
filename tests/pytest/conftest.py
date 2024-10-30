#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0
import os
import shutil
import pytest

set_up_directories = [
    "tests/result/android",
    "tests/result/cocoapods",
    "tests/result/exclude",
    "tests/result/gradle",
    "tests/result/gradle2",
    "tests/result/helm",
    "tests/result/maven1",
    "tests/result/maven2",
    "tests/result/multi_pypi_npm",
    "tests/result/npm1",
    "tests/result/npm2",
    "tests/result/nuget1",
    "tests/result/nuget2",
    "tests/result/pub",
    "tests/result/pypi",
    "tests/result/cargo"
]

remove_directories = set_up_directories


@pytest.fixture(scope="session", autouse=True)
def setup_test_result_dir_and_teardown():
    print("==============setup==============")
    for directory in set_up_directories:
        os.makedirs(directory, exist_ok=True)

    yield

    print("==============tearDown==============")
    for directory in remove_directories:
        shutil.rmtree(directory)
