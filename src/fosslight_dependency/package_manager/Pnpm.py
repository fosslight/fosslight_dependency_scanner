#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2025 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import subprocess
import json
import shutil
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager, get_url_to_purl
from fosslight_dependency.dependency_item import DependencyItem, change_dependson_to_purl
from fosslight_dependency.package_manager.Npm import check_multi_license
from fosslight_util.oss_item import OssItem

logger = logging.getLogger(constant.LOGGER_NAME)
node_modules = 'node_modules'


class Pnpm(PackageManager):
    package_manager_name = const.PNPM

    dn_url = 'https://www.npmjs.com/package/'
    input_file_name = 'tmp_pnpm_license_output.json'
    flag_tmp_node_modules = False
    project_name_list = []
    pkg_list = {}

    def __init__(self, input_dir, output_dir):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)

    def __del__(self):
        if os.path.isfile(self.input_file_name):
            os.remove(self.input_file_name)
        if self.flag_tmp_node_modules:
            shutil.rmtree(node_modules, ignore_errors=True)

    def run_plugin(self):
        ret = True

        pnpm_install_cmd = 'pnpm install --prod --ignore-scripts --ignore-pnpmfile'
        if os.path.isdir(node_modules) != 1:
            logger.info(f"node_modules directory is not existed. So it executes '{pnpm_install_cmd}'.")
            self.flag_tmp_node_modules = True
            cmd_ret = subprocess.call(pnpm_install_cmd, shell=True)
            if cmd_ret != 0:
                logger.error(f"{pnpm_install_cmd} returns an error")
                ret = False
        if ret:
            project_cmd = 'pnpm ls -r --depth -1 -P --json'
            ret_txt = subprocess.check_output(project_cmd, text=True, shell=True)
            if ret_txt is not None:
                deps_l = json.loads(ret_txt)
                for items in deps_l:
                    self.project_name_list.append(items["name"])
        return ret

    def parse_direct_dependencies(self):
        if not self.direct_dep:
            return
        try:
            direct_cmd = 'pnpm ls -r --depth 0 -P --json'
            ret_txt = subprocess.check_output(direct_cmd, text=True, shell=True)
            if ret_txt is not None:
                deps_l = json.loads(ret_txt)
                for item in deps_l:
                    if 'dependencies' in item and isinstance(item['dependencies'], dict):
                        self.direct_dep_list.extend(item['dependencies'].keys())
            else:
                self.direct_dep = False
                logger.warning('Cannot print direct/transitive dependency')
        except Exception as e:
            logger.warning(f'Fail to print direct/transitive dependency: {e}')
            self.direct_dep = False
        if self.direct_dep:
            self.direct_dep_list = list(filter(lambda dep: dep not in self.project_name_list, self.direct_dep_list))

    def extract_dependencies(self, dependencies, purl_dict):
        dep_item_list = []
        for dep_name, dep_info in dependencies.items():
            if dep_name not in self.project_name_list:
                if dep_name in self.pkg_list.keys():
                    if dep_info.get('version') in self.pkg_list[dep_name]:
                        continue
                self.pkg_list.setdefault(dep_name, []).append(dep_info.get('version'))
                dep_item = DependencyItem()
                oss_item = OssItem()
                oss_item.name = f'npm:{dep_name}'
                oss_item.version = dep_info.get('version')

                license_name = dep_info.get('license')
                if license_name:
                    multi_license, license_comment, multi_flag = check_multi_license(license_name, '')
                    if multi_flag:
                        oss_item.comment = license_comment
                        license_name = multi_license
                    else:
                        license_name = license_name.replace(",", "")
                    oss_item.license = license_name

                oss_item.homepage = f'{self.dn_url}{dep_name}'
                oss_item.download_location = dep_info.get('repository')
                if oss_item.download_location:
                    if oss_item.download_location.endswith('.git'):
                        oss_item.download_location = oss_item.download_location[:-4]
                    if oss_item.download_location.startswith('git://'):
                        oss_item.download_location = 'https://' + oss_item.download_location[6:]
                    elif oss_item.download_location.startswith('git+https://'):
                        oss_item.download_location = 'https://' + oss_item.download_location[12:]
                    elif oss_item.download_location.startswith('git+ssh://git@'):
                        oss_item.download_location = 'https://' + oss_item.download_location[14:]
                else:
                    oss_item.download_location = f'{self.dn_url}{dep_name}/v/{oss_item.version}'

                dn_loc = f'{oss_item.homepage}/v/{oss_item.version}'
                dep_item.purl = get_url_to_purl(dn_loc, 'npm')
                purl_dict[f'{dep_name}({oss_item.version})'] = dep_item.purl

                if dep_name in self.direct_dep_list:
                    oss_item.comment = 'direct'
                else:
                    oss_item.comment = 'transitive'

                if 'dependencies' in dep_info:
                    for dn, di in dep_info.get('dependencies').items():
                        if dn not in self.project_name_list:
                            dep_item.depends_on_raw.append(f"{dn}({di['version']})")

                dep_item.oss_items.append(oss_item)
                dep_item_list.append(dep_item)

            if 'dependencies' in dep_info:
                dep_item_list_inner, purl_dict_inner = self.extract_dependencies(dep_info['dependencies'], purl_dict)
                dep_item_list.extend(dep_item_list_inner)
                purl_dict.update(purl_dict_inner)

        return dep_item_list, purl_dict

    def parse_oss_information_for_pnpm(self):
        project_cmd = 'pnpm ls --json -r --depth Infinity -P --long'
        ret_txt = subprocess.check_output(project_cmd, text=True, shell=True)
        if ret_txt is not None:
            deps_l = json.loads(ret_txt)
            purl_dict = {}
            for items in deps_l:
                if 'dependencies' in items:
                    dep_item_list_inner, purl_dict_inner = self.extract_dependencies(items['dependencies'], purl_dict)
                    self.dep_items.extend(dep_item_list_inner)
                    purl_dict.update(purl_dict_inner)
            if self.direct_dep:
                self.dep_items = change_dependson_to_purl(purl_dict, self.dep_items)
        else:
            logger.warning(f'No output for {project_cmd}')
