<!--
Copyright (c) 2021 LG Electronics
SPDX-License-Identifier: Apache-2.0
 -->
 <p align='right'>
  <a href="https://github.com/fosslight/fosslight_dependency_scanner/blob/main/docs/user-guide.md">[English]</a>
</p>

# User Guide

## Contents

- [How to analyze the dependencies](#-how-to-analyze-the-dependencies)
- [Prerequisite](#-prerequisite)
  - [NPM](#npm)
  - [Gradle](#gradle)
  - [Gradle - Android](#android-gradle)
  - [Pypi](#pypi)
  - [Maven](#maven-optional)
  - [Pub](#pub)
  - [Cocoapods](#cocoapods)
- [How to install](#-how-to-install)
- [How to run](#-how-to-run)
- [Result](#-result)

<br>

## 🧐 How to analyze the dependencies

FOSSLight Dependency Scanner는 다른 오픈소스 소프트웨어를 이용하여 여러 패키지 매니저들의 dependency 분석을 수행하고 있습니다. 그 중 다음 기준에 따라 오픈소스 소프트웨어를 선택하고 있습니다.

1. Direct dependency뿐만 아니라 transitive dependency까지 추출 가능
2. 오픈소스 이름, 버전, License명 추출 가능

각 패키지 매니저에 따라 이용하는 오픈소스 소프트웨어는 다음과 같습니다:

- NPM : [NPM License Checker](https://github.com/davglass/license-checker)
- Pypi : [pip-licenses](https://github.com/raimon49/pip-licenses)
- Gradle : [License Gradle Plugin](https://github.com/hierynomus/license-gradle-plugin)
- Maven : [license-maven-plugin](https://github.com/mojohaus/license-maven-plugin)
- Pub : [flutter_oss_licenses](https://github.com/espresso3389/flutter_oss_licenses)

따라서 각 패키지 매니저마다 다른 오픈소스 소프트웨어를 이용하기 때문에, 분석하고자 하는 패키지 매니저에 따라 아래 [Prerequisite](#-prerequisite) 단계를 수행하시기 바랍니다.

<br>

## 📋 Prerequisite

### NPM

1. Npm dependency 분석을 수행하기 위해 NPM License Checker를 설치합니다.

```
$ npm install -g license-checker
```

2. dependency를 설치하기 위해 다음 명령어를 실행합니다. (optional)

```
$ npm install
```

> - package.json 파일이 input directory에 존재하는 경우, 해당 명령어 실행은 FOSSLight Dependency Scanner에서 자동으로 수행하므로 skip 가능합니다.
> - 이미 dependency들이 설치된 node_modules 디렉토리가 존재하는 경우, node_modules폴더가 존재하는 path를 input directory로 설정하여 실행 가능합니다.

<br>

### Gradle

1. 'build.gradle' 파일에 License Gradle Plugin을 추가합니다.

```
plugins {
    id 'com.github.hierynomus.license' version '0.15.0'
}

downloadLicenses {
    includeProjectDependencies = true
    dependencyConfiguration = 'runtimeClasspath'
}
```

> - 사용하는 gradle 버전이 4.6 또는 더 낮은 버전인 경우에는, dependencyConfiguration에 'runtimeClasspath' 대신 'runtime'을 추가합니다.

2. 'downloadLicenses' task를 실행합니다.

```
$ gradle downloadLicenses
```

<br>

### Android (gradle)

1. 'build.gradle' 파일에 Android License Plugin을 추가합니다.

```
buildscript {
    repositories {
        jcenter()
    }

    dependencies {
        classpath 'com.lge.android.licensetools:dependency-scanning-tool:0.4.0'
    }
}

apply plugin: 'com.lge.android.licensetools'
```

2. 'generateLicenseTxt' task를 실행합니다.

```
$ gradle generateLicenseTxt
```

<br>

### Pypi

시스템 내 전역으로 설치된 파이썬 dependency로부터 분석하고자 하는 프로젝트 dependency를 분리하기 위해 가상환경을 설정하여 이용하기를 권장합니다.

1. 가상환경을 생성하고 활성화합니다.

```
// virtualenv example
$ virtualenv -p /usr/bin/python3.6 venv
$ source venv/bin/activate

// conda example
$ conda create --name {venv name}
$ conda activate {venv name}
```

2. 가상환경 내 분석하고자 하는 프로젝트의 dependency를 설치합니다.

```
// If you install the dependencies with requirements.txt...
$ pip install -r requirements.txt
```

<br>

### Maven (optional)

> - Maven의 경우, input directory에 pom.xml 파일이 존재하는 경우, plugin 추가 및 실행을 FOSSLight Dependency Scanner 내부에서 자동으로 수행하므로 다음은 skip하셔도 됩니다.

1. pom.xml 파일에 license-maven-plugin을 추가합니다.

```
<project>
  ...
  <build>
  ...
    <plugins>
    ...
      <plugin>
        <groupId>org.codehaus.mojo</groupId>
        <artifactId>license-maven-plugin</artifactId>
        <version>2.0.0</version>
        <executions>
          <execution>
            <id>aggregate-download-licenses</id>
            <goals>
              <goal>aggregate-download-licenses</goal>
            </goals>
          </execution>
        </executions>
      </plugin>
    </plugins>
    ...
  </build>
  ...
</project>
```

2. license-maven-plugin task를 실행합니다.

```
$ mvn license:aggregate-download-licenses
```

<br>

### Pub

1. 다음 명령어를 통해 flutter_oss_licenses를 실행합니다.

```
$ flutter pub get
$ flutter pub global activate flutter_oss_licenses
$ flutter pub global run flutter_oss_licenses:generate.dart
```

<br>

### Cocoapods

1. Podfile을 통해 pod package를 설치합니다.

```
$ pod install
```

<br>

## 🎉 How to install

FOSSLight Dependency Scanner는 Python3.6+ 환경에서 설치할 것을 권장합니다.

### From pip

```
$ pip install fosslight-dependency
```

### From source code

```
$ git clone https://github.com/fosslight/fosslight_dependency_scanner.git
$ cd fosslight_dependency_scanner
$ pip install .
```

<br>

## 🚀 How to run

FOSSLight Dependency Scanner는 패키지 매니저에 따라 다음 option들을 이용하여 실행할 수 있습니다.

```
$ fosslight_dependency
```

| Option | Argument                                    | Description                                                                                  |
| ------ | ------------------------------------------- | -------------------------------------------------------------------------------------------- |
| -m     | npm, maven, gradle, pip, pub, cocoapods     | (optional) <br> 프로젝트의 package manager                                                   |
| -p     | (path)                                      | (optional) <br> 분석하고자 하는 input directory                                              |
| -o     | (path)                                      | (optional) <br> 결과 파일이 생성되는 output directory                                        |
| -a     | conda example: 'conda activate (venv name)' | (pypi only required) <br> 가상환경 activate command                                          |
| -d     | conda example: 'conda deactivate'           | (pypi only required) <br> 가상환경 deactivate command                                        |
| -c     | (customized output directory name)          | (gradle, maven only optional) <br> 커스터마이즈한 build output directory명 (default: target) |
| -n     | (app name)                                  | (android only optional) <br> app directory name (default: app)                               |
| -v     | N/A                                         | release 버전                                                                                 |

이때, FOSSLight Dependency Scanner는 패키지 매니저의 manifest 파일이 존재하는 프로젝트의 top directory에서 실행되어야 합니다.
예를 들면, NPM 패키지 매니저를 이용하는 프로젝트의 경우, input directory는 'package.json' 파일이 존재하는 directory여야 합니다.
각 패키지 매니저별 manifest 파일은 다음과 같습니다.

| Package manager | Npm          | Pip              | Maven   | Gradle       | Pub          | Cocoapods | Android |
| --------------- | ------------ | ---------------- | ------- | ------------ | ------------ | --------- | ------- |
| Manifest file   | package.json | requirements.txt | pom.xml | build.gradle | pubspec.yaml | Podfile   | gradlew |

즉, FOSSLight Dependency Scanner 실행 시, input directory('-p' 옵션)는 위와 같이 패키지 매니저의 manifest 파일이 존재하는 프로젝트의 top directory로 지정해 주어야 합니다.
Android 프로젝트의 실제 manifest file은 다른 gradle 프로젝트와 동일한 'build.gradle' 파일이지만, 다른 java 프로젝트와 구별하기 위해 gradlew 파일로 지정하였습니다.
<br>

## 📁 Result

FOSSLight Dependency Scanner는 xlsx(Microsoft Excel file)양식의 결과 파일을 생성합니다.

결과 파일에는 transitive dependency들을 포함한 모든 분석된 dependency들의 manifest 파일을 기반으로 OSS 정보가 기록됩니다.
이때, 고유한 OSS명을 작성하기 위해, OSS명은 (패키지 매니저):(OSS명) 또는 (group id):(artifact id) 양식으로 기록됩니다.

| Package manager                | OSS Name                 | Download Location                                                                                  | Homepage                                            |
| ------------------------------ | ------------------------ | -------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| Npm                            | npm:(oss name)           | 우선순위1. repository in package.json <br> 우선순위2. npmjs.com/package/(oss name)/v/(oss version) | npmjs.com/package/(oss name)                        |
| Pip                            | pypi:(oss name)          | pypi.org/project/(oss name)/(version)                                                              | homepage in (pip show) information                  |
| Maven<br>& Gradle<br>& Android | (group_id):(artifact_id) | mvnrepository.com/artifact/(group id)/(artifact id)/(version)                                      | mvnrepository.com/artifact/(group id)/(artifact id) |
| Pub                            | pub:(oss name)           | pub.dev/packages/(oss name)/versions/(version)                                                     | homepage in (pub information)                       |
| Cocoapods                      | cocoapods:(oss name)     | source in (pod spec information)                                                                   | cocoapods.org/(oss name)                            |
