#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0
from fosslight_util.help import PrintHelpMsg

_HELP_MESSAGE_DEPENDENCY = """
    Usage: fosslight_dependency [option1] <arg1> [option2] <arg2>...

    FOSSLight Dependency Scanner is the tool that supports the analysis of dependencies for multiple package managers.
    It detects the manifest file of package managers automatically and analyzes the dependencies with using open source tools.
    Then, it generates the report file that contains OSS information of dependencies.

    Currently, it supports the following package managers:
        Gradle (Java)
        Maven (Java)
        NPM (Node.js)
        PIP (Python)
        Pub (Dart with flutter)
        Cocoapods (Swift/Obj-C)
        Swift (Swift)
        Carthage (Swift/Obj-C)
        Go (Go)
        Nuget (.NET)

    Options:
        Optional
            -h\t\t\t\t    Print help message.
            -v\t\t\t\t    Print the version of the script.
            -m <package_manager>\t    Enter the package manager.
                                        \t(npm, maven, gradle, pip, pub, cocoapods, android, swift, carthage, go, nuget)
            -p <input_path>\t\t    Enter the path where the script will be run.
            -o <output_path>\t\t    Output path
            \t\t\t\t\t(If you want to generate the specific file name, add the output path with file name.)
            -f <format>\t\t\t    Output file format (excel, csv, opossum, yaml)
            --direct\t\t\t    Print the direct/transitive dependency type in comment.
                                \t\tChoice 'True' or 'False'. (default:True)
            --notice\t\t\t    Print the open source license notice text.

        Required only for swift, carthage
            -t <token>\t\t\t    Enter the github personal access token.

        Optional only for pypi
            -a <activate_cmd>\t\t    Virtual environment activate command(ex, 'conda activate (venv name)')
            -d <deactivate_cmd>\t\t    Virtual environment deactivate command(ex, 'conda deactivate')

        Optional only for gradle, maven
            -c <dir_name>\t\t    Enter the customized build output directory name
                                    \t\t-Default name : 'build' for gradle, 'target' for maven

        Optional only for android
            -n <app_name>\t\t    Enter the application directory name where the plugin output file is located(default: app)
        """


def print_help_msg():
    helpMsg = PrintHelpMsg(_HELP_MESSAGE_DEPENDENCY)
    helpMsg.print_help_msg(True)
