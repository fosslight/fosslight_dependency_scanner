#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import json
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import connect_github
from fosslight_dependency._package_manager import get_github_license

logger = logging.getLogger(constant.LOGGER_NAME)


class Swift(PackageManager):
    package_manager_name = const.SWIFT

    input_file_name = const.SUPPORT_PACKAE.get(package_manager_name)

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

            sheet_list.append([const.SUPPORT_PACKAE.get(self.package_manager_name),
                              oss_name, oss_version, license_name, dn_loc, homepage, '', '', ''])

        return sheet_list
