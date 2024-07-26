#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import json
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import version_refine, get_url_to_purl
from fosslight_dependency.dependency_item import DependencyItem, change_dependson_to_purl
from fosslight_util.oss_item import OssItem

logger = logging.getLogger(constant.LOGGER_NAME)


class Gradle(PackageManager):
    package_manager_name = const.GRADLE

    dn_url = 'https://mvnrepository.com/artifact/'
    input_file_name = os.path.join('build', 'reports', 'license', 'dependency-license.json')

    def __init__(self, input_dir, output_dir, output_custom_dir):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)

        if output_custom_dir:
            self.output_custom_dir = output_custom_dir
            self.input_file_name = os.path.join(output_custom_dir, os.sep.join(self.input_file_name.split(os.sep)[1:]))

        self.append_input_package_list_file(self.input_file_name)

    def parse_oss_information(self, f_name):
        with open(f_name, 'r', encoding='utf8') as json_file:
            json_data = json.load(json_file)

        purl_dict = {}

        for d in json_data['dependencies']:
            dep_item = DependencyItem()
            oss_item = OssItem()
            used_filename = False
            group_id = ""
            artifact_id = ""

            name = d['name']
            filename = d['file']

            if name != filename:
                group_id, artifact_id, oss_ini_version = parse_oss_name_version_in_artifactid(name)
                oss_name = f"{group_id}:{artifact_id}"
            else:
                oss_name, oss_ini_version = parse_oss_name_version_in_filename(filename)
                used_filename = True
            oss_item.name = oss_name
            dep_key = f"{oss_item.name}({oss_ini_version})"
            if self.total_dep_list:
                if dep_key not in self.total_dep_list:
                    continue

            oss_item.version = version_refine(oss_ini_version)

            try:
                license_names = []
                for licenses in d['licenses']:
                    if licenses['name'] != '':
                        license_names.append(licenses['name'].replace(",", ""))
                oss_item.license = ', '.join(license_names)
            except Exception:
                logger.info("Cannot find the license name")

            if used_filename or group_id == "":
                oss_item.download_location = 'Unknown'
            else:
                oss_item.download_location = f"{self.dn_url}{group_id}/{artifact_id}/{oss_ini_version}"
                oss_item.homepage = f"{self.dn_url}{group_id}/{artifact_id}"
                dep_item.purl = get_url_to_purl(oss_item.download_location, 'maven')
                purl_dict[f'{oss_item.name}({oss_ini_version})'] = dep_item.purl

            if self.direct_dep:
                if len(self.direct_dep_list) > 0:
                    if dep_key in self.direct_dep_list:
                        oss_item.comment = 'direct'
                    else:
                        oss_item.comment = 'transitive'
                try:
                    if dep_key in self.relation_tree:
                        dep_item.depends_on_raw = self.relation_tree[dep_key]
                except Exception as e:
                    logger.error(f"Fail to find oss scope in dependency tree: {e}")

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
