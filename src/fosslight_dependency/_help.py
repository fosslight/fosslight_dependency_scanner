#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0
from fosslight_util.help import PrintHelpMsg, print_package_version
from fosslight_util.output_format import SUPPORT_FORMAT

_HELP_MESSAGE_DEPENDENCY = f"""
    📖 Usage
    ────────────────────────────────────────────────────────────────────
    fosslight_dependency [options] <arguments>

    📝 Description
    ────────────────────────────────────────────────────────────────────
    FOSSLight Dependency Scanner analyzes dependencies for multiple package
    managers. It detects manifest files automatically and generates reports
    containing OSS information of dependencies.

    📚 Guide: https://fosslight.org/fosslight-guide/scanner/3_dependency.html

    📦 Supported Package Managers
    ────────────────────────────────────────────────────────────────────
    Gradle, Maven (Java)          │ NPM, PNPM, Yarn (Node.js)
    PIP (Python)                  │ Pub (Dart/Flutter)
    Cocoapods, Swift, Carthage    │ Go (Go)
    Nuget (.NET)                  │ Helm (Kubernetes)
    Unity (Unity)                 │ Cargo (Rust)

    ⚙️  General Options
    ────────────────────────────────────────────────────────────────────
    -p <path>              Path to analyze (default: current directory)
    -o <path>              Output file path or directory
    -f <format>            Output formats: {', '.join(SUPPORT_FORMAT)}
    -e <pattern>           Exclude paths from analysis (files and directories)
                           ⚠️  IMPORTANT: Always wrap in quotes to avoid shell expansion
                           Example: fosslight_dependency -e "test/" "node_modules/"
    -h                     Show this help message
    -v                     Show version information

    🔍 Scanner-Specific Options
    ────────────────────────────────────────────────────────────────────
    -m <manager>           Specify package manager (npm, maven, gradle, pypi, pub,
                           cocoapods, android, swift, carthage, go, nuget, helm,
                           unity, cargo, pnpm, yarn)
    -r                     Recursive mode: scan all subdirectories for manifest files
    --graph-path <path>    Save dependency graph image (pdf, jpg, png) (recommend pdf extension)
                           Example: fosslight_dependency --graph-path /your/path/filename.[pdf, jpg, png]
    --graph-format <format> Set graph image format (default: pdf)
    --graph-size <w> <h>   Set graph image size in pixels (requires --graph-path)
    --direct <True|False>  Print direct/transitive dependency type
                           Choose True or False (default: True)
    --notice               Print the open source license notice text

    🔧 Package Manager Specific Options
    ────────────────────────────────────────────────────────────────────
    Swift, Carthage:
      -t <token>           GitHub personal access token

    Pypi:
      -a <cmd>             Virtual environment activate command
                           (ex: 'conda activate myenv')
      -d <cmd>             Virtual environment deactivate command
                           (ex: 'conda deactivate')

    Gradle, Maven:
      -c <dir>             Customized build output directory
                           (default: 'build' for gradle, 'target' for maven)

    Android:
      -n <name>            Application directory name (default: app)

    💡 Examples
    ────────────────────────────────────────────────────────────────────
    # Scan current directory
    fosslight_dependency

    # Scan specific path with exclusions
    fosslight_dependency -p /path/to/project -e "test/" "vendor/"

    # Generate output in specific format
    fosslight_dependency -f excel -o results/

    # Specify package manager
    fosslight_dependency -m npm -p /path/to/nodejs/project

    # Recursive scan with all subdirectories
    fosslight_dependency -r

    # Generate dependency graph
    fosslight_dependency --graph-path dependency_tree.pdf
"""


def print_version(pkg_name: str) -> None:
    print_package_version(pkg_name, "FOSSLight Dependency Scanner Version:")


def print_help_msg():
    helpMsg = PrintHelpMsg(_HELP_MESSAGE_DEPENDENCY)
    helpMsg.print_help_msg(True)
