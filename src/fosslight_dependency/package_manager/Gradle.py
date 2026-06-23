#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import json
import re
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import version_refine, get_url_to_purl
from fosslight_dependency._package_manager import collect_gradle_download_urls, get_download_location
from fosslight_dependency.dependency_item import DependencyItem, change_dependson_to_purl
from fosslight_util.get_pom_license import get_license_from_pom
from fosslight_util.oss_item import OssItem

logger = logging.getLogger(constant.LOGGER_NAME)


class Gradle(PackageManager):
    package_manager_name = const.GRADLE

    dn_url = 'https://mvnrepository.com/artifact/'
    input_file_name = os.path.join('build', 'reports', 'license', 'dependency-license.json')

    def __init__(self, input_dir, output_dir, output_custom_dir):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)
        self.download_url_map = {}

        if output_custom_dir:
            self.output_custom_dir = output_custom_dir
            self.input_file_name = os.path.join(output_custom_dir, os.sep.join(self.input_file_name.split(os.sep)[1:]))

        self.append_input_package_list_file(self.input_file_name)

    def parse_oss_information(self, f_name):
        with open(f_name, 'r', encoding='utf8') as json_file:
            json_data = json.load(json_file)

        purl_dict = {}
        if isinstance(json_data, list):
            dependencies = json_data
            json_format = "list"
        else:
            dependencies = json_data.get("dependencies", [])
            json_format = "dict"

        for d in dependencies:
            dep_item = DependencyItem()
            oss_item = OssItem()

            module_name = d.get("moduleName", "")
            module_version = d.get("moduleVersion", "")
            module_urls = d.get("moduleUrls", [])
            if isinstance(module_urls, str):
                module_urls = [module_urls]
            module_url = next((u for u in module_urls if u), d.get("moduleUrl", ""))

            if json_format == "list":
                module_licenses_raw = d.get("moduleLicenses", [])
                license_names = []
                for lic in module_licenses_raw:
                    lic_name = lic.get("name") or ""
                    final_license_name = normalize_license_name_from_name(lic_name) if lic_name else None
                    if final_license_name:
                        license_names.append(final_license_name)
                license_names = list(dict.fromkeys(license_names))
                module_license = ", ".join(license_names)
            else:
                module_license = d.get("moduleLicense", "")

            group_id = ""
            artifact_id = ""

            if ":" in module_name:
                parts = module_name.split(":")
                group_id = parts[0]
                artifact_id = parts[1]
                oss_name = f"{group_id}:{artifact_id}"
            else:
                oss_name = module_name

            oss_item.name = oss_name
            oss_ini_version = module_version
            dep_key = f"{oss_item.name}({oss_ini_version})"

            if self.total_dep_list:
                if dep_key not in self.total_dep_list:
                    continue

            oss_item.version = version_refine(oss_ini_version)

            if module_license and module_license.strip():
                oss_item.license = module_license.strip()
            else:
                oss_item.license = ""

            is_gradle_plugin = (
                group_id.startswith('gradle.plugin.')
                or artifact_id.endswith('.gradle.plugin')
                or group_id == 'com.github.jk1'
            )
            if not oss_item.license and group_id and artifact_id and oss_ini_version and not is_gradle_plugin:
                license_names = get_license_from_pom(
                    group_id,
                    artifact_id,
                    oss_ini_version
                )

                if license_names:
                    oss_item.license = license_names

            if not self.download_url_map:
                self.download_url_map = collect_gradle_download_urls(
                    self.input_dir,
                    self.package_manager_name
                )

            # download location / homepage / purl
            if group_id:
                oss_item.download_location = get_download_location(
                    self.download_url_map,
                    group_id,
                    artifact_id,
                    oss_ini_version,
                    self.dn_url
                )

                if module_url:
                    oss_item.homepage = module_url
                else:
                    oss_item.homepage = f"{self.dn_url}{group_id}/{artifact_id}"

                mvn_dn_url = f"{self.dn_url}{group_id}/{artifact_id}/{oss_ini_version}"
                dep_item.purl = get_url_to_purl(mvn_dn_url, "maven")

                purl_dict[dep_key] = dep_item.purl
            else:
                oss_item.download_location = "Unknown"

            if self.direct_dep:
                if self.direct_dep_list:
                    if dep_key in self.direct_dep_list:
                        oss_item.comment = "direct"
                    else:
                        oss_item.comment = "transitive"

                try:
                    if dep_key in self.relation_tree:
                        dep_item.depends_on_raw = self.relation_tree[dep_key]
                except Exception as e:
                    logger.error(f"Fail to find dependency tree: {e}")

            dep_item.oss_items.append(oss_item)
            self.dep_items.append(dep_item)

        if self.direct_dep:
            self.dep_items = change_dependson_to_purl(purl_dict, self.dep_items)

        return


def parse_oss_name_version_in_filename(name):
    filename = name.rstrip('.jar')
    split_name = filename.rpartition('-')

    oss_name = split_name[0]
    oss_version = split_name[2]

    return oss_name, oss_version


def parse_oss_name_version_in_artifactid(name):
    artifact_comp = name.split(':')

    group_id = artifact_comp[0]
    artifact_id = artifact_comp[1]
    oss_version = artifact_comp[2]

    return group_id, artifact_id, oss_version


def normalize_license_name_from_name(license_name):
    if license_name is None:
        return None

    license_name = license_name.strip()

    if ";link=" in license_name:
        license_name = license_name.split(";link=", 1)[0]

    license_name = license_name.strip().strip('"').strip("'").strip()
    license_name = re.sub(r'^[#\s\-\*]+|[#\s\-\*]+$', '', license_name)

    if not license_name:
        return None

    lowered = license_name.lower()

    dual_keywords = [
        "dual", "multi", " or ", " and ", " with ", " + ", " ; "
    ]

    if any(keyword in lowered for keyword in dual_keywords):
        if "common development and distribution license (cddl) version 1.0" in lowered:
            return sanitize_license_name("CDDL-1.0")
        return sanitize_license_name(license_name)

    formal_rules = [
        ("Apache-1.0", r"\bapache\b.*1\.0"),
        ("Apache-1.1", r"\bapache\b.*1\.1"),
        ("Apache-2.0", r"asl\s?2(\.0)?"),
        ("Apache-2.0", r"\bapache\b.*2(\.0)?"),
        ("MIT-0", r"mit no attribution"),
        ("MIT-0", r"mit[- ]?0"),
        ("MIT", r"(the\s)?mit(\slicen[cs]e)?(\s\(mit\))?"),
        ("BSD-2-Clause", r"bsd[- ]?2[- ]clause"),
        ("BSD-3-Clause", r"bsd[- ]?3[- ]clause"),
        ("BSD-3-Clause", r"(the\s)?new bsd license"),
        ("BSD-3-Clause", r"modified bsd license"),
        ("EPL-1.0", r"eclipse publi(c|sh) license.*1"),
        ("EPL-2.0", r"eclipse public license.*2"),
        ("GPL-1.0-only", r"\bgpl\b.*1(\.0)?"),
        ("GPL-2.0-only", r"\bgpl\b.*2(\.0)?"),
        ("GPL-3.0-only", r"\bgpl\b.*3(\.0)?"),
        ("AGPL-3.0-only", r"\bagpl\b.*3(\.0)?"),
        ("LGPL-2.1-only", r"\blgpl\b.*2\.1"),
        ("LGPL-3.0-only", r"\blgpl\b.*3(\.0)?"),
        ("MPL-1.1", r"mozilla public license.*1\.1"),
        ("MPL-2.0", r"mozilla public license.*2(\.0)?"),
        ("CDDL-1.0", r"cddl.*1\.0"),
        ("CDDL-1.1", r"cddl.*1\.1"),
        ("CPL-1.0", r"common public license.*1"),
        ("CC0-1.0", r"cc0([- ]1(\.0)?)?"),
        ("Public-Domain", r"public\sdomain"),
    ]

    for normalized_name, re_pattern in formal_rules:
        if re.search(re_pattern, lowered, re.IGNORECASE):
            return sanitize_license_name(normalized_name)

    return sanitize_license_name(license_name)


def sanitize_license_name(license_name):
    if not license_name:
        return None

    license_name = re.sub(r'\s*,\s*', ' ', license_name)
    license_name = re.sub(r'\s+', ' ', license_name).strip()

    return license_name or None
