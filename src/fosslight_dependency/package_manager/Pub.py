#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import json
import re
import shutil
import yaml
import subprocess
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import check_and_run_license_scanner

logger = logging.getLogger(constant.LOGGER_NAME)


class Pub(PackageManager):
    package_manager_name = const.PUB

    dn_url = 'https://pub.dev/packages/'
    input_file_name = 'tmp_flutter_oss_licenses.json'
    tmp_dir = "fl_dependency_tmp_dir"
    cur_path = ''

    def __init__(self, input_dir, output_dir):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)
        self.append_input_package_list_file(self.input_file_name)

    def __del__(self):
        if self.cur_path != '':
            os.chdir(self.cur_path)
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)

    def run_plugin(self):
        if os.path.exists(self.input_file_name):
            logger.info(f"Found {self.input_file_name}, skip the flutter cmd to analyze dependency.")
            return True

        if not os.path.exists(const.SUPPORT_PACKAE.get(self.package_manager_name)):
            logger.error(f"Cannot find the file({const.SUPPORT_PACKAE.get(self.package_manager_name)})")
            return False

        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)
        os.mkdir(self.tmp_dir)
        shutil.copy(const.SUPPORT_PACKAE.get(self.package_manager_name),
                    os.path.join(self.tmp_dir, const.SUPPORT_PACKAE.get(self.package_manager_name)))

        self.cur_path = os.getcwd()
        os.chdir(self.tmp_dir)

        with open(const.SUPPORT_PACKAE.get(self.package_manager_name), 'r', encoding='utf8') as f:
            tmp_yml = yaml.safe_load(f)
            tmp_yml['dev_dependencies'] = {'flutter_oss_licenses': '^2.0.1'}
        with open(const.SUPPORT_PACKAE.get(self.package_manager_name), 'w', encoding='utf8') as f:
            f.write(yaml.dump(tmp_yml))

        cmd = "flutter pub get"
        ret = subprocess.call(cmd, shell=True)
        if ret != 0:
            logger.error(f"Failed to run: {cmd}")
            os.chdir(self.cur_path)
            return False
        cmd = "flutter pub deps --no-dev"
        ret = subprocess.check_output(cmd, shell=True)
        if ret != 0:
            pub_deps = ret.decode('utf8')
            self.parse_no_deps_file(pub_deps)

        cmd = f"flutter pub run flutter_oss_licenses:generate.dart -o {self.input_file_name} --json"
        ret = subprocess.call(cmd, shell=True)
        if ret != 0:
            logger.error(f"Failed to run: {cmd}")
            os.chdir(self.cur_path)
            return False

        return True

    def parse_no_deps_file(self, f):
        for line in f.split('\n'):
            re_result = re.findall(r'\-\-\s(\S+[^.\s])[.|\s]', line)
            if re_result:
                self.total_dep_list.append(re_result[0])
        self.total_dep_list = list(set(self.total_dep_list))

    def parse_oss_information(self, f_name):
        tmp_license_txt_file_name = 'tmp_license.txt'
        json_data = ''
        comment = ''
        tmp_no_deps_file = 'tmp_no_deps_result.txt'

        if os.path.exists(tmp_no_deps_file):
            with open(tmp_no_deps_file, 'r', encoding='utf8') as deps_f:
                deps_l = deps_f.read()
                self.parse_no_deps_file(deps_l)

        with open(f_name, 'r', encoding='utf8') as pub_file:
            json_f = json.load(pub_file)

        try:
            sheet_list = []

            for json_data in json_f:
                oss_origin_name = json_data['name']
                if self.total_dep_list != [] and oss_origin_name not in self.total_dep_list:
                    continue
                oss_name = f"{self.package_manager_name}:{oss_origin_name}"
                oss_version = json_data['version']
                homepage = json_data['homepage']
                dn_loc = f"{self.dn_url}{oss_origin_name}/versions/{oss_version}"
                license_txt = json_data['license']

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

                if self.direct_dep:
                    if json_data['isDirectDependency']:
                        comment = 'direct'
                    else:
                        comment = 'transitive'

                sheet_list.append([const.SUPPORT_PACKAE.get(self.package_manager_name),
                                  oss_name, oss_version, license_name, dn_loc, homepage, '', '', comment])
        except Exception as e:
            logger.error(f"Fail to parse pub oss information: {e}")

        if os.path.isfile(tmp_license_txt_file_name):
            os.remove(tmp_license_txt_file_name)

        return sheet_list

    def parse_direct_dependencies(self):
        self.direct_dep = True
