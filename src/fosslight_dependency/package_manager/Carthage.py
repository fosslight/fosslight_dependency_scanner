#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import logging
import re
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import connect_github
from fosslight_dependency._package_manager import get_github_license

logger = logging.getLogger(constant.LOGGER_NAME)


class Carthage(PackageManager):
    package_manager_name = const.CARTHAGE

    input_file_name = const.SUPPORT_PACKAE.get(package_manager_name)
    dn_url = "https://github.com/"

    def __init__(self, input_dir, output_dir, github_token):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)
        self.github_token = github_token
        self.append_input_package_list_file(self.input_file_name)

    def parse_oss_information(self, f_name):
        with open(f_name, 'r', encoding='utf8') as input_fp:
            sheet_list = []

            g = connect_github(self.github_token)

            for i, line in enumerate(input_fp.readlines()):

                re_result = re.findall(r'github[\s]\"(\S*)\"[\s]\"(\S*)\"', line)
                try:
                    github_repo = re_result[0][0]
                    oss_origin_name = github_repo.split('/')[1]
                    oss_name = self.package_manager_name + ":" + oss_origin_name
                    oss_version = re_result[0][1]
                    homepage = self.dn_url + github_repo
                    dn_loc = homepage

                    license_name = ''
                    license_name = get_github_license(g, github_repo, self.platform, self.license_scanner_bin)

                except Exception:
                    logger.error("It cannot find the github oss information. So skip it.")
                    break

                sheet_list.append([const.SUPPORT_PACKAE.get(self.package_manager_name),
                                  oss_name, oss_version, license_name, dn_loc, homepage, '', '', ''])

        return sheet_list
