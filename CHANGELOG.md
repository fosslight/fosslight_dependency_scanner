# Changelog

## v3.13.6 (09/11/2023)
## Changes
## 🚀 Features

- Find the top directory where the manifest file is located @dd-jy (#180)

## 🐛 Hotfixes

- Fix the direct/transitive bug @dd-jy (#178)

## 🔧 Maintenance

- Change the sheet name @dd-jy (#179)

---

## v3.13.5 (13/10/2023)
## Changes

## 🐛 Hotfixes

- Fix the bug of direct/transitive npm packages @dd-jy (#176, #177)
- Fix the maven direct/transitive comment @dd-jy (#175)

## 🔧 Maintenance

- Update readme @dd-jy (#174)
- Fix the vulnerability @dd-jy (#171)
- Change None string to N/A for pub homepage @dd-jy (#139)

---

## v3.13.4 (19/05/2023)
## Changes
## 🐛 Hotfixes

- Fix to use customized output format @dd-jy (#137)

---

## v3.13.3 (08/05/2023)
## Changes
## 🚀 Features

- Support spdx format result @dd-jy (#136)

---

## v3.13.2 (18/04/2023)
## Changes
## 🚀 Features

- Add dependencies of swift in comment @dd-jy (#133)

## 🐛 Hotfixes

- Fix the breaking script when npm ls returns error @dd-jy, @RHeynsZa (#132)

---

## v3.13.1 (07/04/2023)
## Changes
## 🚀 Features

- Add dependencies of cocoapods, go, nuget package in comment @dd-jy (#130)

## 🐛 Hotfixes

- Add dependencies of cocoapods, go, nuget package in comment @dd-jy (#130)

## 🔧 Maintenance

- Add the helm in help meesage @dd-jy (#129)

---

## v3.13.0 (22/03/2023)
## Changes
## 🚀 Features

- Print the dependencies of each package in comment @dd-jy (#128)
  - Implemented : gradle(java, android), maven, npm, pypi, pub
  - Not implemented yet : cocoapods, go, nuget, swift

---

## v3.12.7 (09/03/2023)
## Changes
## 🚀 Features

- Support Helm package manager @dd-jy (#125)

## 🐛 Hotfixes

- Fix the encoding issue @dd-jy (#127)

---

## v3.12.6 (23/02/2023)
## Changes
## 🐛 Hotfixes

- Fix the cocoapods issue @dd-jy (#124)

## 🔧 Maintenance

- Fix the cocoapods issue @dd-jy (#124)

---

## v3.12.5 (27/01/2023)
## Changes
## 🔧 Maintenance

- Unify version output format @bjk7119 (#123)

---

## v3.12.4 (05/01/2023)
## Changes
## 🐛 Hotfixes

- Fix the npm multi license issue @dd-jy (#122)

## 🔧 Maintenance

- Change package to get release package @bjk7119 (#121)
- Update version of packages for actions @bjk7119 (#120)

---

## v3.12.3 (22/12/2022)
## Changes
## 🐛 Hotfixes

- Fix the parsing bug for swift's Package.resolved @dd-jy (#107)

---

## v3.12.2 (24/11/2022)
## Changes
## 🐛 Hotfixes

- Fix the gradle direct/transitive issue @dd-jy (#106)

## 🔧 Maintenance

- Fix duplicated output file if multi package manager @dd-jy (#105)

---

## v3.12.1 (27/10/2022)
## Changes
## 🚀 Features

- Exclude private packages from NPM license-checker @Elastino (#103)

## 🔧 Maintenance

- Print license text through notice parameter @dd-jy (#104)

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
