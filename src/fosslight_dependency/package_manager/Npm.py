#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import subprocess
import json
import shutil
import re
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager, get_url_to_purl
from fosslight_dependency.dependency_item import DependencyItem, change_dependson_to_purl
from fosslight_util.oss_item import OssItem

logger = logging.getLogger(constant.LOGGER_NAME)
node_modules = 'node_modules'


class Npm(PackageManager):
    package_manager_name = const.NPM

    dn_url = 'https://www.npmjs.com/package/'
    input_file_name = 'tmp_npm_license_output.json'
    tmp_custom_json = 'custom.json'
    flag_tmp_node_modules = False

    def __init__(self, input_dir, output_dir):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)

    def __del__(self):
        if os.path.isfile(self.input_file_name):
            os.remove(self.input_file_name)
        if self.flag_tmp_node_modules:
            shutil.rmtree(node_modules, ignore_errors=True)
        if os.path.exists(self.tmp_custom_json):
            os.remove(self.tmp_custom_json)

    def run_plugin(self):
        ret = self.start_license_checker()
        return ret

    def start_license_checker(self):
        ret = True
        license_checker_cmd = f'license-checker --production --json --out {self.input_file_name}'
        custom_path_option = ' --customPath '
        npm_install_cmd = 'npm install --production --ignore-scripts'

        if os.path.isdir(node_modules) != 1:
            logger.info(f"node_modules directory is not existed. So it executes '{npm_install_cmd}'.")
            self.flag_tmp_node_modules = True
            cmd_ret = subprocess.call(npm_install_cmd, shell=True)
            if cmd_ret != 0:
                logger.error(f"{npm_install_cmd} returns an error")
                return False

        # customized json file for obtaining specific items with license-checker
        self.make_custom_json(self.tmp_custom_json)

        cmd = license_checker_cmd + custom_path_option + self.tmp_custom_json
        cmd_ret = subprocess.call(cmd, shell=True)
        if cmd_ret != 0:
            logger.error(f"It returns the error: {cmd}")
            logger.error("Please check if the license-checker is installed.(sudo npm install -g license-checker)")
            ret = False
        else:
            self.append_input_package_list_file(self.input_file_name)
        if os.path.exists(self.tmp_custom_json):
            os.remove(self.tmp_custom_json)

        return ret

    def make_custom_json(self, tmp_custom_json):
        with open(tmp_custom_json, 'w', encoding='utf8') as custom:
            custom.write(
                "{\n\t\"name\": \"\",\n\t\"version\": \"\",\n\t\"licenses\": \"\",\n\t\"repository\": \
                \"\",\n\t\"url\": \"\",\n\t\"copyright\": \"\",\n\t\"licenseText\": \"\"\n}\n".encode().decode("utf-8"))

    def parse_rel_dependencies(self, rel_name, rel_ver, rel_dependencies):
        _dependencies = 'dependencies'
        _version = 'version'
        _peer = 'peerMissing'

        for rel_dep_name in rel_dependencies.keys():
            # Optional, non-installed dependencies are listed as empty objects
            if rel_dependencies[rel_dep_name] == {}:
                continue
            if _peer in rel_dependencies[rel_dep_name]:
                if rel_dependencies[rel_dep_name][_peer]:
                    continue
            if f'{rel_name}({rel_ver})' not in self.relation_tree:
                self.relation_tree[f'{rel_name}({rel_ver})'] = []
            elif f'{rel_dep_name}({rel_dependencies[rel_dep_name][_version]})' in self.relation_tree[f'{rel_name}({rel_ver})']:
                continue
            self.relation_tree[f'{rel_name}({rel_ver})'].append(f'{rel_dep_name}({rel_dependencies[rel_dep_name][_version]})')
            if _dependencies in rel_dependencies[rel_dep_name]:
                self.parse_rel_dependencies(rel_dep_name, rel_dependencies[rel_dep_name][_version],
                                            rel_dependencies[rel_dep_name][_dependencies])

    def parse_transitive_relationship(self):
        _dependencies = 'dependencies'
        _version = 'version'
        _name = 'name'
        ret = True
        err_msg = ''

        cmd = 'npm ls -a --omit=dev --json -s'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
        rel_tree = result.stdout
        if rel_tree is None:
            logger.error(f"It returns the error: {cmd}")
            logger.error(f"No output for {cmd}")
            ret = False
        if ret:
            if result.returncode == 1:
                logger.warning(f"'{cmd}' returns error code: {result.stderr}")

            try:
                rel_json = json.loads(rel_tree)
                if len(rel_json) < 1:
                    ret = False
                else:
                    self.package_name = f'{rel_json[_name]}({rel_json[_version]})'
                    if _dependencies in rel_json:
                        self.parse_rel_dependencies(rel_json[_name], rel_json[_version], rel_json[_dependencies])
            except Exception as e:
                ret = False
                err_msg = e
        return ret, err_msg

    def parse_direct_dependencies(self):
        if not self.direct_dep:
            return
        try:
            if os.path.isfile(const.SUPPORT_PACKAE.get(self.package_manager_name)):
                ret, err_msg = self.parse_transitive_relationship()
                if not ret:
                    self.direct_dep = False
                    logger.warning(f'It cannot print direct/transitive dependency: {err_msg}')
            else:
                logger.info('Direct/transitive support is not possible because the package.json file does not exist.')
                self.direct_dep = False
        except Exception as e:
            logger.warning(f'Cannot print direct/transitive dependency: {e}')
            self.direct_dep = False

    def parse_oss_information(self, f_name):
        with open(f_name, 'r', encoding='utf8') as json_file:
            json_data = json.load(json_file)

        _licenses = 'licenses'
        _repository = 'repository'
        _private = 'private'

        keys = [key for key in json_data]
        purl_dict = {}
        for i in range(0, len(keys)):
            dep_item = DependencyItem()
            oss_item = OssItem()
            d = json_data.get(keys[i - 1])
            oss_init_name = d['name']
            oss_item.name = self.package_manager_name + ":" + oss_init_name

            if d[_licenses]:
                license_name = d[_licenses]
            else:
                license_name = ''

            oss_item.version = d['version']
            package_path = d['path']

            private_pkg = False
            if _private in d:
                if d[_private]:
                    private_pkg = True

            oss_item.download_location = f"{self.dn_url}{oss_init_name}/v/{oss_item.version}"
            dn_loc = f"{self.dn_url}{oss_init_name}"
            dep_item.purl = get_url_to_purl(dn_loc, self.package_manager_name)
            purl_dict[f'{oss_init_name}({oss_item.version})'] = dep_item.purl
            if d[_repository]:
                dn_loc = d[_repository]
            elif private_pkg:
                dn_loc = ''

            oss_item.homepage = dn_loc

            if private_pkg:
                oss_item.download_location = oss_item.homepage
                oss_item.comment = 'private'
            if self.package_name == f'{oss_init_name}({oss_item.version})':
                oss_item.comment = 'root package'
            elif self.direct_dep and len(self.relation_tree) > 0:
                if f'{oss_init_name}({oss_item.version})' in self.relation_tree[self.package_name]:
                    oss_item.comment = 'direct'
                else:
                    oss_item.comment = 'transitive'

                if f'{oss_init_name}({oss_item.version})' in self.relation_tree:
                    dep_item.depends_on_raw = self.relation_tree[f'{oss_init_name}({oss_item.version})']

            manifest_file_path = os.path.join(package_path, const.SUPPORT_PACKAE.get(self.package_manager_name))
            multi_license, license_comment, multi_flag = check_multi_license(license_name, manifest_file_path)

            if multi_flag:
                oss_item.comment = license_comment
                license_name = multi_license
            else:
                license_name = license_name.replace(",", "")
                license_name = check_unknown_license(license_name, manifest_file_path)
            oss_item.license = license_name

            dep_item.oss_items.append(oss_item)
            self.dep_items.append(dep_item)

        if self.direct_dep:
            self.dep_items = change_dependson_to_purl(purl_dict, self.dep_items)
        return


def check_multi_license(license_name, manifest_file_path):
    multi_license_list = []
    multi_license = ''
    license_comment = ''
    multi_flag = False
    try:
        if isinstance(license_name, list):
            for i in range(0, len(license_name)):
                l_i = license_name[i].replace(",", "")
                multi_license_list.append(check_unknown_license(l_i, manifest_file_path))
            multi_license = ','.join(multi_license_list)
            multi_flag = True
        else:
            if license_name.startswith('(') and license_name.endswith(')'):
                license_name = license_name.lstrip('(').rstrip(')')
                license_comment = license_name
                multi_license = ','.join(re.split(r'OR|AND', license_name))
                multi_flag = True
    except Exception as e:
        multi_license = license_name
        logger.warning(f'Fail to parse multi license in npm: {e}')

    return multi_license, license_comment, multi_flag


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
