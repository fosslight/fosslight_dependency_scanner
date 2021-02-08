# User Guide 
<br>

## 1. Prerequisite
### How to analyze the dependencies
FOSSLight dependency utilizes the open source software for analyzing each package manager dependencies. We choose the open source software for each package manager that shows not only the direct dependencies but also the transitive dependencies including the information of dependencies such as oss name, oss version and license name.

Each package manager uses the results of the following software:
- NPM : [NPM License Checker](https://github.com/davglass/license-checker)
- Pypi : [pip-licenses](https://github.com/raimon49/pip-licenses)
- Gradle : [License Gradle Plugin](https://github.com/hierynomus/license-gradle-plugin)
- Maven : [license-maven-plugin](https://github.com/mojohaus/license-maven-plugin)
- Pub : [flutter_oss_licenses](https://github.com/espresso3389/flutter_oss_licenses)

Because we utilizes the different open source software to analyze the dependencies of each package manager, you need to set up the below steps according to package manager to analyze.

### NPM
1. Install the NPM License Checker to ananlyze the npm dependencies. (required)
```
$ npm install -g license-checker
```
2. Run the command to install the dependencies (optional)
```
$ npm install
```

### Gradle (required)
1. Add the License Gradle Plugin in build.gradle file.
```
plugins {
    id 'com.github.hierynomus.license' version '0.15.0'
}
 
downloadLicenses {
    includeProjectDependencies = true
    dependencyConfiguration = 'runtimeClasspath' // If the gradle version is 4.6 or lower, then add the 'runtime' instead of 'runtimeClasspath'.
}
```
2. Run the task.
```
$ gradle downloadLicenses
```

### Pypi (required)
You can run this tool with virtualenv environment for separating the project dependencies from system dependencies.
1. Create the virtualenv environment
```
// conda example
$ conda create --name {venv name}
$ conda activate {venv name}
```
2. Install the dependencies
```
// If you install the dependencies with requirements.txt...
$ pip install -r requirements.txt
```

### Maven (optional)
1. Add the license-maven-plugin into pom.xml file.
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
2. Run the license-maven-plugin.
```
$ mvn license:aggregate-download-licenses
```

### Pub (required)
1. Run the flutter_oss_licenses.
```
$ flutter pub get
$ flutter pub global activate flutter_oss_licenses
$ flutter pub global run flutter_oss_licenses:generate.dart
```

<br>

## 2. How to install
Python2.7 or Python3.6+ supports.
### From pip
```
pip install fosslight-dependency
```
Or
```
pip install git+https://github.com/LGE-OSS/fosslight_dependency.git
```
### From source code
```
git clone https://github.com/LGE-OSS/fosslight_dependency.git
cd fosslight_dependency
python setup.py install
```

<br>

## 3. How to run
You can run the FOSSLight dependency with options based on your package manager.
```
$ fosslight_dependency
```
| Options | Description | Value |
| --------- | ------------- | ------- |
| -m | (optional) <br> package manager for your project | npm, maven, gradle, pip, pub |
| -p | (optional) <br> input directory | (path) |
| -o | (optional) <br> output file directory | (path) |
| -a | (pypi only required) <br> virtual environment activate command | conda example: 'conda activate (venv name)' |
| -d | (pypi only required) <br> virtual environment deactivate command | conda example: 'conda deactivate' |
| -c | (gradle, maven only optional) <br> customized build output directory name (default: target) | (customized output directory name) |
| -v | version of the script | N/A |

Note that input directory should be the top directory of the project where the manifest file of the package manager is located.
For example, if your project uses the NPM package manager, then the input directory should be the path where 'package.json' file is located.
Similarily, the manifest file of pip is 'requirements.txt', maven has 'pom.xml' manifest file and gradle has 'build.gradle' manifest file.
If you want to run the command with other path, then you can use '-p' option.


<br>

## 4. How to generate Result file
FOSSLight dependency creates the result file that has xlsx extension (Microsoft Excel file).

It prints the OSS information based on manifest file(package.json, pom.xml) of dependencies (including transitive dependenices).
For a unique OSS name, OSS name is printed such as (package_manager):(oss name) or (group id):(artifact id).

| Package manager | OSS Name           | Download Location | Homepage |
| --------------- | ------------------ | ----------------- | -------- |
| Npm             | npm:(oss name)     | Priority1. repository in package.json <br> Priority2. www.npmjs.com/package/(oss_name) | www.npmjs.com/package/(oss_name) |
| Pip             | pypi:(oss name)    | https://pypi.org/project/(oss_name)/(version) | homepage in (pip show) information |
| Maven (Gradle) | (group_id):(artifact_id) | https://mvnrepository.com/artifact/(group_id)/(artifact_id)/(version) | https://mvnrepository.com/artifact/(group_id)/(artifact_id) |
| Pub             | (oss name)         | homepage in (pub information) | homepage in (pub information) |

