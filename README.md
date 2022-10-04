<!--
Copyright (c) 2021 LG Electronics
SPDX-License-Identifier: Apache-2.0
 -->
# FOSSLight Dependency Scanner

<img src="https://img.shields.io/pypi/l/fosslight_dependency" alt="License" /> <a href="https://pypi.org/project/fosslight-dependency/"><img src="https://img.shields.io/pypi/v/fosslight_dependency" alt="Current python package version." /></a> <img src="https://img.shields.io/pypi/pyversions/fosslight_dependency" /> [![REUSE status](https://api.reuse.software/badge/github.com/fosslight/fosslight_dependency_scanner)](https://api.reuse.software/info/github.com/fosslight/fosslight_dependency_scanner)


## 💡 Introduction

This is the tool that supports the analysis of dependencies for multiple package managers. It detects the manifest file of package managers automatically and analyzes the dependencies with using open source tools. Then, it generates the report file that contains OSS information of dependencies.


## 📖 User Guide

We describe the user guide in the [**FOSSLight Guide page**](https://fosslight.org/fosslight-guide-en/scanner/3_dependency.html).  
In this user guide, you can see how to install the FOSSLight Dependency Scanner and how to set up the prerequisite step and run it according to the package manager of your project. Also, you can check the results of the FOSSLight Dependency Scanner.


## 🧐 How to analyze the dependencies

FOSSLight Dependency Scanner utilizes the open source software for analyzing each package manager dependencies. We choose the open source software for each package manager that shows not only the direct dependencies but also the transitive dependencies including the information of dependencies such as oss name, oss version and license name.

Each package manager uses the results of the following software:

- NPM : [NPM License Checker](https://github.com/davglass/license-checker)
- Pypi : [pip-licenses](https://github.com/raimon49/pip-licenses)
- Gradle : [License Gradle Plugin](https://github.com/hierynomus/license-gradle-plugin)
- Maven : [license-maven-plugin](https://github.com/mojohaus/license-maven-plugin)
- Pub : [flutter_oss_licenses](https://github.com/espresso3389/flutter_oss_licenses)
- Android(gradle) : [android-dependency-scanning](https://github.com/fosslight/android-dependency-scanning)

Because we utilizes the different open source software to analyze the dependencies of each package manager, you need to set up the **Prerequisite** steps in [User guide](https://fosslight.org/fosslight-guide-en/scanner/3_dependency.html#-prerequisite) according to package manager to analyze.


### 🌐 How it works without Internet
| Package manager | Can it work without Internet?             |
|-----------------|-------------------------------------------|
| [Gradle](https://gradle.org/) (Java)          | Yes, if the following conditions are met. <br /> - installed the plugin([com.github.hierynomus.license '0.16.1'](https://plugins.gradle.org/plugin/com.github.hierynomus.license/0.16.1)) <br /> - installed the packages of the project |
| [Maven](http://maven.apache.org/) (Java)           | Yes, if the following conditions are met. <br /> - installed the plugin([org.codehaus.mojo:license-maven-plugin](https://search.maven.org/artifact/org.codehaus.mojo/license-maven-plugin/2.0.0/)) <br /> - installed the packages of the project |
| [NPM](https://www.npmjs.com/) (Node.js)             | Yes, if the following conditions are met. <br /> - installed the plugin([license-checker](https://www.npmjs.com/package/license-checker)) <br /> - installed the packages of the project (in other words, generated the node_modules directory) |
| [PIP](https://pip.pypa.io/) (Python)             | No, it can't.                              |
| [Android(gradle)](https://gradle.org/) (Android application)       | Yes, if the following conditions are met. <br /> - installed the plugin([android-dependency-scanning](https://search.maven.org/artifact/org.fosslight/android-dependency-scanning/1.0.0/jar)) <br /> - installed the packages of the project |
| [Pub](https://pub.dev/) (Dart with flutter)             | Yes, if the following conditions are met. <br /> - installed the plugin([flutter_oss_licenses](https://pub.dev/packages/flutter_oss_licenses)) <br /> - installed the packages of the project |
| [Cocoapods](https://cocoapods.org/) (Swift/Obj-C)       | Yes, if the following conditions are met. <br /> - installed the packages of the project <br /> - enable to run the command (pod spec which --regex {package name} ) |
| [Swift](https://swift.org/package-manager/) (Swift)           | No, it can't.                              |
| [Carthage](https://github.com/Carthage/Carthage) (Swift/Obj-C)        | Yes, if the following conditions are met. <br /> - installed the packages of the project (in other words, downloadeded the sources in 'Carthgae/Checkouts' directory). |
| [Go](https://pkg.go.dev/) (Go)              | No, it can't.                              |
| [Nuget](https://www.nuget.org/) (.NET)      | No, it can't.                              |


## 👏 Contributing Guide

We always welcome your contributions.  
Please see the [CONTRIBUTING guide](https://github.com/fosslight/fosslight_dependency_scanner/blob/main/CONTRIBUTING.md) for how to contribute.


## 📄 License

Copyright (c) 2020 LG Electronics, Inc.  
FOSSLight Dependency Scanner is licensed under Apache-2.0, as found in the [LICENSE](https://github.com/fosslight/fosslight_dependency_scanner/blob/main/LICENSE) file.
