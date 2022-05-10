#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import subprocess
import json
import shutil
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager

logger = logging.getLogger(constant.LOGGER_NAME)
node_modules = 'node_modules'


class Npm(PackageManager):
    package_manager_name = const.NPM

    dn_url = 'https://www.npmjs.com/package/'
    input_file_name = 'tmp_npm_license_output.json'
    flag_tmp_node_modules = False

    direct_dep_dict = dict()

    def __init__(self, input_dir, output_dir):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)
        self.direct_dep_dict = dict()

    def __del__(self):
        if os.path.isfile(self.input_file_name):
            os.remove(self.input_file_name)
        if self.flag_tmp_node_modules:
            shutil.rmtree(node_modules, ignore_errors=True)

    def run_plugin(self):
        ret = self.start_license_checker()
        return ret

    def start_license_checker(self):
        ret = True
        tmp_custom_json = 'custom.json'
        license_checker_cmd = f'license-checker --production --json --out {self.input_file_name}'
        custom_path_option = ' --customPath '
        npm_install_cmd = 'npm install --prod'

        if os.path.isdir(node_modules) != 1:
            logger.info("node_modules directory is not existed. So it executes 'npm install'.")
            self.flag_tmp_node_modules = True
            cmd_ret = subprocess.call(npm_install_cmd, shell=True)
            if cmd_ret != 0:
                logger.error(f"{npm_install_cmd} returns an error")
                return False

        # customized json file for obtaining specific items with license-checker
        self.make_custom_json(tmp_custom_json)

        cmd = license_checker_cmd + custom_path_option + tmp_custom_json
        cmd_ret = subprocess.call(cmd, shell=True)
        if cmd_ret != 0:
            logger.error(f"It returns the error: {cmd}")
            logger.error("Please check if the license-checker is installed.(sudo npm install -g license-checker)")
            return False
        else:
            self.append_input_package_list_file(self.input_file_name)

        os.remove(tmp_custom_json)

        return ret

    def make_custom_json(self, tmp_custom_json):
        with open(tmp_custom_json, 'w', encoding='utf8') as custom:
            custom.write(
                "{\n\t\"name\": \"\",\n\t\"version\": \"\",\n\t\"licenses\": \"\",\n\t\"repository\": \
                \"\",\n\t\"url\": \"\",\n\t\"copyright\": \"\",\n\t\"licenseText\": \"\"\n}\n".encode().decode("utf-8"))

    def parse_oss_information(self, f_name):
        with open(f_name, 'r', encoding='utf8') as json_file:
            json_data = json.load(json_file)

        sheet_list = []
        comment = ''

        keys = [key for key in json_data]

        for i in range(0, len(keys)):
            d = json_data.get(keys[i - 1])
            oss_init_name = d['name']
            oss_name = self.package_manager_name + ":" + oss_init_name

            if d['licenses']:
                license_name = d['licenses']
            else:
                license_name = ''

            oss_version = d['version']
            package_path = d['path']

            if d['repository']:
                dn_loc = d['repository']
            else:
                dn_loc = f"{self.dn_url}{oss_init_name}/v/{oss_version}"

            homepage = self.dn_url + oss_init_name

            if self.direct_dep_dict:
                if oss_init_name in self.direct_dep_dict.keys():
                    if oss_version in self.direct_dep_dict[oss_init_name]:
                        comment = 'direct'
                else:
                    comment = 'transitive'

            multi_license = check_multi_license(license_name)
            manifest_file_path = os.path.join(package_path, const.SUPPORT_PACKAE.get(self.package_manager_name))
            if multi_license:
                for l_idx in range(0, len(license_name)):
                    license_name = license_name[l_idx].replace(",", "")
                    license_name = check_unknown_license(license_name, manifest_file_path)
                    sheet_list.append([const.SUPPORT_PACKAE.get(self.package_manager_name),
                                      oss_name, oss_version, license_name, dn_loc, homepage, '', '', comment])
            else:
                license_name = license_name.replace(",", "")
                license_name = check_unknown_license(license_name, manifest_file_path)
                sheet_list.append([const.SUPPORT_PACKAE.get(self.package_manager_name),
                                  oss_name, oss_version, license_name, dn_loc, homepage, '', '', comment])

        return sheet_list

    def parse_direct_dependencies(self):
        tmp_oss_list = []
        dependencies = 'dependencies'
        version = 'version'

        manifest_file = const.SUPPORT_PACKAE.get(self.package_manager_name)
        try:
            with open(manifest_file, 'r') as lock_file:
                json_lock = json.load(lock_file)
                if dependencies in json_lock:
                    for dep in json_lock[dependencies]:
                        tmp_oss_list.append(dep)
            for direct_oss in tmp_oss_list:
                with open(os.path.join(node_modules, direct_oss, manifest_file)) as direct_file:
                    json_direct = json.load(direct_file)
                    if version in json_direct:
                        self.direct_dep_dict[direct_oss] = json_direct[version]
        except Exception as e:
            logger.warning(f'Cannot print if it is direct dependency: {e}')


def check_multi_license(license_name):
    if isinstance(license_name, list):
        multi_license = True
    else:
        multi_license = False

    return multi_license


def check_unknown_license(license_name, manifest_file_path):
    if license_name.endswith('*'):
        license_name = license_name[:-1]

    if license_name == 'UNKNOWN':
        try:
            with open(manifest_file_path, 'r') as f:
                json_f = json.load(f)
                for key in json_f.keys():
                    if key == 'license':
                        license_name = json_f[key]
                        break
        except Exception as e:
            logging.warning(f"Cannot check unknown license: {e}")

    return license_name
