<!--
Copyright (c) 2021 LG Electronics
SPDX-License-Identifier: Apache-2.0
 -->
testest
# FOSSLight Dependency Scanner

<img src="https://img.shields.io/pypi/l/fosslight_dependency" alt="License" /> <img src="https://img.shields.io/pypi/v/fosslight_dependency" alt="Current python package version." /> <img src="https://img.shields.io/pypi/pyversions/fosslight_dependency" /> [![REUSE status](https://api.reuse.software/badge/github.com/fosslight/fosslight_dependency_scanner)](https://api.reuse.software/info/github.com/fosslight/fosslight_dependency_scanner)

## 💡 Introduction

This is the tool that supports the analysis of dependencies for multiple package managers. It detects the manifest file of package managers automatically and analyzes the dependencies with using open source tools. Then, it generates the report file that contains OSS information of dependencies.

Currently, it supports the following package managers.

- [Gradle](https://gradle.org/) (Java)
- [Maven](http://maven.apache.org/) (Java)
- [NPM](https://www.npmjs.com/) (Node.js)
- [PIP](https://pip.pypa.io/) (Python)
- [Pub](https://pub.dev/) (Dart with flutter)
- [Cocoapods](https://cocoapods.org/) (Swift/Obj-C)
- [Swift](https://swift.org/package-manager/) (Swift)
- [Carthage](https://github.com/Carthage/Carthage) (Swift/Obj-C)

## 🧐 How to analyze the dependencies

FOSSLight Dependency Scanner utilizes the open source software for analyzing each package manager dependencies. We choose the open source software for each package manager that shows not only the direct dependencies but also the transitive dependencies including the information of dependencies such as oss name, oss version and license name.

Each package manager uses the results of the following software:

- NPM : [NPM License Checker](https://github.com/davglass/license-checker)
- Pypi : [pip-licenses](https://github.com/raimon49/pip-licenses)
- Gradle : [License Gradle Plugin](https://github.com/hierynomus/license-gradle-plugin)
- Maven : [license-maven-plugin](https://github.com/mojohaus/license-maven-plugin)
- Pub : [flutter_oss_licenses](https://github.com/espresso3389/flutter_oss_licenses)
- Android(gradle) : [android-dependency-scanning](https://github.com/fosslight/android-dependency-scanning)

Because we utilizes the different open source software to analyze the dependencies of each package manager, you need to set up the **Prerequisite** steps in [User guide](https://fosslight.org/fosslight-guide-en/scanner/2_dependency.html) according to package manager to analyze.

## 📖 User Guide

We describe the user guide in the FOSSLight guide page.
Please see the [**User Guide**](https://fosslight.org/fosslight-guide-en/scanner/2_dependency.html) for more information on how to install and run it.

## 👏 Contributing Guide

We always welcome your contributions.  
Please see the [CONTRIBUTING guide](https://github.com/fosslight/fosslight_dependency_scanner/blob/main/CONTRIBUTING.md) for how to contribute.

## 📄 License

Copyright (c) 2020 LG Electronics, Inc.  
FOSSLight Dependency Scanner is licensed under Apache-2.0, as found in the [LICENSE](https://github.com/fosslight/fosslight_dependency_scanner/blob/main/LICENSE) file.
