# Changelog

## v3.15.2 (14/06/2024)
## Changes
- Change depends on to purl @dd-jy (#195)

---

## v3.15.1 (10/06/2024)
## Changes
## 🚀 Features

- Supports for excluding paths @SeongjunJo (#200)

## 🔧 Maintenance

- Change Package URL col name @dd-jy (#203)

---

## v3.15.0 (22/05/2024)
## Changes
## 🚀 Features

- Add android-dependency-scanning plugin automatically @dd-jy (#202)

---

## v3.14.3 (16/05/2024)
## Changes
## 🐛 Hotfixes

- Fix the issue of adding allDeps task for android @dd-jy (#201)
- Add the version into unity purl @dd-jy (#198)
- Fix the issue for go.work (go 1.18 or later) @dd-jy (#199)

---

## v3.14.2 (08/05/2024)
## Changes
## 🚀 Features

- Support unity package manager @dd-jy (#197)

## 🐛 Hotfixes

- Fix the fail package manager comment @dd-jy (#196)

---

## v3.14.1 (26/04/2024)
## Changes

## 🚀 Features

- Add detection summary message (cover sheet) @dd-jy (#191)
- Change manifest col to purl col @dd-jy (#190)

## 🔧 Maintenance

- Change col name @dd-jy (#193)

---

## v3.14.0 (29/02/2024)
## Changes
## 🚀 Features

- Fix the pypi direct/transitive bug, Support pyproject.toml @dd-jy (#187)

## 🐛 Hotfixes

- Fix the pypi direct/transitive bug, Support pyproject.toml @dd-jy (#187)

## 🔧 Maintenance

- Modify the oss info for local package of cocoapods @dd-jy (#189)
- Use common github actions @bjk7119 (#188)

---

## v3.13.9 (05/01/2024)
## Changes
## 🐛 Hotfixes

- Add exception when no dependencies in Chart.yaml @dd-jy (#186)
- Fix the npm issue (no dependencies in package.json) @dd-jy (#185)

---

## v3.13.8 (27/12/2023)
## Changes
## 🐛 Hotfixes

- Fix the typo @dd-jy (#184)


---

## v3.13.7 (22/12/2023)
## Changes
## 🐛 Hotfixes

- Add the exception when the maven subprocess raises the error @dd-jy (#182)

## 🔧 Maintenance

- Normalize pypi package name (PEP 0503) @dd-jy (#181)

---

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
