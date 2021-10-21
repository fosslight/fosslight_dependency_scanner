# Changelog

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

---

## v3.2.0 (11/06/2021)
## Changes
## 🚀 Features

- add android dependency scanning @dd-jy (#21)

## 🔧 Maintenance

- change user guide @dd-jy (#22)

---

## v3.1.0 (10/06/2021)
## Changes
## 🐛 Hotfixes

- fix the executable file import error @dd-jy (#20)

## 🔧 Maintenance

- Add files for reuse compliance. @soimkim (#19)
- Update only CHANGELOG.md when releasing @soimkim (#18)
- Apply Tox Configuration & Change help message @bjk7119 (#17)

---

## v3.0.7 (17/05/2021)
## Changes
## 🔧 Maintenance

- Refactoring code and use fosslight_util @dd-jy (#15)
- Update user-guide.md @dd-jy (#14)
- Update contributing guide about DCO @dd-jy (#13)
- Update the pypi description to README.md @dd-jy (#12)
- Add 'cocoapods:' to oss name for cocoapods package @dd-jy (#11)
- Change oss name for cocoapods package manager @dd-jy (#10)
- Create CODE_OF_CONDUCT.md @dd-jy (#9)
- Add CONTRIBUTING.md @dd-jy (#8)

---

## v3.0.6 (25/03/2021)
## Changes
## 🐛 Hotfixes

- Fix the cocoapods error @dd-jy (#7)

## 🔧 Maintenance

- Update changelog @dd-jy (#6)
- Update github workflows @dd-jy (#5)
---

## v3.0.5 (19/03/2021)
## Changes
## 🚀 Features
- Support cocoapods package manager


---

## v3.0.4 (13/03/2021)
## Changes
## 🔧 Maintenance
- Add license file to wheel
---

## v3.0.3 (12/03/2021)
## Changes
## 🔧 Maintenance
- Modify to include binaries that analyze license text.
---

## v3.0.2 (05/03/2021)
## Changes
## 🐛 Hotfixes
- Fix to generate a single oss for multiple license names for npm, maven
---

## v3.0.1 (26/02/2021)
## Changes
## 🚀 Features
- Add prefix 'pub:' to oss name in result file for pub package manager
## 🔧 Maintenance
- Update 3rd party License text
- Update documents (README, user-guide)
---

## v3.0.0 (27/01/2021)
## Changes
## 🚀 Features
- FOSSLight dependency initial release