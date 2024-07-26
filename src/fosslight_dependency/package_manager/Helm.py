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
from fosslight_dependency._package_manager import PackageManager, get_url_to_purl
from fosslight_util.download import extract_compressed_dir
from fosslight_dependency.dependency_item import DependencyItem
from fosslight_util.oss_item import OssItem

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
                if not os.path.isdir(charts_dir):
                    logger.warning(f"Cannot create {charts_dir} because of no dependencies in Chart.yaml. "
                                   f"So you don't need to analyze dependency.")
                    return True
                else:
                    shutil.copytree(charts_dir, self.tmp_charts_dir)
                    shutil.rmtree(charts_dir, ignore_errors=True)
        if ret:
            ret = extract_compressed_dir(self.tmp_charts_dir, self.tmp_charts_dir, False)
            if not ret:
                logger.error(f'Fail to extract compressed dir: {self.tmp_charts_dir}')
            else:
                logger.warning('Success to extract compressed dir')

        return ret

    def parse_oss_information(self, f_name):
        dep_item_list = []
        _dependencies = 'dependencies'

        with open(f_name, 'r', encoding='utf8') as yaml_fp:
            yaml_f = yaml.safe_load(yaml_fp)
            if _dependencies in yaml_f:
                for dep in yaml_f[_dependencies]:
                    dep_item_list.append(dep['name'])
        for dep in dep_item_list:
            try:
                f_path = os.path.join(self.tmp_charts_dir, dep, f_name)
                dep_item = DependencyItem()
                oss_item = OssItem()
                with open(f_path, 'r', encoding='utf8') as yaml_fp:
                    yaml_f = yaml.safe_load(yaml_fp)
                    oss_item.name = f'{self.package_manager_name}:{yaml_f["name"]}'
                    oss_item.version = yaml_f.get('version', '')
                    if oss_item.version.startswith('v'):
                        oss_item.version = oss_item.version[1:]

                    oss_item.homepage = yaml_f.get('home', '')
                    if yaml_f.get('sources', '') != '':
                        oss_item.download_location = yaml_f.get('sources', '')[0]

                    dep_item.purl = get_url_to_purl(
                        oss_item.download_location if oss_item.download_location else oss_item.homepage,
                        self.package_manager_name
                    )

                    if yaml_f.get('annotations', '') != '':
                        oss_item.license = yaml_f['annotations'].get('licenses', '')

                    if self.direct_dep:
                        oss_item.comment = 'direct'

            except Exception as e:
                logging.warning(f"Fail to parse chart info {dep}: {e}")
                continue
            dep_item.oss_items.append(oss_item)
            self.dep_items.append(dep_item)
        return
