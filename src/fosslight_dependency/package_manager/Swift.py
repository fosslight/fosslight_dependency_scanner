#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import json
import subprocess
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import connect_github, get_github_license
from fosslight_dependency._package_manager import get_url_to_purl
from fosslight_dependency.dependency_item import DependencyItem, change_dependson_to_purl
from fosslight_util.oss_item import OssItem

logger = logging.getLogger(constant.LOGGER_NAME)


class Swift(PackageManager):
    package_manager_name = const.SWIFT

    input_file_name = const.SUPPORT_PACKAE.get(package_manager_name)
    tmp_dep_tree_fname = 'show-dep.json'

    def __init__(self, input_dir, output_dir, github_token):
        super().__init__(self.package_manager_name, '', input_dir, output_dir)
        self.github_token = github_token

        self.check_input_file_path()
        self.append_input_package_list_file(self.input_file_name)

    def check_input_file_path(self):
        if not os.path.isfile(self.input_file_name):
            for file_in_swift in os.listdir("."):
                if file_in_swift.endswith(".xcodeproj"):
                    input_file_name_in_xcodeproj = os.path.join(file_in_swift,
                                                                "project.xcworkspace/xcshareddata/swiftpm",
                                                                self.input_file_name)
                    if input_file_name_in_xcodeproj != self.input_file_name:
                        if os.path.isfile(input_file_name_in_xcodeproj):
                            self.input_file_name = input_file_name_in_xcodeproj
                            logger.info(f"It uses the manifest file: {self.input_file_name}")

    def parse_direct_dependencies(self):
        ret = False
        if os.path.isfile('Package.swift') or os.path.isfile(self.tmp_dep_tree_fname):
            if not os.path.isfile(self.tmp_dep_tree_fname):
                cmd = "swift package show-dependencies --format json"
                try:
                    ret_txt = subprocess.check_output(cmd, text=True, shell=True)
                    if ret_txt is not None:
                        deps_l = json.loads(ret_txt)
                        ret = self.parse_dep_tree_json(deps_l)
                except Exception as e:
                    logger.warning(f'Fail to get swift dependency tree information: {e}')
            else:
                with open(self.tmp_dep_tree_fname) as f:
                    try:
                        deps_l = json.load(f)
                        ret = self.parse_dep_tree_json(deps_l)
                    except Exception as e:
                        logger.warning(f'Fail to load swift dependency tree json: {e}')
        else:
            logger.info(f"No Package.swift or {self.tmp_dep_tree_fname}, skip to print direct/transitive.")
        if not ret:
            self.direct_dep = False

    def get_dependencies(self, dependencies, package):
        package_name = 'name'
        deps = 'dependencies'
        version = 'version'

        pkg_name = package[package_name]
        pkg_ver = package[version]
        dependency_list = package[deps]
        dependencies[f"{pkg_name}({pkg_ver})"] = []
        for dependency in dependency_list:
            dep_name = dependency[package_name]
            dep_version = dependency[version]
            dependencies[f"{pkg_name}({pkg_ver})"].append(f"{dep_name}({dep_version})")
            if dependency[deps] != []:
                dependencies = self.get_dependencies(dependencies, dependency)
        return dependencies

    def parse_dep_tree_json(self, rel_json):
        ret = True
        try:
            for p in rel_json['dependencies']:
                self.direct_dep_list.append(p['name'])
                if p['dependencies'] == []:
                    continue
                self.relation_tree = self.get_dependencies(self.relation_tree, p)
        except Exception as e:
            logger.error(f'Failed to parse dependency tree: {e}')
            ret = False
        return ret

    def parse_oss_information(self, f_name):
        json_ver = 2
        purl_dict = {}

        with open(f_name, 'r', encoding='utf8') as json_file:
            json_raw = json.load(json_file)
            json_ver = json_raw['version']

            if json_ver == 1:
                json_data = json_raw["object"]["pins"]
            elif json_ver == 2 or json_ver == 3:
                json_data = json_raw["pins"]
            else:
                logger.warning(f'Not supported Package.resolved version {json_ver}')
                logger.warning('Try to parse as version 2(or 3)')
                json_data = json_raw["pins"]

        g = connect_github(self.github_token)

        for key in json_data:
            dep_item = DependencyItem()
            oss_item = OssItem()
            if json_ver == 1:
                oss_origin_name = key['package']
                oss_item.homepage = key['repositoryURL']
            else:
                oss_origin_name = key['identity']
                oss_item.homepage = key['location']

            if oss_item.homepage.endswith('.git'):
                oss_item.homepage = oss_item.homepage[:-4]

            oss_item.name = f"{self.package_manager_name}:{oss_origin_name}"

            oss_item.version = key['state'].get('version', None)
            if oss_item.version is None:
                oss_item.version = key['state'].get('revision', None)

            oss_item.download_location = oss_item.homepage

            github_repo = "/".join(oss_item.homepage.split('/')[-2:])
            dep_item.purl = get_url_to_purl(oss_item.download_location, self.package_manager_name, github_repo, oss_item.version)
            purl_dict[f'{oss_origin_name}({oss_item.version})'] = dep_item.purl
            oss_item.license = get_github_license(g, github_repo)

            if self.direct_dep and len(self.direct_dep_list) > 0:
                if oss_origin_name in self.direct_dep_list:
                    oss_item.comment = 'direct'
                else:
                    oss_item.comment = 'transitive'
                if f'{oss_origin_name}({oss_item.version})' in self.relation_tree:
                    dep_item.depends_on_raw = self.relation_tree[f'{oss_origin_name}({oss_item.version})']

            dep_item.oss_items.append(oss_item)
            self.dep_items.append(dep_item)

        if self.direct_dep:
            self.dep_items = change_dependson_to_purl(purl_dict, self.dep_items)

        return
