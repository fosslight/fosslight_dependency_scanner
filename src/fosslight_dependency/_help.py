#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0
from fosslight_util.help import PrintHelpMsg

_HELP_MESSAGE_DEPENDENCY = """
    Usage: fosslight_dependency [option1] <arg1> [option2] <arg2>...

    FOSSLight Dependency utilizes the open source software for analyzing each package manager dependencies.
    We choose the open source software for each package manager that shows not only the direct dependencies
    but also the transitive dependencies including the information of dependencies such as oss name, oss version and license name.

    Each package manager uses the results of the following software:
        NPM : NPM License Checker
        Pypi : Pip-licenses
        Gradle : License Gradle Plugin
        Maven : License-maven-plugin
        Pub : Flutter_oss_licenses

    Options:
        Optional
            -h\t\t\t\t    Print help message.
            -v\t\t\t\t    Print the version of the script.
            -m <package_manager>\t    Enther the package manager(npm, maven, gradle, pip, pub, cocoapods, android).
            -p <input_path>\t\t    Enter the path where the script will be run.
            -o <output_path>\t\t    Enter the path where the result file will be generated.

        Required only for pypi
            -a <activate_cmd>\t\t    Virtual environment activate command(ex, 'conda activate (venv name)')
            -d <deactivate_cmd>\t\t    Virtual environment deactivate command(ex, 'conda deactivate')

        Optional only for gradle, maven
            -c <dir_name>\t\t    Enter the customized build output directory name(default: target)
        
        Optional only for android
            -n <app_name>\t\t   Enter the application directory name where the plugin output file is located(default: app)
        """


def print_help_msg():
    helpMsg = PrintHelpMsg(_HELP_MESSAGE_DEPENDENCY)
    helpMsg.print_help_msg(True)
