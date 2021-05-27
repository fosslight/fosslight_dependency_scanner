#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2020 LG Electronics

from codecs import open
from setuptools import setup, find_packages

with open('README.md', 'r', 'utf-8') as f:
    reamdme = f.read()

with open('requirements.txt', 'r', 'utf-8') as f:
    required = f.read().splitlines()

exec(open("src/fosslight_dependency/_version.py").read())

if __name__ == "__main__":
    setup(
        name='fosslight_dependency',
        version=__version__,
        package_dir={"": "src"},
        packages=find_packages(where='src'),
        description='FOSSLight Dependency',
        long_description=reamdme,
        long_description_content_type='text/markdown',
        license='Apache-2.0',
        author='LG Electronics',
        url='https://github.com/fosslight/fosslight_dependency',
        download_url='https://github.com/fosslight/fosslight_dependency',
        classifiers=['Programming Language :: Python :: 3.6',
                     'License :: OSI Approved :: Apache Software License'],
        install_requires=required,
        package_data={'fosslight_dependency': ['third_party/nomos/nomossa',
                                               'third_party/askalono/askalono.exe',
                                               'third_party/askalono/askalono_macos']},
        include_package_data=True,
        entry_points={
            "console_scripts": [
                "fosslight_dependency = fosslight_dependency.analyze_dependency:main"
            ]
        }
    )
