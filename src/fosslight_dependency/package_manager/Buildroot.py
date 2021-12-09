#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import subprocess
import json
import urllib.parse
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager

logger = logging.getLogger(constant.LOGGER_NAME)


class Buildroot(PackageManager):
    package_manager_name = const.BUILDROOT

    input_file_name = ''
    is_run_plugin = False
    dn_url = ''
    tmp_file_name = 'tmp_show_info.json'

    detect_package_type = ["target"]

    def __init__(self, input_dir, output_dir):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)

    def __del__(self):
        if os.path.isfile(self.tmp_file_name):
            os.remove(self.tmp_file_name)

    def run_plugin(self):
        ret = True

        logger.info("Execute 'make show-info' to obtain package info.")
        cmd = "make show-info > " + self.tmp_file_name

        ret_cmd = subprocess.call(cmd, shell=True)
        if ret_cmd != 0:
            logger.error("Failed to make show-info: " + cmd)
            ret = False

        self.append_input_package_list_file(self.tmp_file_name)

        return ret

    def parse_oss_information(self, f_name):
        with open(f_name, 'r', encoding='utf8') as show_info:
            json_file = json.load(show_info)

        package_type = "type"
        package_install_target = "install_target"
        package_version = "version"
        package_license = "licenses"

        sheet_list = []
        for key in json_file:
            if (package_type in json_file[key]) and (package_install_target in json_file[key]):
                if (json_file[key][package_type] in self.detect_package_type) and (json_file[key][package_install_target]):
                    try:
                        oss_name = key
                        try:
                            oss_version = json_file[key][package_version]
                        except Exception:
                            oss_version = ''
                        try:
                            license_name = json_file[key][[package_license]]
                            if license_name == 'unknown':
                                license_name = ''
                            license_name = license_name.replace(',', '')
                        except Exception:
                            license_name = ''
                        try:
                            source = json_file[key]["downloads"][0]["source"]
                            uris = json_file[key]["downloads"][0]["uris"][0].split("+")[-1]
                            dn_loc = urllib.parse.urljoin(base=uris, url=source)
                            homepage = uris
                        except Exception:
                            dn_loc = ''
                            homepage = ''

                        sheet_list.append([const.SUPPORT_PACKAE.get(self.package_manager_name),
                                          oss_name, oss_version, license_name, dn_loc, homepage, '', '', ''])
                    except Exception as e:
                        logging.warning("Fail to parse " + key + ": " + str(e))

        return sheet_list
