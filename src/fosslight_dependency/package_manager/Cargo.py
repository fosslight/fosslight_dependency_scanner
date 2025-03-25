#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import json
import re
import subprocess
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import get_url_to_purl
from fosslight_dependency.dependency_item import DependencyItem, change_dependson_to_purl
from fosslight_util.oss_item import OssItem
logger = logging.getLogger(constant.LOGGER_NAME)


class Cargo(PackageManager):
    package_manager_name = const.CARGO

    dn_url = 'https://crates.io/crates/'
    input_file_name = 'tmp_cargo_fosslight_output.json'
    tmp_input_file_flag = False
    cur_path = ''
    cargo_lock_f = 'Cargo.lock'

    def __init__(self, input_dir, output_dir):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)
        self.append_input_package_list_file(self.input_file_name)

    def __del__(self):
        if self.tmp_input_file_flag:
            os.remove(self.input_file_name)

    def run_plugin(self):
        if os.path.exists(self.input_file_name):
            logger.info(f"Found {self.input_file_name}, skip the flutter cmd to analyze dependency.")
            return True

        if not os.path.exists(const.SUPPORT_PACKAE.get(self.package_manager_name)):
            logger.error(f"Cannot find the file({const.SUPPORT_PACKAE.get(self.package_manager_name)})")
            return False

        if os.path.exists(self.cargo_lock_f):
            cmd = f'cargo metadata --locked --format-version 1 > {self.input_file_name}'
        else:
            cmd = f'cargo metadata --format-version 1 > {self.input_file_name}'
        ret = subprocess.call(cmd, shell=True)
        if ret != 0:
            logger.error(f"Failed to run: {cmd}")
            os.chdir(self.cur_path)
            return False
        self.tmp_input_file_flag = True
        return True

    def parse_oss_information(self, f_name):
        json_data = ''

        with open(f_name, 'r', encoding='utf8') as cargo_file:
            json_f = json.load(cargo_file)
        try:
            purl_dict = {}
            workspace_members_key = 'workspace_members'
            resolve_key = 'resolve'
            root_key = 'root'
            nodes_key = 'nodes'
            workspace_members = []
            root = ''
            resolve_node = []

            if workspace_members_key in json_f:
                workspace_members = json_f[workspace_members_key]

            if resolve_key in json_f:
                if root_key in json_f[resolve_key]:
                    root = json_f[resolve_key][root_key]
                if nodes_key in json_f[resolve_key]:
                    resolve_node = json_f[resolve_key][nodes_key]
                if root and resolve_node:
                    self.direct_dep_list.extend(get_matched_dependencies(root, resolve_node))
            else:
                self.direct_dep = False
                logger.info('Cannot find dependencies relationship (no resolve nodes.)')

            for json_data in json_f['packages']:
                dep_item = DependencyItem()
                oss_item = OssItem()
                pkg_id = json_data['id']
                oss_origin_name = json_data['name']

                oss_item.name = f"{self.package_manager_name}:{oss_origin_name}"
                oss_item.version = json_data['version']
                oss_item.homepage = f"{self.dn_url}{oss_origin_name}"
                oss_item.download_location = json_data['repository']
                if oss_item.download_location is None:
                    oss_item.download_location = oss_item.homepage
                dep_item.purl = get_url_to_purl(oss_item.homepage, self.package_manager_name, oss_origin_name, oss_item.version)
                purl_dict[f'{oss_origin_name}({oss_item.version})'] = dep_item.purl
                if json_data['license'] is not None:
                    oss_item.license = json_data['license']

                if self.direct_dep:
                    if pkg_id == root:
                        oss_item.comment = 'root package'
                    if pkg_id in workspace_members:
                        oss_item.comment = 'local package'
                    if len(self.direct_dep_list) > 0:
                        if pkg_id != root:
                            if f'{oss_origin_name}({oss_item.version})' in self.direct_dep_list:
                                oss_item.comment = 'direct'
                            else:
                                oss_item.comment = 'transitive'
                    dep_item.depends_on_raw.extend(get_matched_dependencies(pkg_id, resolve_node))

                dep_item.oss_items.append(oss_item)
                self.dep_items.append(dep_item)
        except Exception as e:
            logger.error(f"Fail to parse pub oss information: {e}")
        if self.direct_dep:
            self.dep_items = change_dependson_to_purl(purl_dict, self.dep_items)

        return


def get_matched_dependencies(match_id, resolve_node):
    dependencies_list = []
    for node in resolve_node:
        if match_id == node['id']:
            for dep_pkg in node['dependencies']:
                try:
                    match = re.findall(r'^.*#(\S*)@(\S*)', dep_pkg)
                    dependencies_list.append(f'{match[0][0]}({match[0][1]})')
                except Exception:
                    try:
                        match = re.findall(r'^(\S*)\s(\S*)\s', dep_pkg)
                        dependencies_list.append(f'{match[0][0]}({match[0][1]})')
                    except Exception:
                        logger.info(f'cannot find name and version for dependencies: {match_id}')
                        pass
            break
    return dependencies_list
