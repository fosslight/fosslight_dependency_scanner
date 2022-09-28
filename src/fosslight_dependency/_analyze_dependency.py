#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import fosslight_dependency.constant as const
from fosslight_dependency.package_manager.Pypi import Pypi
from fosslight_dependency.package_manager.Npm import Npm
from fosslight_dependency.package_manager.Maven import Maven
from fosslight_dependency.package_manager.Gradle import Gradle
from fosslight_dependency.package_manager.Pub import Pub
from fosslight_dependency.package_manager.Cocoapods import Cocoapods
from fosslight_dependency.package_manager.Android import Android
from fosslight_dependency.package_manager.Swift import Swift
from fosslight_dependency.package_manager.Carthage import Carthage
from fosslight_dependency.package_manager.Go import Go
from fosslight_dependency.package_manager.Nuget import Nuget
import fosslight_util.constant as constant

logger = logging.getLogger(constant.LOGGER_NAME)


def analyze_dependency(package_manager_name, input_dir, output_dir, pip_activate_cmd='', pip_deactivate_cmd='',
                       output_custom_dir='', app_name=const.default_app_name, github_token='', manifest_file_name=[],
                       direct=True):
    ret = True
    package_sheet_list = []

    if package_manager_name == const.PYPI:
        package_manager = Pypi(input_dir, output_dir, pip_activate_cmd, pip_deactivate_cmd)
    elif package_manager_name == const.NPM:
        package_manager = Npm(input_dir, output_dir)
    elif package_manager_name == const.MAVEN:
        package_manager = Maven(input_dir, output_dir, output_custom_dir)
    elif package_manager_name == const.GRADLE:
        package_manager = Gradle(input_dir, output_dir, output_custom_dir)
    elif package_manager_name == const.PUB:
        package_manager = Pub(input_dir, output_dir)
    elif package_manager_name == const.COCOAPODS:
        package_manager = Cocoapods(input_dir, output_dir)
    elif package_manager_name == const.ANDROID:
        package_manager = Android(input_dir, output_dir, app_name)
    elif package_manager_name == const.SWIFT:
        package_manager = Swift(input_dir, output_dir, github_token)
    elif package_manager_name == const.CARTHAGE:
        package_manager = Carthage(input_dir, output_dir, github_token)
    elif package_manager_name == const.GO:
        package_manager = Go(input_dir, output_dir)
    elif package_manager_name == const.NUGET:
        package_manager = Nuget(input_dir, output_dir)
    else:
        logger.error(f"Not supported package manager name: {package_manager_name}")
        ret = False
        return ret, package_sheet_list

    if manifest_file_name:
        package_manager.set_manifest_file(manifest_file_name)

    if direct:
        package_manager.set_direct_dependencies(direct)
    ret = package_manager.run_plugin()
    if ret:
        if direct:
            package_manager.parse_direct_dependencies()

        for f_name in package_manager.input_package_list_file:
            logger.info(f"Parse oss information with file: {f_name}")

            if os.path.isfile(f_name):
                package_sheet_list.extend(package_manager.parse_oss_information(f_name))
            else:
                logger.error(f"Failed to open input file: {f_name}")
                ret = False

    if ret:
        logger.warning(f"### Complete to analyze: {package_manager_name}")
    else:
        logger.error(f"### Fail to analyze: {package_manager_name}")

    del package_manager

    return ret, package_sheet_list
