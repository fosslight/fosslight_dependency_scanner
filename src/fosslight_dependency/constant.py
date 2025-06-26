#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0
import os

# System platform name
WINDOWS = 'Windows'
LINUX = 'Linux'
MACOS = 'Darwin'

# Package manager name
PYPI = 'pypi'
NPM = 'npm'
MAVEN = 'maven'
GRADLE = 'gradle'
PUB = 'pub'
COCOAPODS = 'cocoapods'
ANDROID = 'android'
SWIFT = 'swift'
CARTHAGE = 'carthage'
GO = 'go'
NUGET = 'nuget'
HELM = 'helm'
UNITY = 'unity'
CARGO = 'cargo'
PNPM = 'pnpm'

# Supported package name and manifest file
SUPPORT_PACKAE = {
    PYPI: ['requirements.txt', 'setup.py', 'pyproject.toml'],
    PNPM: 'pnpm-lock.yaml',
    NPM: 'package.json',
    MAVEN: 'pom.xml',
    GRADLE: 'build.gradle',
    PUB: 'pubspec.yaml',
    COCOAPODS: 'Podfile.lock',
    ANDROID: 'build.gradle',
    SWIFT: 'Package.resolved',
    CARTHAGE: 'Cartfile.resolved',
    GO: 'go.mod',
    NUGET: ['packages.config', os.path.join('obj', 'project.assets.json')],
    HELM: 'Chart.yaml',
    UNITY: os.path.join('Library', 'PackageManager', 'ProjectCache'),
    CARGO: 'Cargo.toml'
}

SUGGESTED_PACKAGE = {
    'Podfile': COCOAPODS,
    'Package.swift': SWIFT,
    'Cartfile': CARTHAGE
}

# default android app name
default_app_name = 'app'
