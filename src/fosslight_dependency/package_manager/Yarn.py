#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2025 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import subprocess
import json
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency.package_manager.Npm import Npm
from fosslight_dependency.dependency_item import DependencyItem, change_dependson_to_purl
from fosslight_util.oss_item import OssItem
from fosslight_dependency._package_manager import get_url_to_purl
from fosslight_dependency.package_manager.Npm import check_multi_license, check_unknown_license

logger = logging.getLogger(constant.LOGGER_NAME)


class Yarn(Npm):

    def __init__(self, input_dir, output_dir):
        super().__init__(input_dir, output_dir)
        self.package_manager_name = const.YARN
        self.yarn_version = None

    def detect_yarn_version(self):
        """Detect Yarn version (1.x = Classic, 2+ = Berry)"""
        if self.yarn_version is not None:
            return self.yarn_version

        try:
            result = subprocess.run('yarn -v', shell=True, capture_output=True, text=True, encoding='utf-8')
            if result.returncode == 0:
                version_str = result.stdout.strip()
                major_version = int(version_str.split('.')[0])
                self.yarn_version = major_version
                logger.info(f"Detected Yarn version: {version_str} (major: {major_version})")
                return major_version
        except Exception as e:
            logger.warning(f"Failed to detect Yarn version: {e}")
        return None

    def start_license_checker(self):
        ret = True
        license_checker_cmd = f'license-checker --production --json --out {self.input_file_name}'
        custom_path_option = ' --customPath '
        node_modules = 'node_modules'

        self.detect_yarn_version()

        # For Yarn Berry (2+), check if using PnP mode
        is_pnp_mode = False
        if self.yarn_version and self.yarn_version >= 2:
            # Check if .pnp.cjs exists (PnP mode indicator)
            if os.path.exists('.pnp.cjs') or os.path.exists('.pnp.js'):
                is_pnp_mode = True
                logger.info("Detected Yarn Berry with PnP mode")

        if not os.path.isdir(node_modules):
            logger.info("node_modules directory does not exist.")
            self.flag_tmp_node_modules = True

            # For PnP mode, try to force node_modules creation
            if is_pnp_mode:
                logger.info("Attempting to create node_modules for PnP project...")
                yarn_install_cmd = 'YARN_NODE_LINKER=node-modules yarn install --production --ignore-scripts'
                logger.info(f"Executing: {yarn_install_cmd}")
            else:
                yarn_install_cmd = 'yarn install --production --ignore-scripts'
                logger.info(f"Executing: {yarn_install_cmd}")

            cmd_ret = subprocess.call(yarn_install_cmd, shell=True)
            if cmd_ret != 0:
                logger.error(f"{yarn_install_cmd} failed")
                if is_pnp_mode:
                    logger.error("Yarn Berry PnP mode detected. Consider setting 'nodeLinker: node-modules' in .yarnrc.yml")
                return False
            else:
                logger.info(f"Successfully executed {yarn_install_cmd}")

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
            oss_item.name = f'{const.NPM}:{oss_init_name}'

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
            dep_item.purl = get_url_to_purl(oss_item.download_location, self.package_manager_name)
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

            # For Yarn, use 'package.json' instead of yarn.lock for license info
            manifest_file_path = os.path.join(package_path, 'package.json')
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

    def parse_rel_dependencies(self, rel_name, rel_ver, rel_dependencies):
        """Override to handle missing packages and packages without version"""
        _dependencies = 'dependencies'
        _version = 'version'
        _peer = 'peerMissing'
        _missing = 'missing'

        for rel_dep_name in rel_dependencies.keys():
            # Optional, non-installed dependencies are listed as empty objects
            if rel_dependencies[rel_dep_name] == {}:
                continue
            if _peer in rel_dependencies[rel_dep_name]:
                if rel_dependencies[rel_dep_name][_peer]:
                    continue
            # Skip missing packages (not installed)
            if _missing in rel_dependencies[rel_dep_name]:
                if rel_dependencies[rel_dep_name][_missing]:
                    continue
            # Skip if version key doesn't exist
            if _version not in rel_dependencies[rel_dep_name]:
                continue

            if f'{rel_name}({rel_ver})' not in self.relation_tree:
                self.relation_tree[f'{rel_name}({rel_ver})'] = []
            elif f'{rel_dep_name}({rel_dependencies[rel_dep_name][_version]})' in self.relation_tree[f'{rel_name}({rel_ver})']:
                continue
            self.relation_tree[f'{rel_name}({rel_ver})'].append(f'{rel_dep_name}({rel_dependencies[rel_dep_name][_version]})')
            if _dependencies in rel_dependencies[rel_dep_name]:
                self.parse_rel_dependencies(rel_dep_name, rel_dependencies[rel_dep_name][_version],
                                            rel_dependencies[rel_dep_name][_dependencies])

    def parse_direct_dependencies(self):
        if not self.direct_dep:
            return
        try:
            # For Yarn, check if package.json exists (not yarn.lock)
            # input_package_list_file[0] is the license-checker output file path
            manifest_dir = os.path.dirname(self.input_package_list_file[0])
            package_json_path = os.path.join(manifest_dir, 'package.json')

            if os.path.isfile(package_json_path):
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
