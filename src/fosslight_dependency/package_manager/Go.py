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
import re
import shutil
import time
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager, get_url_to_purl
from fosslight_dependency.dependency_item import DependencyItem, change_dependson_to_purl
from fosslight_util.oss_item import OssItem

logger = logging.getLogger(constant.LOGGER_NAME)


class Go(PackageManager):
    package_manager_name = const.GO

    input_file_name = ''
    is_run_plugin = False
    dn_url = 'https://pkg.go.dev/'
    tmp_file_name = 'tmp_go_list.json'
    go_work = 'go.work'
    tmp_go_work = 'go.work.tmp'

    def __init__(self, input_dir, output_dir):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)
        self.input_file_name = ''
        self.is_run_plugin = False

    def __del__(self):
        if os.path.isfile(self.tmp_file_name):
            os.remove(self.tmp_file_name)
        if os.path.isfile(self.tmp_go_work):
            shutil.move(self.tmp_go_work, self.go_work)

    def parse_dependency_tree(self, go_deptree_txt):
        for line in go_deptree_txt.split('\n'):
            re_result = re.findall(r'(\S+)@v(\S+)\s(\S+)@v(\S+)', line)
            if len(re_result) > 0 and len(re_result[0]) >= 4:
                oss_name = re_result[0][0]
                oss_ver = re_result[0][1]
                pkg_name = re_result[0][2]
                pkg_ver = re_result[0][3]
                if f'{oss_name}({oss_ver})' not in self.relation_tree:
                    self.relation_tree[f'{oss_name}({oss_ver})'] = []
                self.relation_tree[f'{oss_name}({oss_ver})'].append(f'{pkg_name}({pkg_ver})')

    def run_plugin(self):
        ret = True

        if os.path.isfile(self.go_work):
            shutil.move(self.go_work, self.tmp_go_work)

        logger.info("Execute 'go list -m -mod=mod -json all' to obtain package info.")
        cmd = f"go list -m -mod=mod -json all > {self.tmp_file_name}"

        ret_cmd = subprocess.call(cmd, shell=True)
        if ret_cmd != 0:
            logger.error(f"Failed to make the result: {cmd}")
            ret = False

        self.append_input_package_list_file(self.tmp_file_name)

        cmd_tree = "go mod graph"
        ret_cmd_tree = subprocess.check_output(cmd_tree, shell=True, text=True, encoding='utf-8')
        if ret_cmd_tree != 0:
            self.parse_dependency_tree(ret_cmd_tree)

        if os.path.isfile(self.tmp_go_work):
            shutil.move(self.tmp_go_work, self.go_work)
        return ret

    def parse_oss_information(self, f_name):
        indirect = 'Indirect'
        purl_dict = {}
        json_list = []
        with open(f_name, 'r', encoding='utf8') as input_fp:
            json_data_raw = ''
            for line in input_fp.readlines():
                json_data_raw += line
                if line.startswith('}'):
                    json_list.append(json.loads(json_data_raw))
                    json_data_raw = ''

        for dep_i in json_list:
            dep_item = DependencyItem()
            oss_item = OssItem()
            try:
                if 'Main' in dep_i:
                    if dep_i['Main']:
                        continue
                package_path = dep_i['Path']
                oss_item.name = f"{self.package_manager_name}:{package_path}"
                oss_origin_version = dep_i['Version']
                if oss_origin_version.startswith('v'):
                    oss_item.version = oss_origin_version[1:]
                else:
                    oss_item.version = oss_origin_version

                if self.direct_dep:
                    if indirect in dep_i:
                        if dep_i[indirect]:
                            oss_item.comment = 'transitive'
                        else:
                            oss_item.comment = 'direct'
                    else:
                        oss_item.comment = 'direct'

                if f'{package_path}({oss_item.version})' in self.relation_tree:
                    dep_item.depends_on_raw = self.relation_tree[f'{package_path}({oss_item.version})']

                dn_loc_set = []
                tmp_dn_loc = self.dn_url + package_path
                dep_item.purl = get_url_to_purl(f"{tmp_dn_loc}@{oss_item.version}", self.package_manager_name)
                purl_dict[f'{package_path}({oss_item.version})'] = dep_item.purl

                if oss_origin_version:
                    oss_item.download_location = f"{tmp_dn_loc}@{oss_origin_version}"
                    dn_loc_set.append(oss_item.download_location)
                dn_loc_set.append(tmp_dn_loc)

                for dn_loc_i in dn_loc_set:
                    urlopen_success = False
                    while True:
                        try:
                            res = urllib.request.urlopen(dn_loc_i)
                            if res.getcode() == 200:
                                urlopen_success = True
                                if dn_loc_i == tmp_dn_loc:
                                    if oss_item.version:
                                        oss_item.comment = (f'Not found {oss_item.download_location}, '
                                                            'get info from latest version.')
                                        oss_item.download_location = tmp_dn_loc
                                break
                        except urllib.error.HTTPError as e:
                            if e.code == 429:
                                logger.info(f"{e} ({dn_loc_i}), Retrying to connect after 20 seconds")
                                time.sleep(20)
                                continue
                            else:
                                logger.info(f"{e} ({dn_loc_i})")
                                break
                        except Exception as e:
                            logger.warning(f"{e} ({dn_loc_i})")
                            break
                    if urlopen_success:
                        break

                if urlopen_success:
                    content = res.read().decode('utf8')
                    bs_obj = BeautifulSoup(content, 'html.parser')

                    license_data = bs_obj.find('a', {'data-test-id': 'UnitHeader-license'})
                    if license_data:
                        oss_item.license = license_data.text

                    repository_data = bs_obj.find('div', {'class': 'UnitMeta-repo'})
                    if repository_data:
                        oss_item.homepage = repository_data.find('a')['href']
                    else:
                        oss_item.homepage = oss_item.download_location

            except Exception as e:
                logging.warning(f"Fail to parse {package_path} in go mod : {e}")
                continue
            dep_item.oss_items.append(oss_item)
            self.dep_items.append(dep_item)
        if self.direct_dep:
            self.dep_items = change_dependson_to_purl(purl_dict, self.dep_items)
        return
