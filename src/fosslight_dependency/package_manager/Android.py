#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager, get_url_to_purl
from fosslight_dependency.dependency_item import DependencyItem, change_dependson_to_purl
from fosslight_util.oss_item import OssItem

logger = logging.getLogger(constant.LOGGER_NAME)


class Android(PackageManager):
    package_manager_name = const.ANDROID

    plugin_output_file = 'android_dependency_output.txt'
    app_name = const.default_app_name
    input_file_name = ''
    plugin_auto_run = False

    def __init__(self, input_dir, output_dir, app_name):
        super().__init__(self.package_manager_name, '', input_dir, output_dir)
        if app_name:
            self.app_name = app_name
        self.input_file_name = self.check_input_path()
        self.append_input_package_list_file(self.input_file_name)

    def __del__(self):
        if self.plugin_auto_run:
            if os.path.isfile(self.input_file_name):
                os.remove(self.input_file_name)

    def check_input_path(self):
        if os.path.isfile(self.plugin_output_file):
            return self.plugin_output_file
        else:
            return os.path.join(self.app_name, self.plugin_output_file)

    def parse_oss_information(self, f_name):
        with open(f_name, 'r', encoding='utf8') as input_fp:
            purl_dict = {}
            for i, line in enumerate(input_fp.readlines()):
                dep_item = DependencyItem()
                oss_item = OssItem()
                split_str = line.strip().split("\t")
                if i < 2:
                    continue

                if len(split_str) == 9 or len(split_str) == 7:
                    _, _, oss_item.name, oss_item.version, oss_item.license, \
                        oss_item.download_location, oss_item.homepage = split_str[:7]
                else:
                    continue
                dep_item.purl = get_url_to_purl(oss_item.download_location, 'maven')
                purl_dict[f'{oss_item.name}({oss_item.version})'] = dep_item.purl

                if self.direct_dep:
                    dep_key = f"{oss_item.name}({oss_item.version})"
                    if self.total_dep_list:
                        if dep_key not in self.total_dep_list:
                            continue
                    if dep_key in self.direct_dep_list:
                        oss_item.comment = 'direct'
                    else:
                        oss_item.comment = 'transitive'
                    try:
                        if dep_key in self.relation_tree:
                            dep_item.depends_on_raw = self.relation_tree[dep_key]
                    except Exception as e:
                        logger.error(f"Fail to find oss scope in dependency tree: {e}")

                dep_item.oss_items.append(oss_item)
                self.dep_items.append(dep_item)

            if self.direct_dep:
                self.dep_items = change_dependson_to_purl(purl_dict, self.dep_items)

        return
