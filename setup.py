#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2020 LG Electronics

from codecs import open
from setuptools import setup, find_packages

with open('requirements.txt') as f:
    required = f.read()

if __name__ == "__main__":
    setup(
        name             = 'fosslight_dependency',
        version          = '3.0.0',
        packages         = find_packages(),
        description      = 'FOSSLight Dependency',
        long_description = 'It is a script file to scan dependencies through package manager file and generate a result report.',
        long_description_content_type = 'text/plain',
        license          = 'Apache-2.0',
        author           = 'LG Electronics',
        url              = 'https://github.com/LGE-OSS/fosslight_dependency',
        classifiers      = ['Programming Language :: Python :: 3.6',
                            'License :: OSI Approved :: Apache Software License'],
        install_requires = required,
        entry_points = {
            "console_scripts": [
                "fosslight_dependency=unified_script.dependency_unified:main"
                ]
            }
    )
