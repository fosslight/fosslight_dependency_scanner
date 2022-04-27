#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import json
import yaml
import re
import traceback
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager

logger = logging.getLogger(constant.LOGGER_NAME)

_spec_repos = 'SPEC REPOS'
_external_sources = 'EXTERNAL SOURCES'
_dependencies = 'DEPENDENCIES'
_source_type = ['git', 'http', 'svn', 'hg']


class Cocoapods(PackageManager):
    package_manager_name = const.COCOAPODS

    dn_url = 'https://cocoapods.org/'
    input_file_name = const.SUPPORT_PACKAE.get(package_manager_name)

    def __init__(self, input_dir, output_dir):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)
        self.append_input_package_list_file(self.input_file_name)

    def parse_oss_information(self, f_name):
        with open(f_name, 'r', encoding='utf8') as input_fp:
            podfile_yaml = yaml.load(input_fp, Loader=yaml.FullLoader)

        pod_in_sepc_list = []
        pod_not_in_spec_list = []
        spec_repo_list = []
        external_source_list = []
        comment = ''

        if _spec_repos in podfile_yaml:
            for spec_item_key in podfile_yaml[_spec_repos]:
                for spec_item in podfile_yaml[_spec_repos][spec_item_key]:
                    spec_repo_list.append(spec_item)
        if _external_sources in podfile_yaml:
            for external_sources_key in podfile_yaml[_external_sources]:
                external_source_list.append(external_sources_key)
                spec_repo_list.append(external_sources_key)
        if len(spec_repo_list) == 0:
            logger.error("Cannot fint SPEC REPOS or EXTERNAL SOURCES in Podfile.lock.")
            return ''

        for dep_key in podfile_yaml[_dependencies]:
            dep_key_re = re.findall(r'(^\S*)', dep_key)
            dep_name = dep_key_re[0]
            if '/' in dep_name:
                dep_name = dep_name.split('/')[0]
            self.direct_dep_list.append(dep_name)

        for pods_list in podfile_yaml['PODS']:
            if not isinstance(pods_list, str):
                for pods_list_key, pods_list_item in pods_list.items():
                    pod_in_sepc_list, spec_repo_list, pod_not_in_spec_list = \
                        compile_pods_item(pods_list_key, spec_repo_list, pod_in_sepc_list, pod_not_in_spec_list)
            else:
                pod_in_sepc_list, spec_repo_list, pod_not_in_spec_list = \
                    compile_pods_item(pods_list, spec_repo_list, pod_in_sepc_list, pod_not_in_spec_list)

        if len(spec_repo_list) != 0:
            for spec_in_item in spec_repo_list:
                spec_oss_name_adding_core = spec_in_item + "/Core"
                for pod_not_item in pod_not_in_spec_list:
                    if spec_oss_name_adding_core == pod_not_item[0]:
                        pod_in_sepc_list.append([spec_in_item, pod_not_item[1]])

        sheet_list = []

        for pod_oss in pod_in_sepc_list:
            try:
                if self.direct_dep:
                    if pod_oss[0] in self.direct_dep_list:
                        comment = 'direct'
                    else:
                        comment = 'transitive'
                if pod_oss[0] in external_source_list:
                    podspec_filename = pod_oss[0] + '.podspec.json'
                    spec_file_path = os.path.join("Pods", "Local Podspecs", podspec_filename)
                else:
                    search_oss_name = ""
                    for alphabet_oss in pod_oss[0]:
                        if not alphabet_oss.isalnum():
                            search_oss_name += f"\\\\{alphabet_oss}"
                        else:
                            search_oss_name += alphabet_oss

                    command = f"pod spec which --regex ^{search_oss_name}$"
                    spec_which = os.popen(command).readline()
                    if spec_which.startswith('[!]'):
                        logger.error(f"This command({command}) returns an error")
                        return ''

                    file_path = spec_which.rstrip().split(os.path.sep)
                    if file_path[0] == '':
                        file_path_without_version = os.path.join(os.sep, *file_path[:-2])
                    else:
                        file_path_without_version = os.path.join(*file_path[:-2])
                    spec_file_path = os.path.join(file_path_without_version, pod_oss[1], file_path[-1])

                oss_name, oss_version, license_name, dn_loc, homepage = self.get_oss_in_podspec(spec_file_path)

                sheet_list.append([const.SUPPORT_PACKAE.get(self.package_manager_name),
                                  oss_name, oss_version, license_name, dn_loc, homepage, '', '', comment])
            except Exception as e:
                logger.warning(f"It failed to get {pod_oss[0]}:{e}")
                logger.warning(traceback.format_exc())

        return sheet_list

    def get_oss_in_podspec(self, spec_file_path):
        with open(spec_file_path, 'r', encoding='utf8') as json_file:
            json_data = json.load(json_file)

            oss_origin_name = json_data['name']
            oss_name = f"{self.package_manager_name}:{oss_origin_name}"
            oss_version = json_data['version']
            homepage = f"{self.dn_url}pods/{oss_origin_name}"

            if not isinstance(json_data['license'], str):
                if 'type' in json_data['license']:
                    license_name = json_data['license']['type']
            else:
                license_name = json_data['license']

            license_name = license_name.replace(",", "")

            source_keys = [key for key in json_data['source']]
            for src_type_i in _source_type:
                if src_type_i in source_keys:
                    dn_loc = json_data['source'][src_type_i]
                    if dn_loc.endswith('.git'):
                        dn_loc = dn_loc[:-4]

        return oss_name, oss_version, license_name, dn_loc, homepage

    def parse_direct_dependencies(self):
        self.direct_dep = True


def compile_pods_item(pods_item, spec_repo_list, pod_in_sepc_list, pod_not_in_spec_list):
    pods_item_re = re.findall(r'(\S*)\s{1}\((.*)\)', pods_item)

    oss_name = pods_item_re[0][0]
    oss_version = pods_item_re[0][1]

    oss_info = []
    oss_info.append(oss_name)
    oss_info.append(oss_version)

    if oss_name in spec_repo_list:
        pod_in_sepc_list.append(oss_info)
        spec_repo_list.remove(oss_name)
    else:
        pod_not_in_spec_list.append(oss_info)

    return pod_in_sepc_list, spec_repo_list, pod_not_in_spec_list
