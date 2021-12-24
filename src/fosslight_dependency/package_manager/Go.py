#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import subprocess
import re
from bs4 import BeautifulSoup
import urllib.request
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager

logger = logging.getLogger(constant.LOGGER_NAME)


class Go(PackageManager):
    package_manager_name = const.GO

    input_file_name = ''
    is_run_plugin = False
    dn_url = 'https://pkg.go.dev/'
    tmp_file_name = 'tmp_go_list.json'

    def __init__(self, input_dir, output_dir):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)

    def __del__(self):
        if os.path.isfile(self.tmp_file_name):
            os.remove(self.tmp_file_name)

    def run_plugin(self):
        ret = True

        logger.info("Execute 'go list -m all' to obtain package info.")
        cmd = "go list -m all > " + self.tmp_file_name

        ret_cmd = subprocess.call(cmd, shell=True)
        if ret_cmd != 0:
            logger.error("Failed to make the result: " + cmd)
            ret = False

        self.append_input_package_list_file(self.tmp_file_name)

        return ret

    def parse_oss_information(self, f_name):
        with open(f_name, 'r', encoding='utf8') as input_fp:
            sheet_list = []
            for i, line in enumerate(input_fp.readlines()):

                re_result = re.findall(r'(\S+)\s?(\S*)', line)
                try:
                    package_path = re_result[0][0]
                    oss_name = self.package_manager_name + ":" + package_path
                    oss_version = re_result[0][1]

                    tmp_dn_loc = self.dn_url + package_path
                    if oss_version:
                        dn_loc = tmp_dn_loc + '@' + oss_version
                    else:
                        dn_loc = tmp_dn_loc

                    license_name = ''
                    homepage = ''
                    comment = ''

                    for dn_loc_i in [dn_loc, tmp_dn_loc]:
                        try:
                            res = urllib.request.urlopen(dn_loc_i)
                            if res.getcode() == 200:
                                urlopen_success = True
                                if dn_loc_i == tmp_dn_loc:
                                    if oss_version:
                                        comment = 'Cannot connect ' \
                                                  + dn_loc \
                                                  + ', so use the latest version page to get the license, homepage.'
                                    dn_loc = tmp_dn_loc
                                break
                        except Exception:
                            continue

                    if urlopen_success:
                        content = res.read().decode('utf8')
                        bs_obj = BeautifulSoup(content, 'html.parser')

                        license_data = bs_obj.find('a', {'data-test-id': 'UnitHeader-license'})
                        if license_data:
                            license_name = license_data.text

                        repository_data = bs_obj.find('div', {'class': 'UnitMeta-repo'})
                        if repository_data:
                            homepage = repository_data.find('a')['href']

                except Exception as e:
                    logging.warning("Fail to parse " + line + ": " + str(e))
                    continue

                sheet_list.append([const.SUPPORT_PACKAE.get(self.package_manager_name),
                                  oss_name, oss_version, license_name, dn_loc, homepage, '', '', comment])

        return sheet_list
