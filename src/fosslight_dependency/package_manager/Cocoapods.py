#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import json
import yaml
import re
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager, get_url_to_purl
from fosslight_dependency.dependency_item import DependencyItem, change_dependson_to_purl
from fosslight_util.oss_item import OssItem

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

        spec_repo_list = []
        external_source_list = []

        if _spec_repos in podfile_yaml:
            for spec_item_key in podfile_yaml[_spec_repos]:
                for spec_item in podfile_yaml[_spec_repos][spec_item_key]:
                    spec_repo_list.append(spec_item)
        if _external_sources in podfile_yaml:
            for external_sources_key in podfile_yaml[_external_sources]:
                external_source_list.append(external_sources_key)
                spec_repo_list.append(external_sources_key)
        if len(spec_repo_list) == 0:
            logger.error("Cannot find SPEC REPOS or EXTERNAL SOURCES in Podfile.lock.")
            return ''

        for dep_key in podfile_yaml[_dependencies]:
            dep_key_re = re.findall(r'(^\S*)', dep_key)
            self.direct_dep_list.append(dep_key_re[0])

        pod_item_list = {}
        for pods_i in podfile_yaml['PODS']:
            if not isinstance(pods_i, str):
                for key, items in pods_i.items():
                    k_name, k_ver = get_pods_info(key)
                    pod_item_list[k_name] = k_ver
                    self.relation_tree[f'{k_name}({k_ver})'] = []
                    for item in items:
                        i_name, _ = get_pods_info(item)
                        self.relation_tree[f'{k_name}({k_ver})'].append(i_name)
            else:
                oss_name, oss_version = get_pods_info(pods_i)
                pod_item_list[oss_name] = oss_version

        for rel_key in self.relation_tree:
            try:
                tmp_item_list = []
                for ri in self.relation_tree[rel_key]:
                    ri_version = pod_item_list[ri]
                    tmp_item_list.append(f'{ri}({ri_version})')
                self.relation_tree[rel_key] = []
                self.relation_tree[rel_key].extend(tmp_item_list)
            except Exception as e:
                logger.warning(f'Fail to check packages of {rel_key}: {e}')
                if rel_key in self.relation_tree:
                    self.relation_tree[rel_key] = []

        purl_dict = {}
        for pod_oss_name_origin, pod_oss_version in pod_item_list.items():
            dep_item = DependencyItem()
            oss_item = OssItem()
            try:
                if self.direct_dep and (len(self.direct_dep_list) > 0):
                    if pod_oss_name_origin in self.direct_dep_list:
                        oss_item.comment = 'direct'
                    else:
                        oss_item.comment = 'transitive'
                    if f'{pod_oss_name_origin}({pod_oss_version})' in self.relation_tree:
                        dep_item.depends_on_raw = self.relation_tree[f'{pod_oss_name_origin}({pod_oss_version})']

                oss_item.name = f'{self.package_manager_name}:{pod_oss_name_origin}'
                pod_oss_name = pod_oss_name_origin
                oss_item.version = pod_oss_version
                if '/' in pod_oss_name_origin:
                    pod_oss_name = pod_oss_name_origin.split('/')[0]
                if pod_oss_name in external_source_list:
                    oss_item.name = pod_oss_name_origin
                    podspec_filename = pod_oss_name + '.podspec.json'
                    spec_file_path = os.path.join("Pods", "Local Podspecs", podspec_filename)
                else:
                    search_oss_name = ""
                    for alphabet_oss in pod_oss_name:
                        if not alphabet_oss.isalnum():
                            search_oss_name += f"\\\\{alphabet_oss}"
                        else:
                            search_oss_name += alphabet_oss

                    command = f"pod spec which --regex ^{search_oss_name}$"
                    spec_which = os.popen(command).readline()
                    if spec_which.startswith('[!]'):
                        logger.warning(f"This command({command}) returns an error")
                        continue

                    file_path = spec_which.rstrip().split(os.path.sep)
                    if file_path[0] == '':
                        file_path_without_version = os.path.join(os.sep, *file_path[:-2])
                    else:
                        file_path_without_version = os.path.join(*file_path[:-2])
                    spec_file_path = os.path.join(file_path_without_version, oss_item.version, file_path[-1])

                oss_name, oss_version, oss_item.license, oss_item.download_location, \
                    oss_item.homepage = self.get_oss_in_podspec(spec_file_path)
                dep_item.purl = get_url_to_purl(oss_item.homepage, self.package_manager_name, pod_oss_name_origin, oss_version)
                purl_dict[f'{pod_oss_name_origin}({oss_version})'] = dep_item.purl
                if pod_oss_name in external_source_list:
                    oss_item.homepage = ''
                if oss_name == '':
                    continue
                if oss_item.version != oss_version:
                    logger.warning(f'{pod_oss_name_origin} has different version({oss_item.version})\
                                   with spec version({oss_version})')
                dep_item.oss_items.append(oss_item)
                self.dep_items.append(dep_item)
            except Exception as e:
                logger.warning(f"Fail to get {pod_oss_name_origin}:{e}")
        if self.direct_dep:
            self.dep_items = change_dependson_to_purl(purl_dict, self.dep_items)

        return

    def get_oss_in_podspec(self, spec_file_path):
        oss_name = ''
        oss_version = ''
        license_name = ''
        dn_loc = ''
        homepage = ''
        try:
            with open(spec_file_path, 'r', encoding='utf8') as json_file:
                json_data = json.load(json_file)

                oss_origin_name = json_data['name']
                oss_name = f"{self.package_manager_name}:{oss_origin_name}"
                oss_version = json_data['version']
                homepage = f"{self.dn_url}pods/{oss_origin_name}"

                if 'license' in json_data:
                    if not isinstance(json_data['license'], str):
                        if 'type' in json_data['license']:
                            license_name = json_data['license']['type']
                    else:
                        license_name = json_data['license']
                else:
                    license_name = ''
                license_name = license_name.replace(",", "")

                source_keys = [key for key in json_data['source']]
                for src_type_i in _source_type:
                    if src_type_i in source_keys:
                        dn_loc = json_data['source'][src_type_i]
                        if dn_loc.endswith('.git'):
                            dn_loc = dn_loc[:-4]
        except Exception as e:
            logger.warning(f"Fail to get oss info in podspec:{e}")

        return oss_name, oss_version, license_name, dn_loc, homepage

    def parse_direct_dependencies(self):
        self.direct_dep = True


def get_pods_info(pods_item):
    pods_item_re = re.findall(r'(\S*)(?:\s{1}\((.*)\))?', pods_item)

    oss_name = pods_item_re[0][0]
    oss_version = pods_item_re[0][1]

    return oss_name, oss_version
