#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import logging
import re
import os
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import connect_github
from fosslight_dependency._package_manager import get_github_license
from fosslight_dependency._package_manager import check_and_run_license_scanner

logger = logging.getLogger(constant.LOGGER_NAME)


checkout_dir = os.path.join("Carthage", 'Checkouts')
license_file_regs = ['licen[cs]e[s]?', 'notice[s]?', 'copying*', 'copyright[s]?',
                     'mit', 'bsd[-]?[0-4]?', 'bsd[-]?[0-4][-]?clause[s]?', 'apache[-,_]?[1-2]?[.,-,_]?[0-2]?',
                     'unlicen[cs]e', '[a,l]?gpl[-]?[1-3]?[.,-,_]?[0-1]?', 'legal']


class Carthage(PackageManager):
    package_manager_name = const.CARTHAGE

    input_file_name = const.SUPPORT_PACKAE.get(package_manager_name)
    dn_url = "https://github.com/"

    def __init__(self, input_dir, output_dir, github_token):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)
        self.github_token = github_token
        self.append_input_package_list_file(self.input_file_name)

    def parse_oss_information(self, f_name):
        github = "github"
        checkout_dir_list = get_checkout_dirname()
        comment = ''
        with open(f_name, 'r', encoding='utf8') as input_fp:
            sheet_list = []
            g = ''
            if not checkout_dir_list:
                g = connect_github(self.github_token)

            for i, line in enumerate(input_fp.readlines()):
                # Cartfile origin : github, git
                # Ref. https://github.com/Carthage/Carthage/blob/master/Documentation/Artifacts.md
                re_result = re.findall(r'(github|git)[\s]\"(\S*)\"[\s]\"(\S*)\"', line)
                try:
                    repo = re_result[0][0]
                    oss_path = re_result[0][1]
                    if oss_path.endswith('.git'):
                        oss_path = oss_path[:-4]
                    oss_origin_name = oss_path.split('/')[-1]
                    oss_name = self.package_manager_name + ":" + oss_origin_name

                    if repo == github:
                        homepage = self.dn_url + oss_path
                    else:
                        homepage = oss_path
                    dn_loc = homepage

                    oss_version = re_result[0][2]

                    license_name = ''
                    find_license = False
                    if oss_origin_name in checkout_dir_list:
                        oss_path_in_checkout = os.path.join(checkout_dir, oss_origin_name)
                        for filename_in_dir in os.listdir(oss_path_in_checkout):
                            if find_license:
                                break
                            filename_with_checkout_path = os.path.join(oss_path_in_checkout, filename_in_dir)
                            if os.path.isfile(filename_with_checkout_path):
                                for license_file_reg in license_file_regs:
                                    match_result = re.match(license_file_reg, filename_in_dir.lower())
                                    if match_result is not None:
                                        license_name = check_and_run_license_scanner(self.platform,
                                                                                     self.license_scanner_bin,
                                                                                     filename_with_checkout_path)
                                        find_license = True
                                        break
                    if license_name == '':
                        if repo == github:
                            try:
                                if not g:
                                    g = connect_github(self.github_token)
                                license_name = get_github_license(g, oss_path, self.platform, self.license_scanner_bin)
                            except Exception as e:
                                logger.warning(f"Failed to get license with github api: {e}")
                                license_name == ''

                    if self.direct_dep_list:
                        if oss_origin_name in self.direct_dep_list:
                            comment = 'direct'
                        else:
                            comment = 'transitive'

                    sheet_list.append([const.SUPPORT_PACKAE.get(self.package_manager_name),
                                      oss_name, oss_version, license_name, dn_loc, homepage, '', '', comment])

                except Exception as e:
                    logger.warning(f"Failed to parse oss information: {e}")

        return sheet_list

    def parse_direct_dependencies(self):
        self.direct_dep = True
        cartfile = 'Cartfile'
        if os.path.exists(cartfile):
            with open(cartfile, 'r', encoding='utf8') as input_fp:
                for i, line in enumerate(input_fp.readlines()):
                    re_result = re.findall(r'(github|git)[\s]\"(\S*)\"[\s]\"(\S*)\"', line)
                    try:
                        oss_path = re_result[0][1]
                        if oss_path.endswith('.git'):
                            oss_path = oss_path[:-4]
                        oss_origin_name = oss_path.split('/')[-1]
                        self.direct_dep_list.append(oss_origin_name)
                    except Exception as e:
                        logger.warning(f"Failed to parse Cartfile: {e}")


def get_checkout_dirname():
    checkout_dir_list = []
    if os.path.isdir(checkout_dir):
        for item in os.listdir(checkout_dir):
            if os.path.isdir(os.path.join(checkout_dir, item)):
                checkout_dir_list.append(item)

    return checkout_dir_list
