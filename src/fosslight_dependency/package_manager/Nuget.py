#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2022 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import logging
import re
import os
from defusedxml.ElementTree import parse, fromstring
import json
import requests
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import check_license_name, get_url_to_purl
from fosslight_dependency.dependency_item import DependencyItem, change_dependson_to_purl
from fosslight_util.oss_item import OssItem

logger = logging.getLogger(constant.LOGGER_NAME)


class Nuget(PackageManager):
    package_manager_name = const.NUGET

    dn_url = "https://nuget.org/packages/"
    packageReference = False
    nuget_api_url = 'https://api.nuget.org/v3-flatcontainer/'
    dotnet_ver = []

    def __init__(self, input_dir, output_dir):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)

        for manifest_i in const.SUPPORT_PACKAE.get(self.package_manager_name):
            if os.path.isfile(manifest_i):
                self.append_input_package_list_file(manifest_i)
                if manifest_i != 'packages.config':
                    self.packageReference = True

    def parse_oss_information(self, f_name):
        tmp_license_txt_file_name = 'tmp_license.txt'
        with open(f_name, 'r', encoding='utf8') as input_fp:
            purl_dict = {}
            package_list = []
            if self.packageReference:
                package_list = self.get_package_info_in_packagereference(input_fp)
            else:
                package_list = self.get_package_list_in_packages_config(input_fp)

        for oss_origin_name, oss_version in package_list:
            try:
                dep_item = DependencyItem()
                oss_item = OssItem()
                oss_item.name = f'{self.package_manager_name}:{oss_origin_name}'
                oss_item.version = oss_version

                license_name = ''
                response = requests.get(f'{self.nuget_api_url.lower()}{oss_origin_name.lower()}/'
                                        f'{oss_item.version.lower()}/{oss_origin_name.lower()}.nuspec')
                if response.status_code == 200:
                    root = fromstring(response.text)
                    xmlns = ''
                    m = re.search('{.*}', root.tag)
                    if m:
                        xmlns = m.group(0)
                    nupkg_metadata = root.find(f'{xmlns}metadata')

                    license_name_id = nupkg_metadata.find(f'{xmlns}license')
                    if license_name_id is not None:
                        license_name, license_comment = self.check_multi_license(license_name_id.text)
                        if license_comment != '':
                            oss_item.comment = license_comment
                    else:
                        license_url = nupkg_metadata.find(f'{xmlns}licenseUrl')
                        if license_url is not None:
                            url_res = requests.get(license_url.text)
                            if url_res.status_code == 200:
                                license_name_with_scanner = check_license_name(url_res.text)
                                if license_name_with_scanner != "":
                                    license_name = license_name_with_scanner
                                else:
                                    license_name = license_url.text
                    oss_item.license = license_name
                    repo_id = nupkg_metadata.find(f'{xmlns}repository')
                    if repo_id is not None:
                        oss_item.download_location = repo_id.get("url")
                    else:
                        proj_url_id = nupkg_metadata.find(f'{xmlns}projectUrl')
                        if proj_url_id is not None:
                            oss_item.download_location = proj_url_id.text
                    oss_item.homepage = f'{self.dn_url}{oss_origin_name}'
                    if oss_item.download_location == '':
                        oss_item.download_location = f'{oss_item.homepage}/{oss_item.version}'
                    else:
                        if oss_item.download_location.endswith('.git'):
                            oss_item.download_location = oss_item.download_location[:-4]
                    dep_item.purl = get_url_to_purl(f'{oss_item.homepage}/{oss_item.version}', self.package_manager_name)
                else:
                    oss_item.comment = 'Fail to response for nuget api'
                    dep_item.purl = f'pkg:nuget/{oss_origin_name}@{oss_item.version}'
                purl_dict[f'{oss_origin_name}({oss_item.version})'] = dep_item.purl

                if self.direct_dep and self.packageReference:
                    if oss_origin_name in self.direct_dep_list:
                        oss_item.comment = 'direct'
                    else:
                        oss_item.comment = 'transitive'

                    if f'{oss_origin_name}({oss_item.version})' in self.relation_tree:
                        dep_item.depends_on_raw = self.relation_tree[f'{oss_origin_name}({oss_item.version})']

                dep_item.oss_items.append(oss_item)
                self.dep_items.append(dep_item)

            except Exception as e:
                logger.warning(f"Failed to parse oss information: {e}")
        if self.direct_dep:
            self.dep_items = change_dependson_to_purl(purl_dict, self.dep_items)

        if os.path.isfile(tmp_license_txt_file_name):
            os.remove(tmp_license_txt_file_name)

        return

    def get_package_list_in_packages_config(self, input_fp):
        package_list = []
        root = parse(input_fp).getroot()
        for p in root.findall("package"):
            package_list.append([p.get("id"), p.get("version")])
        return package_list

    def get_package_info_in_packagereference(self, input_fp):
        json_f = json.load(input_fp)

        self.get_dotnet_ver_list(json_f)
        package_list = self.get_package_list_in_packages_assets(json_f)
        self.get_dependency_tree(json_f)
        self.get_direct_package_in_packagereference()

        return package_list

    def get_package_list_in_packages_assets(self, json_f):
        package_list = []
        for item in json_f['libraries']:
            if json_f['libraries'][item]['type'] == 'package':
                oss_info = item.split('/')
                package_list.append([oss_info[0], oss_info[1]])
        return package_list

    def get_dotnet_ver_list(self, json_f):
        json_project_group = json_f['projectFileDependencyGroups']
        for dotnet_ver in json_project_group:
            self.dotnet_ver.append(dotnet_ver)

    def get_dependency_tree(self, json_f):
        json_target = json_f['targets']
        for item in json_target:
            if item not in self.dotnet_ver:
                continue
            json_item = json_target[item]
            for pkg in json_item:
                json_pkg = json_item[pkg]
                if 'type' not in json_pkg:
                    continue
                if 'dependencies' not in json_pkg:
                    continue
                if json_pkg['type'] != 'package':
                    continue
                oss_info = pkg.split('/')
                self.relation_tree[f'{oss_info[0]}({oss_info[1]})'] = []
                for dep in json_pkg['dependencies']:
                    oss_name = dep
                    oss_ver = json_pkg['dependencies'][dep]
                    self.relation_tree[f'{oss_info[0]}({oss_info[1]})'].append(f'{oss_name}({oss_ver})')

    def get_direct_package_in_packagereference(self):
        for f in os.listdir(self.input_dir):
            if os.path.isfile(f) and ((f.split('.')[-1] == 'csproj') or (f.split('.')[-1] == 'xproj')):
                with open(f, 'r', encoding='utf8') as input_fp:
                    root = parse(input_fp).getroot()
                itemgroups = root.findall('ItemGroup')
                for itemgroup in itemgroups:
                    for item in itemgroup.findall('PackageReference'):
                        self.direct_dep_list.append(item.get('Include'))

    def check_multi_license(self, license_name):
        multi_license = license_name
        license_comment = ''
        try:
            if license_name.startswith('(') and license_name.endswith(')'):
                license_name = license_name.lstrip('(').rstrip(')')
                license_comment = license_name
                multi_license = ','.join(re.split(r'OR|AND', license_name))
        except Exception as e:
            logger.warning(f'Fail to parse multi license in npm: {e}')

        return multi_license, license_comment
