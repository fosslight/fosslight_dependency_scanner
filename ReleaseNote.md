# ReleaseNote

### V3.0.5 (2021.03.19)
 - Support the cocoapods package manager.

### V3.0.4 (2021.03.13)
 - Modify to include binaries that analyze license text.

### V3.0.2 (2021.03.05)
 - Modify to generate a single oss for multiple license names for npm,maven.

### V3.0.1 (2021.02.23)
 - Change the result report format for pub package manager.

### V3.0.0 (2021.01.21)
 - Create fossology_dependency github repository and upload the source codes.
 
### V2.4.2 (2021.01.13)
- Add virtualenv to requirements.txt

### V2.4.1 (2021.01.11)
- fix the pip to run in Windows

### V2.4.0 (2020.12.08)
- Refactoring the code
  * change print function to logging
  * fix the code warning
  * change the main function

### V2.3.2 (2020.11.25)
- Fix the issue that maven dependency scanning was not executed on Python2.7.
- Fix the error that cannot remove the output directory of maven dependency scanning.
- add options
  * '-p' option, you can enter the path to run the script.
  * '-o' option, you can enter the path to generate result file.
  * '-v' option, it prints the version of the script.
- change option
  * '-o' option -> '-c' option : the customized build output directory of pom.xml, build.gradle

### V2.3.1 (2020.11.13)
- Fix the error for dependency_unified.exe
  1) remove the unused dependency pip package
  2) add the path that askalono.exe is located

### V2.3.0 (2020.10.12)
- Support pub(package manager for dart/flutter) dependency scanning

### V2.2.0 (2020.09.11)
- Change pip dependency scanning option
  1) 'a' option : virtual environment activate command
  2) 'd' option : virtual environment deactivate command
- run the 'npm install' automatically in the script for npm scanning
- run the 'license-maven-plugin' automatically in the script for maven scanning

### V2.1.0 (2020.09.04)
- Change pip dependency scanning process
  1) change '-a' option : enter the virtualenv full path
  2) change nomossa_linux binary

### V2.0.2 (2020.07.20)
- Remove 'License Text' info in OSS report

### V2.0.1 (2020.07.06)
- Add '-o' option for the customized build output directory of pom.xml, build.gradle

### V2.0.0 (2020.04.21)
- Change the printed OSS name, download location, homepage format.
  (Please read the README.txt for details.)
- Add README.txt and ReleaseNote

### V1.0.0 (2020.01.28)
- Initial release of dependency_unified script
- Change to the unified script for four package managers(npm,pypi,maven,gradle)
