# Changelog

## v3.12.1 (01/01/1970)
## Changes
* No changes

---

## v3.12.0 (04/10/2022)
## Changes
## 🚀 Features

- Support nuget package manager @dd-jy (#100)

## 🔧 Maintenance

- Fix the path string for each platform @dd-jy (#102)
- Add the additional infor for Nuget @dd-jy (#101)
- Change log file name to fosslight_log_{datetime}.txt @dd-jy (#99)

---

## v3.11.7 (15/09/2022)
## Changes
## 🔧 Maintenance

- Change output report file name @dd-jy (#98)

---

## v3.11.6 (01/09/2022)
## Changes
## 🐛 Hotfixes

- Fix error when it fails to create venv for Pypi @dd-jy (#97)

## 🔧 Maintenance

- Change the help message @dd-jy (#96)

---

## v3.11.5 (23/08/2022)
## Changes
## 🐛 Hotfixes

- Fix to separate multi license for npm @dd-jy (#95)

---

## v3.11.4 (22/08/2022)
## Changes
## 🐛 Hotfixes

- Fix the comment for npm root package @dd-jy (#93)

## 🔧 Maintenance

- Separate multi license for Npm @dd-jy (#94)

---

## v3.11.3 (12/08/2022)
## Changes
## 🔧 Maintenance

- Change a message when there is no output @soimkim (#92)

---

## v3.11.2 (22/07/2022)
## Changes
## 🚀 Features

- [Enhancement] Golang go list option Fix @ehdwn1991 (#91)

---

## v3.11.1 (07/07/2022)
## Changes
## 🐛 Hotfixes

- Modify to analyze pub dependency @dd-jy (#90)

---

## v3.11.0 (16/06/2022)
## Changes
## 🚀 Features

- Add to generate yaml format result @dd-jy (#88)

## 🔧 Maintenance

- Change the output for Go @dd-jy (#89)

---

## v3.10.1 (10/05/2022)
## Changes
## 🔧 Maintenance

- Add --direct option in help message @dd-jy (#87)

---

## v3.10.0 (10/05/2022)
## Changes
## 🚀 Features

- Support to comment direct/transitive type @dd-jy (#83)

---

## v3.9.4 (11/04/2022)
## Changes
## 🚀 Features

- Support Package.resolved v2 (swift) @dd-jy (#84)

## 🐛 Hotfixes

- Fix to show npm package license even if not spdx @dd-jy (#80)
- Fix the npm issue (no packages to install) @dd-jy (#79)

## 🔧 Maintenance

- Add a commit message checker @soimkim (#82)

---

## v3.9.3 (11/03/2022)
## Changes
## 🔧 Maintenance

- Apply f-string format @bjk7119 (#78)
- Comment out some sentences in the PR template @soimkim (#77)

---

## v3.9.2 (14/02/2022)
## Changes
## 🐛 Hotfixes

- Support local scm package for Cocoapods @dd-jy (#76)

---

## v3.9.1 (10/02/2022)
## Changes
## 🔧 Maintenance

- Modify to print output file name @bjk7119 (#75)

---

## v3.9.0 (13/01/2022)
## Changes
## 🚀 Features

- Modify to analyze the license name for carthage @dd-jy (#73)

## 🔧 Maintenance

- Update the README to add 'how it works without Internet' @dd-jy (#74)

---

## v3.8.0 (24/12/2021)
## Changes
## 🚀 Features

- Support GO package manager @dd-jy (#71)

## 🔧 Maintenance

- Update CONTRIBUTING guide @dd-jy (#72)
- Fix typo @syleeeee (#70)
- Update README.md @syleeeee (#68)
- Update LicenseRef-3rd_party_licenses.txt @dd-jy (#67)

---

## v3.7.6 (18/11/2021)
## Changes
## 🚀 Features

- Add setup.py installation for pypi @dd-jy (#63)

## 🐛 Hotfixes

- Fix the pypi result when pip-licenses package exists @dd-jy (#66)

## 🔧 Maintenance

- Change the log when it fails to detect the package manager @dd-jy (#65)
- Fix url for User Guide @JustinWonjaePark (#64)

---

## v3.7.5 (04/11/2021)
## Changes
## 🔧 Maintenance

- Add maven scope into comment of FOSSLight report @dd-jy (#62)

---

## v3.7.4 (21/10/2021)
## Changes
## 🐛 Hotfixes

- Fix a bug related to return sheet_list in main @soimkim (#59)

## 🔧 Maintenance

- Add '-f(format)' option and modify '-o' option. @dd-jy (#61)
- Return sheet_list and change sheet name to SRC_FL_Dependency @soimkim (#60)
- Change sheet name to SRC_FL_Dependency from SRC @soimkim (#57)
- Run PR action for all branches @soimkim (#58)
- Return sheet_list from main @soimkim (#56)

---

## v3.7.3 (07/10/2021)
## Changes
## 🔧 Maintenance

- Modify -o option to add output file name(.csv, .xlsx) @dd-jy (#55)

---

## v3.7.2 (30/09/2021)
## Changes
## 🐛 Hotfixes

- Add test scope in excludedScopes for maven plugin @dd-jy (#54)

## 🔧 Maintenance

- Refactoring the code @dd-jy (#53)

---

## v3.7.1 (16/09/2021)
## Changes
## 🐛 Hotfixes

- Print pip-licenses, PTable packages if it already exists @dd-jy (#51)
- Fix the pypi windows venv command error without virtualenv package @dd-jy (#50)

## 🔧 Maintenance

- Add gitattributes to exclude test directory for languages @dd-jy (#52)
- Update README.md @k2heart (#49)

---

## v3.7.0 (27/08/2021)
## Changes
## 🚀 Features

- Support carthage package manager @dd-jy (#48)

---

## v3.6.1 (25/08/2021)
## Changes
## 🚀 Features

- Support swift package manager @dd-jy (#45)

## 🐛 Hotfixes

- Fix the gradle license parsing error @dd-jy (#47)
- Fix a bug related release actions @soimkim (#46)
- Fix the maven license result parsing issue @dd-jy (#44)

## 🔧 Maintenance

- Fix the gradle license parsing error @dd-jy (#47)
- Set condition to use FOSSLight Util v1.1.0 or later @bjk7119 (#43)
- Merge init_log & init_log_item functiions @bjk7119 (#40)
- Update version in setup.py when released @bjk7119 (#38)
- change the pypi license separator from ';' to ',' @dd-jy (#37)
- Update CONTRIBUTING.md @bjk7119 (#36)

---

## v3.5.0 (14/07/2021)
## Changes
## 🐛 Hotfixes

- Fix the android scanning issues @dd-jy (#35)

## 🔧 Maintenance

- Fix the android scanning issues @dd-jy (#35)
- Move user-guide link to FOSSLight guide &  @dd-jy (#34)
- Add tox test for windows and MacOS @bjk7119 (#34)
- Add tox test for each package manger in Ubuntu environment @bjk7119 (#31)

---

## v3.4.0 (02/07/2021)
## Changes
## 🐛 Hotfixes

- Fix the windows executable file issue @dd-jy (#30)

---

## v3.3.0 (24/06/2021)
## Changes
## 🐛 Hotfixes

- Fix the pub parsing error @dd-jy (#29)

---

## v3.2.1 (24/06/2021)
## 🔧 Maintenance

- Update PR action commands @soimkim (#28)
- Update nomos standalone binary and source @dd-jy (#27)
- Update nomos standalone binary @dd-jy (#25)
- Update reuse related files @soimkim (#24)
- Change name to FOSSLight Dependency Scanner @dd-jy (#23)
