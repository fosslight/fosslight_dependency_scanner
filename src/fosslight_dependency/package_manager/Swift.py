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
from fosslight_dependency._package_manager import connect_github
from fosslight_dependency._package_manager import get_github_license

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
        sheet_list = []
        json_ver = 1

        with open(f_name, 'r', encoding='utf8') as json_file:
            json_raw = json.load(json_file)
            json_ver = json_raw['version']

            if json_ver == 1:
                json_data = json_raw["object"]["pins"]
            elif json_ver == 2:
                json_data = json_raw["pins"]
            else:
                logger.error(f'Not supported Package.resolved version {json_ver}')
                return sheet_list

        g = connect_github(self.github_token)

        for key in json_data:
            if json_ver == 1:
                oss_origin_name = key['package']
                homepage = key['repositoryURL']
            elif json_ver == 2:
                oss_origin_name = key['identity']
                homepage = key['location']

            if homepage.endswith('.git'):
                homepage = homepage[:-4]

            oss_name = f"{self.package_manager_name}:{oss_origin_name}"

            oss_version = key['state'].get('version', None)
            if oss_version is None:
                oss_version = key['state'].get('revision', None)

            dn_loc = homepage
            license_name = ''

            github_repo = "/".join(homepage.split('/')[-2:])
            license_name = get_github_license(g, github_repo, self.platform, self.license_scanner_bin)

            comment_list = []
            deps_list = []
            if self.direct_dep and len(self.direct_dep_list) > 0:
                if oss_origin_name in self.direct_dep_list:
                    comment_list.append('direct')
                else:
                    comment_list.append('transitive')

                if f'{oss_origin_name}({oss_version})' in self.relation_tree:
                    rel_items = [f'{self.package_manager_name}:{ri}'
                                 for ri in self.relation_tree[f'{oss_origin_name}({oss_version})']]
                    deps_list.extend(rel_items)
            comment = ','.join(comment_list)
            deps = ','.join(deps_list)
            sheet_list.append([const.SUPPORT_PACKAE.get(self.package_manager_name),
                              oss_name, oss_version, license_name, dn_loc, homepage, '', '', comment, deps])

        return sheet_list
