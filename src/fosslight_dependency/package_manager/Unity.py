#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2024 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import re
import yaml
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import check_and_run_license_scanner, get_url_to_purl

logger = logging.getLogger(constant.LOGGER_NAME)
proprietary_license = 'Proprietary License'
unclassifed_license = 'UnclassifiedLicense'
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
        comment = ''

        with open(f_name, 'r', encoding='utf8') as f:
            f_yml = yaml.safe_load(f)
            resolvedPkg = f_yml['m_ResolvedPackages']

        try:
            sheet_list = []

            for pkg_data in resolvedPkg:
                oss_name = pkg_data['name']
                oss_version = pkg_data['version']

                oss_packagecache_dir = os.path.join(self.packageCache_dir, f'{oss_name}@{oss_version}')
                license_f = os.path.join(oss_packagecache_dir, license_md)
                if os.path.isfile(license_f):
                    license_name = check_and_run_license_scanner(self.platform,
                                                                 self.license_scanner_bin,
                                                                 license_f)
                    if license_name == unclassifed_license or license_name == '':
                        with open(license_f, 'r', encoding='utf-8') as f:
                            for line in f:
                                matched_l = re.search(r'Unity\s[\s\w]*\sLicense', line)
                                if matched_l:
                                    license_name = matched_l[0]
                                    break
                else:
                    license_name = proprietary_license

                third_f = os.path.join(oss_packagecache_dir, third_party_md)
                if os.path.isfile(third_f):
                    with open(third_f, 'r', encoding='utf-8') as f:
                        third_notice = f.readlines()
                    with open(self.third_notice_txt, 'a+', encoding='utf-8') as tf:
                        for line in third_notice:
                            tf.write(line)
                            tf.flush()

                homepage = pkg_data['repository']['url']
                if homepage and homepage.startswith('git@'):
                    homepage = homepage.replace('git@', 'https://')
                if homepage is None or homepage.startswith(self.unity_internal_url):
                    if license_name != proprietary_license:
                        homepage = f'{self.mirror_url}{oss_name}'
                if homepage is None:
                    homepage = ''

                dn_loc = homepage
                purl = get_url_to_purl(dn_loc, self.package_manager_name)
                if purl == 'None':
                    purl = ''
                if purl != '':
                    purl = f'{purl}@{oss_version}'

                comment_list = []
                if self.direct_dep:
                    if pkg_data['isDirectDependency']:
                        comment_list.append('direct')
                    else:
                        comment_list.append('transitive')

                comment = ','.join(comment_list)
                sheet_list.append([purl, oss_name, oss_version, license_name, dn_loc, homepage,
                                  '', '', comment, ''])
        except Exception as e:
            logger.error(f"Fail to parse unity oss information: {e}")

        return sheet_list
