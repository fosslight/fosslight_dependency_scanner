#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import json
import re
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import check_and_run_license_scanner

logger = logging.getLogger(constant.LOGGER_NAME)


class Pub(PackageManager):
    package_manager_name = const.PUB

    dn_url = 'https://pub.dev/packages/'
    input_file_name = os.path.join('lib', 'oss_licenses.dart')

    def __init__(self, input_dir, output_dir):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)
        self.append_input_package_list_file(self.input_file_name)

    def parse_oss_information(self, f_name):
        tmp_license_txt_file_name = 'tmp_license.txt'
        json_data = ''

        with open(f_name, 'r', encoding='utf8') as pub_file:
            json_txt = preprocess_pub_result(pub_file)
            if json_txt:
                json_data = json.loads(json_txt)

        try:
            sheet_list = []

            for key in json_data:
                oss_origin_name = json_data[key]['name']
                oss_name = self.package_manager_name + ":" + oss_origin_name
                oss_version = json_data[key]['version']
                homepage = json_data[key]['homepage']
                dn_loc = self.dn_url + oss_origin_name + "/versions/" + oss_version
                license_txt = json_data[key]['license']

                tmp_license_txt = open(tmp_license_txt_file_name, 'w', encoding='utf-8')
                tmp_license_txt.write(license_txt)
                tmp_license_txt.close()

                license_name_with_license_scanner = check_and_run_license_scanner(self.platform,
                                                                                  self.license_scanner_bin,
                                                                                  tmp_license_txt_file_name)

                if license_name_with_license_scanner != "":
                    license_name = license_name_with_license_scanner
                else:
                    license_name = ''

                sheet_list.append([const.SUPPORT_PACKAE.get(self.package_manager_name),
                                  oss_name, oss_version, license_name, dn_loc, homepage, '', '', ''])

        except Exception as e:
            logger.error("Fail to parse pub oss information: " + str(e))

        if os.path.isfile(tmp_license_txt_file_name):
            os.remove(tmp_license_txt_file_name)

        return sheet_list


def preprocess_pub_result(input_file):
    matched_json = re.findall(r'final ossLicenses = <String, dynamic>({[\s\S]*});', input_file.read())
    if len(matched_json) > 0:
        return matched_json[0]
    else:
        logger.error("Fail to parse the result json from pub input file.")
        return ''
