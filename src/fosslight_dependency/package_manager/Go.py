#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import subprocess
import json
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
        self.input_file_name = ''
        self.is_run_plugin = False

    def __del__(self):
        if os.path.isfile(self.tmp_file_name):
            os.remove(self.tmp_file_name)

    def run_plugin(self):
        ret = True

        logger.info("Execute 'go list -m -mod=mod -json all' to obtain package info.")
        cmd = f"go list -m -mod=mod -json all > {self.tmp_file_name}"

        ret_cmd = subprocess.call(cmd, shell=True)
        if ret_cmd != 0:
            logger.error(f"Failed to make the result: {cmd}")
            ret = False

        self.append_input_package_list_file(self.tmp_file_name)

        return ret

    def parse_oss_information(self, f_name):
        indirect = 'Indirect'
        sheet_list = []
        json_list = []
        with open(f_name, 'r', encoding='utf8') as input_fp:
            json_data_raw = ''
            for line in input_fp.readlines():
                json_data_raw += line
                if line.startswith('}'):
                    json_list.append(json.loads(json_data_raw))
                    json_data_raw = ''

        for dep_item in json_list:
            try:
                if 'Main' in dep_item:
                    if dep_item['Main']:
                        continue
                package_path = dep_item['Path']
                oss_name = f"{self.package_manager_name}:{package_path}"
                oss_version = dep_item['Version']

                comment = []
                if self.direct_dep:
                    if indirect in dep_item:
                        if dep_item[indirect]:
                            comment.append('transitive')
                        else:
                            comment.append('direct')
                    else:
                        comment.append('direct')

                homepage_set = []
                homepage = self.dn_url + package_path

                if oss_version:
                    tmp_homepage = f"{homepage}@{oss_version}"
                    homepage_set.append(tmp_homepage)
                homepage_set.append(homepage)

                license_name = ''
                dn_loc = ''

                if oss_version.startswith('v'):
                    oss_version = oss_version[1:]

                for homepage_i in homepage_set:
                    try:
                        res = urllib.request.urlopen(homepage_i)
                        if res.getcode() == 200:
                            urlopen_success = True
                            if homepage_i == homepage:
                                if oss_version:
                                    comment.append(f'Cannot connect {tmp_homepage}, get info from the latest version.')
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
                        dn_loc = repository_data.find('a')['href']
                    else:
                        dn_loc = homepage

            except Exception as e:
                logging.warning(f"Fail to parse {package_path} in go mod : {e}")
                continue

            comment = ', '.join(comment)
            sheet_list.append([const.SUPPORT_PACKAE.get(self.package_manager_name),
                              oss_name, oss_version, license_name, dn_loc, homepage, '', '', comment])

        return sheet_list
