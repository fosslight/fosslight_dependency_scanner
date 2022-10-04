#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2022 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import logging
import re
import os
from xml.etree.ElementTree import parse
from xml.etree.ElementTree import fromstring
import json
import requests
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import check_and_run_license_scanner

logger = logging.getLogger(constant.LOGGER_NAME)


class Nuget(PackageManager):
    package_manager_name = const.NUGET

    dn_url = "https://nuget.org/packages/"
    packageReference = False
    nuget_api_url = 'https://api.nuget.org/v3-flatcontainer/'

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
            sheet_list = []
            package_list = []
            if self.packageReference:
                package_list = self.get_package_list_in_packages_assets(input_fp)
                self.get_direct_package_in_packagereference()
            else:
                package_list = self.get_package_list_in_packages_config(input_fp)

        for oss_origin_name, oss_version in package_list:
            try:
                oss_name = self.package_manager_name + ":" + oss_origin_name

                comment = []
                dn_loc = ''
                homepage = ''
                license_name = ''

                response = requests.get(f'{self.nuget_api_url}{oss_origin_name}/{oss_version}/{oss_origin_name}.nuspec')
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
                            comment.append(license_comment)
                    else:
                        license_url = nupkg_metadata.find(f'{xmlns}licenseUrl')
                        if license_url is not None:
                            url_res = requests.get(license_url.text)
                            if url_res.status_code == 200:
                                tmp_license_txt = open(tmp_license_txt_file_name, 'w', encoding='utf-8')
                                tmp_license_txt.write(url_res.text)
                                tmp_license_txt.close()
                                license_name_with_license_scanner = check_and_run_license_scanner(self.platform,
                                                                                                  self.license_scanner_bin,
                                                                                                  tmp_license_txt_file_name)
                                if license_name_with_license_scanner != "":
                                    license_name = license_name_with_license_scanner
                                else:
                                    license_name = license_url.text
                    repo_id = nupkg_metadata.find(f'{xmlns}repository')
                    if repo_id is not None:
                        dn_loc = repo_id.get("url")
                    else:
                        proj_url_id = nupkg_metadata.find(f'{xmlns}projectUrl')
                        if proj_url_id is not None:
                            dn_loc = proj_url_id.text
                    homepage = f'{self.dn_url}{oss_origin_name}'
                    if dn_loc == '':
                        dn_loc = f'{homepage}/{oss_version}'
                    else:
                        if dn_loc.endswith('.git'):
                            dn_loc = dn_loc[:-4]
                else:
                    comment.append('Fail to response for nuget api')

                if self.direct_dep and self.packageReference:
                    if oss_origin_name in self.direct_dep_list:
                        comment.append('direct')
                    else:
                        comment.append('transitive')

                sheet_list.append([','.join(self.input_package_list_file),
                                  oss_name, oss_version, license_name, dn_loc, homepage, '', '', ','.join(comment)])

            except Exception as e:
                logger.warning(f"Failed to parse oss information: {e}")

        if os.path.isfile(tmp_license_txt_file_name):
            os.remove(tmp_license_txt_file_name)

        return sheet_list

    def get_package_list_in_packages_config(self, input_fp):
        package_list = []
        root = parse(input_fp).getroot()
        for p in root.findall("package"):
            package_list.append([p.get("id"), p.get("version")])
        return package_list

    def get_package_list_in_packages_assets(self, input_fp):
        package_list = []
        json_f = json.load(input_fp)
        for item in json_f['libraries']:
            if json_f['libraries'][item]['type'] == 'package':
                oss_info = item.split('/')
                package_list.append([oss_info[0], oss_info[1]])
        return package_list

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
