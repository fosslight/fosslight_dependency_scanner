#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2020 LG Electronics

from codecs import open
import os
import shutil
from setuptools import setup, find_packages

with open('README.md', 'r', 'utf-8') as f:
    reamdme = f.read()

with open('requirements.txt', 'r', 'utf-8') as f:
    required = f.read().splitlines()

_PACKAEG_NAME = 'fosslight_dependency'
_LICENSE_FILE = 'LICENSE'
_LICENSE_DIR = 'LICENSES'

if __name__ == "__main__":
    dest_path = os.path.join('src', _PACKAEG_NAME, _LICENSE_DIR)
    if not os.path.exists(dest_path):
        os.mkdir(dest_path)
    if os.path.isfile(_LICENSE_FILE):
        shutil.copy(_LICENSE_FILE, dest_path)
    if os.path.isdir(_LICENSE_DIR):
        license_f = [f_name for f_name in os.listdir(_LICENSE_DIR) if f_name.upper().startswith(_LICENSE_FILE)]
        for lic_f in license_f:
            shutil.copy(os.path.join(_LICENSE_DIR, lic_f), dest_path)

    setup(
        name=_PACKAEG_NAME,
        version='3.11.7',
        package_dir={"": "src"},
        packages=find_packages(where='src'),
        description='FOSSLight Dependency Scanner',
        long_description=reamdme,
        long_description_content_type='text/markdown',
        license='Apache-2.0',
        author='LG Electronics',
        url='https://github.com/fosslight/fosslight_dependency_scanner',
        download_url='https://github.com/fosslight/fosslight_dependency_scanner',
        classifiers=['Programming Language :: Python :: 3.6',
                     'License :: OSI Approved :: Apache Software License'],
        install_requires=required,
        package_data={_PACKAEG_NAME: [os.path.join('third_party', 'nomos', 'nomossa'),
                                      os.path.join('third_party', 'askalono', 'askalono.exe'),
                                      os.path.join('third_party', 'askalono', 'askalono_macos'),
                                      os.path.join(_LICENSE_DIR, '*')]},
        include_package_data=True,
        entry_points={
            "console_scripts": [
                "fosslight_dependency = fosslight_dependency.run_dependency_scanner:main"
            ]
        }
    )
    shutil.rmtree(dest_path, ignore_errors=True)
