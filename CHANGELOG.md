# Changelog

## v4.1.12 (09/05/2025)
## Changes
## 🐛 Hotfixes

- Fix bug about mvnw cmd @dd-jy (#253)

---

## v4.1.11 (23/04/2025)
## Changes
## 🐛 Hotfixes

- Fix to detect pypi install error @dd-jy (#252)

---

## v4.1.10 (16/04/2025)
## Changes
## 🐛 Hotfixes

- Fix to retry virtualenv for pypi @dd-jy (#250)

## 🔧 Maintenance

- Add venv into .gitignore @dd-jy (#249)
- Change flake8 github action @dd-jy (#248)

---

## v4.1.9 (17/03/2025)
## Changes
## 🚀 Features

- Support pnpm for nodejs project @dd-jy (#247)

---

## v4.1.8 (27/02/2025)
## Changes
## 🚀 Features

- Change license scanner to askalono package @dd-jy (#242)

## 🐛 Hotfixes

- Fix the manual option issue @dd-jy (#246)
- Fix the feature to automatically find manifest file @dd-jy (#243)

## 🔧 Maintenance

- Modify NuGet's API url to lower case @dd-jy (#245)
- Fix to analyze gradle with only plugin input file @dd-jy (#244)

---

## v4.1.7 (14/02/2025)
## Changes
## 🐛 Hotfixes

- Fix the docs.unity3d url with minor version @dd-jy (#240)
- Fix to check if unity url is alive @dd-jy (#239)

## 🔧 Maintenance

- Add temporary execute mode for wrapper @dd-jy (#241)

---

## v4.1.6 (16/01/2025)
## Changes
## 🚀 Features

- Distinguish the origin of the pub package @dd-jy (#238)

---

## v4.1.5 (06/01/2025)
## Changes
## 🐛 Hotfixes

- Fix the pub result parsing bug @dd-jy (#237)

---

## v4.1.4 (09/12/2024)
## Changes
## 🐛 Hotfixes

- Fix the bug @dd-jy (#236)

---

## v4.1.3 (05/12/2024)
## Changes
## 🚀 Features

- Support cycloneDX format @dd-jy (#235)

## 🔧 Maintenance

- Fix -m option, notice screen, dinamic graph size, case insensitive @ethanleelge (#234)
- Change cover sheet fail str @dd-jy (#231)
- test/golang: Added Golang test code and test case. @rewrite0w0 (#229)

---

## v4.1.2 (30/10/2024)
## Changes
## 🚀 Features

- Support cargo package manager @dd-jy (#230)

## 🔧 Maintenance

- Print option name with error msg @bjk7119 (#228)

---

## v4.1.1 (10/10/2024)
## Changes
## 🔧 Maintenance

- Support swift package.resolved v3 @dd-jy (#227)

---

## v4.1.0 (08/10/2024)
## Changes
## 🔧 Maintenance

- Update spdx function @dd-jy (#226)
- Refactor existing tox test to pytest @YongGoose (#225)
- Fix tox version & delete tox-wheel @bjk7119 (#224)

---

## v4.0.0 (06/09/2024)
## Changes
## 🔧 Maintenance

- Refactoring OSS item @dd-jy (#213)

---

## v3.15.6 (28/08/2024)
## Changes
## 🚀 Features

- Add feature that save graph image @fhdufhdu (#214)

## 🐛 Hotfixes

- Fix the macos npm github action bug @dd-jy (#215)

## 🔧 Maintenance

- Limit installation to fosslight_util 1.4.* @soimkim (#223)
- Modify homepage to empty if it is external repo @dd-jy (#217)
- Add dummy in github action token @dd-jy (#216)

---

## v3.15.5 (24/07/2024)
## Changes
## 🚀 Features

- Enable multiple input for -f option @JustinWonjaePark (#210)

## 🔧 Maintenance

- Change pip to pypi in the help message @soimkim (#208)

---

## v3.15.4 (26/06/2024)
## Changes
## 🐛 Hotfixes

- Fix the pub encoding issue @dd-jy (#207)
- Fix the pub_deps.json parsing issue @dd-jy (#206)

---

## v3.15.3 (20/06/2024)
## Changes
## 🚀 Features

- Print external-index-url in comment @dd-jy (#205)

## 🐛 Hotfixes

- Change to print depends on with purl @dd-jy (#204)

---

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
