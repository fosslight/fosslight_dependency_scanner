#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2024 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import re
import yaml
import requests
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import check_license_name, get_url_to_purl
from fosslight_dependency.dependency_item import DependencyItem
from fosslight_util.oss_item import OssItem

logger = logging.getLogger(constant.LOGGER_NAME)
proprietary_license = 'Proprietary License'
license_md = 'LICENSE.md'
third_party_md = 'Third Party Notices.md'


class Unity(PackageManager):
    package_manager_name = const.UNITY

    input_file_name = const.SUPPORT_PACKAE.get(package_manager_name)
    packageCache_dir = os.path.join('Library', 'PackageCache')
    mirror_url = 'https://github.com/needle-mirror/'
    unity_internal_url = 'https://github.cds.internal.unity3d.com'
    third_notice_txt = 'third_party_notice.txt'

    def __init__(self, input_dir, output_dir):
        super().__init__(self.package_manager_name, '', input_dir, output_dir)
        self.append_input_package_list_file(self.input_file_name)

    def parse_oss_information(self, f_name):
        with open(f_name, 'r', encoding='utf8') as f:
            f_yml = yaml.safe_load(f)
            resolvedPkg = f_yml['m_ResolvedPackages']

        try:
            for pkg_data in resolvedPkg:
                dep_item = DependencyItem()
                oss_item = OssItem()
                oss_item.name = pkg_data['name']
                oss_item.version = pkg_data['version']

                oss_packagecache_dir = os.path.join(self.packageCache_dir, f'{oss_item.name}@{oss_item.version}')
                license_f = os.path.join(oss_packagecache_dir, license_md)
                if os.path.isfile(license_f):
                    license_name = check_license_name(license_f, True)
                    if license_name == '':
                        with open(license_f, 'r', encoding='utf-8') as f:
                            for line in f:
                                matched_l = re.search(r'Unity\s[\s\w]*\sLicense', line)
                                if matched_l:
                                    license_name = matched_l[0]
                                    break
                else:
                    license_name = proprietary_license
                oss_item.license = license_name

                third_f = os.path.join(oss_packagecache_dir, third_party_md)
                if os.path.isfile(third_f):
                    with open(third_f, 'r', encoding='utf-8') as f:
                        third_notice = f.readlines()
                    with open(self.third_notice_txt, 'a+', encoding='utf-8') as tf:
                        for line in third_notice:
                            tf.write(line)
                            tf.flush()

                oss_item.homepage = pkg_data['repository']['url']
                if oss_item.homepage and oss_item.homepage.startswith('git@'):
                    oss_item.homepage = oss_item.homepage.replace('git@', 'https://')
                if oss_item.homepage is None or oss_item.homepage.startswith(self.unity_internal_url):
                    if (license_name != proprietary_license) and license_name != '':
                        oss_item.homepage = f'{self.mirror_url}{oss_item.name}'
                if oss_item.homepage is None:
                    oss_item.homepage = ''
                else:
                    if not check_url_alive(oss_item.homepage):
                        minor_version = '.'.join(oss_item.version.split('.')[0:2])
                        oss_item.homepage = f'https://docs.unity3d.com/Packages/{oss_item.name}@{minor_version}'
                oss_item.download_location = oss_item.homepage
                dep_item.purl = get_url_to_purl(oss_item.download_location, self.package_manager_name)
                if dep_item.purl == 'None':
                    dep_item.purl = ''
                if dep_item.purl != '':
                    dep_item.purl = f'{dep_item.purl}@{oss_item.version}'

                comment_list = []
                if self.direct_dep:
                    if pkg_data['isDirectDependency']:
                        comment_list.append('direct')
                    else:
                        comment_list.append('transitive')

                oss_item.comment = ','.join(comment_list)
                dep_item.oss_items.append(oss_item)
                self.dep_items.append(dep_item)
        except Exception as e:
            logger.error(f"Fail to parse unity oss information: {e}")

        return


def check_url_alive(url):
    alive = False
    try:
        response = requests.get(url)
        if response.status_code == 200:
            alive = True
        else:
            logger.debug(f"{url} returned status code {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.debug(f"Check if url({url})is alive err: {e}")
    return alive
