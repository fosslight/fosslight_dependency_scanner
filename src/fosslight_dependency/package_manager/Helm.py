#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2023 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import subprocess
import yaml
import shutil
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_util.download import extract_compressed_dir

logger = logging.getLogger(constant.LOGGER_NAME)


class Helm(PackageManager):
    package_manager_name = const.HELM
    tmp_charts_dir = 'tmp_charts'

    input_file_name = const.SUPPORT_PACKAE.get(package_manager_name)

    def __init__(self, input_dir, output_dir):
        super().__init__(self.package_manager_name, '', input_dir, output_dir)
        self.append_input_package_list_file(self.input_file_name)

    def __del__(self):
        if os.path.exists(self.tmp_charts_dir):
            shutil.rmtree(self.tmp_charts_dir, ignore_errors=True)

    def run_plugin(self):
        ret = True
        charts_dir = 'charts'
        if os.path.isdir(charts_dir):
            shutil.copytree(charts_dir, self.tmp_charts_dir)
        else:
            logger.info("Execute 'helm dependency build' to obtain package info.")
            cmd = "helm dependency build"

            ret_cmd = subprocess.call(cmd, shell=True)
            if ret_cmd != 0:
                logger.error(f"Failed to build helm dependency: {cmd}")
                ret = False
            else:
                shutil.copytree(charts_dir, self.tmp_charts_dir)
                shutil.rmtree(charts_dir, ignore_errors=True)

        ret = extract_compressed_dir(self.tmp_charts_dir, self.tmp_charts_dir, False)
        if not ret:
            logger.error(f'Fail to extract compressed dir: {self.tmp_charts_dir}')
        else:
            logger.warning('Success to extract compressed dir')

        return ret

    def parse_oss_information(self, f_name):
        dep_item_list = []
        sheet_list = []

        with open(f_name, 'r', encoding='utf8') as yaml_fp:
            yaml_f = yaml.safe_load(yaml_fp)
            for dep in yaml_f['dependencies']:
                dep_item_list.append(dep['name'])
        for dep in dep_item_list:
            try:
                f_path = os.path.join(self.tmp_charts_dir, dep, f_name)
                with open(f_path, 'r', encoding='utf8') as yaml_fp:
                    yaml_f = yaml.safe_load(yaml_fp)
                    oss_name = f'{self.package_manager_name}:{yaml_f["name"]}'
                    oss_version = yaml_f.get('version', '')
                    if oss_version.startswith('v'):
                        oss_version = oss_version[1:]

                    homepage = yaml_f.get('home', '')
                    dn_loc = ''
                    if yaml_f.get('sources', '') != '':
                        dn_loc = yaml_f.get('sources', '')[0]

                    license_name = ''
                    if yaml_f.get('annotations', '') != '':
                        license_name = yaml_f['annotations'].get('licenses', '')

                    if self.direct_dep:
                        comment = 'direct'

            except Exception as e:
                logging.warning(f"Fail to parse chart info {dep}: {e}")
                continue

            sheet_list.append([const.SUPPORT_PACKAE.get(self.package_manager_name),
                              oss_name, oss_version, license_name, dn_loc, homepage, '', '', comment, ''])

        return sheet_list
