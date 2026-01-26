# Changelog

## v4.1.31 (26/01/2026)
## Changes
## 🐛 Hotfixes

- Fix the yarn bug when it checks url exists @dd-jy (#285)

---

## v4.1.30 (23/01/2026)
## Changes
## 🔧 Maintenance

- Fix skipped path log not printed when all_mode @dd-jy (#283)

---

## v4.1.29 (23/01/2026)
## Changes
## 🔧 Maintenance

- Remove duplicated exclude logic for all mode @dd-jy (#282)

---

## v4.1.28 (16/01/2026)
## Changes
## 🔧 Maintenance

- Replace exclude function to fosslight_util @dd-jy (#281)

---

## v4.1.27 (14/01/2026)
## Changes
## 🚀 Features

- Run dotnet restore for all .sln and .csproj @dd-jy (#280)

---

## v4.1.26 (13/01/2026)
## Changes
## 🚀 Features

- Add auto-restore for Nuget CPM projects @dd-jy (#279)
- Add dotnet restore cmd when analyzing nuget @dd-jy (#275)
- Refine npm/yarn dn urls via registry lookup @dd-jy (#278)

## 🐛 Hotfixes

- Fix maven direct/transitive bug @dd-jy (#277)
- Fix to detect manifest file when path included @dd-jy (#273)

## 🔧 Maintenance

- Add how to use -e option @bjk7119 (#276)
- Modify comment in scanner info sheet @dd-jy (#274)

---

## v4.1.25 (24/12/2025)
## Changes
## 🔧 Maintenance

- Update supported format @dd-jy (#272)

---

## v4.1.24 (12/12/2025)
## Changes
## 🔧 Maintenance

- Add to get license from pom additionally @dd-jy (#271)

---

## v4.1.23 (12/11/2025)
## Changes
## 🐛 Hotfixes

- Distinguish flutter sdk in package list @dd-jy (#270)

---

## v4.1.22 (16/10/2025)
## Changes
## 🚀 Features

- Support yarn dependency tree @dd-jy (#268)

## 🔧 Maintenance

- Remove wheel pkg in pypi oss list @dd-jy (#269)

---

## v4.1.21 (23/09/2025)
## Changes
## 🚀 Features

- Try to install with yarn if npm failed @soimkim (#267)

---

## v4.1.20 (02/09/2025)
## Changes
## 🚀 Features

- Support recursive dependency analysis @dd-jy (#264)
- Update to use pip inspect to get pypi oss info @dd-jy (#263)

## 🐛 Hotfixes

- Fix the android detect mode bug @dd-jy (#266)

---

## v4.1.19 (17/07/2025)
## Changes
## 🔧 Maintenance

- Update python support ver 3.10-3.12 @dd-jy (#262)

---

## v4.1.18 (11/07/2025)
## Changes
## 🔧 Maintenance

- Remove the pkg_resources @dd-jy (#261)

---

## v4.1.17 (09/07/2025)
## Changes
## 🐛 Hotfixes

- Fix the cargo purl bug @dd-jy (#260)

## 🔧 Maintenance

- Change cargo dn loc with crates.io url @dd-jy (#259)

---

## v4.1.16 (01/07/2025)
## Changes
## 🐛 Hotfixes

- Fix nuget api call error @dd-jy (#258)

---

## v4.1.15 (26/06/2025)
## Changes
## 🔧 Maintenance

- Add comment if no manifest but package manager found @dd-jy (#257)

---

## v4.1.14 (12/06/2025)
## Changes
## 🔧 Maintenance

- Add oss version in npm download location @dd-jy (#256)
- Switch download location and homepage for go @dd-jy (#255)

---

## v4.1.13 (09/06/2025)
## Changes
## 🐛 Hotfixes

- Retry to get go pkg info when http error @dd-jy (#254)

## 🔧 Maintenance

- Change dn loc and homepage for Npm @dd-jy (#251)

---

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
