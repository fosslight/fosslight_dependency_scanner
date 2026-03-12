#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import json
import re
import yaml
import subprocess
from pathlib import Path
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import get_url_to_purl, check_license_name
from fosslight_dependency.dependency_item import DependencyItem, change_dependson_to_purl
from fosslight_util.oss_item import OssItem

logger = logging.getLogger(constant.LOGGER_NAME)


class Pub(PackageManager):
    package_manager_name = const.PUB

    dn_url = 'https://pub.dev/packages/'
    cur_path = ''

    def __init__(self, input_dir, output_dir):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)
        self.pkg_source_list = {}
        self.name_version_dict = {}
        self.pkg_details = {}
        self.append_input_package_list_file(const.SUPPORT_PACKAE.get(self.package_manager_name))

    def __del__(self):
        if self.cur_path != '':
            os.chdir(self.cur_path)

    def run_plugin(self):
        if not os.path.exists(const.SUPPORT_PACKAE.get(self.package_manager_name)):
            logger.error(f"Cannot find the file({const.SUPPORT_PACKAE.get(self.package_manager_name)})")
            return False

        return True

    def parse_pub_deps_file(self, rel_json):
        try:
            for p in rel_json['packages']:
                if p['kind'] == 'root':
                    self.package_name = p['name']
                self.name_version_dict[p['name']] = p['version']

                dep_key = f"{p['name']}({p['version']})"
                self.pkg_source_list[dep_key] = p['source']
                if p['source'] == 'git':
                    desc = p.get('description', {})
                    url = desc.get('url', '') if isinstance(desc, dict) else ''
                    self.pkg_details[dep_key] = {
                        'source': 'git',
                        'url': url
                    }
                elif p['source'] == 'path':
                    desc = p.get('description', {})
                    if isinstance(desc, dict):
                        path = desc.get('path', '')
                    else:
                        path = desc if desc else ''
                    self.pkg_details[dep_key] = {
                        'source': 'path',
                        'path': path
                    }

                if p['dependencies'] == []:
                    continue
                if dep_key not in self.relation_tree:
                    self.relation_tree[dep_key] = []
                self.relation_tree[dep_key].extend(p['dependencies'])

            for i in self.relation_tree:
                tmp_dep = []
                for d in self.relation_tree[i]:
                    d_ver = self.name_version_dict[d]
                    tmp_dep.append(f'{d}({d_ver})')
                self.relation_tree[i] = []
                self.relation_tree[i].extend(tmp_dep)
        except Exception as e:
            logger.error(f'Failed to parse dependency tree: {e}')

    def get_package_info_from_cache(self, package_name, version, pkg_source='hosted', pkg_with_version=None):
        try:
            package_dir = None
            pub_cache_dir = os.environ.get('PUB_CACHE')
            if not pub_cache_dir:
                pub_cache_dir = os.path.join(Path.home(), '.pub-cache')

            if pkg_source == 'hosted':
                package_dir = os.path.join(
                    pub_cache_dir,
                    'hosted',
                    'pub.dev',
                    f'{package_name}-{version}'
                )
                if not os.path.exists(package_dir):
                    package_dir = os.path.join(
                        pub_cache_dir,
                        'hosted',
                        'pub.dartlang.org',
                        f'{package_name}-{version}'
                    )
            elif pkg_source == 'git':
                git_cache_dir = os.path.join(pub_cache_dir, 'git')
                expected_url = ''
                if pkg_with_version and pkg_with_version in self.pkg_details:
                    expected_url = self.pkg_details[pkg_with_version].get('url', '')
                if os.path.exists(git_cache_dir):
                    name_only_match = None
                    for dir_name in os.listdir(git_cache_dir):
                        potential_dir = os.path.join(git_cache_dir, dir_name)
                        if not os.path.isdir(potential_dir):
                            continue
                        pubspec_path = os.path.join(potential_dir, 'pubspec.yaml')
                        if not os.path.exists(pubspec_path):
                            continue
                        try:
                            with open(pubspec_path, 'r', encoding='utf8') as f:
                                pubspec = yaml.safe_load(f)
                                if not pubspec or pubspec.get('name') != package_name:
                                    continue
                            if expected_url:
                                git_config_path = os.path.join(potential_dir, '.git', 'config')
                                remote_url = ''
                                if os.path.exists(git_config_path):
                                    try:
                                        with open(git_config_path, 'r', encoding='utf8') as gc:
                                            for line in gc:
                                                line = line.strip()
                                                if line.startswith('url ='):
                                                    remote_url = line.split('=', 1)[1].strip()
                                                    break
                                    except Exception as e:
                                        logger.debug(f"Failed to read .git/config for {package_name}: {e}")

                                if remote_url and remote_url == expected_url:
                                    package_dir = potential_dir
                                    break
                                else:
                                    if name_only_match is None:
                                        name_only_match = potential_dir
                            else:
                                package_dir = potential_dir
                                break
                        except Exception as e:
                            logger.debug(f"Failed to read pubspec.yaml for {package_name}: {e}")
                            continue

                    # URL 완전 매칭 실패 시 이름만 일치한 디렉터리로 fallback
                    if not package_dir and name_only_match:
                        logger.debug(f"Falling back to name-only match for git package: {package_name}")
                        package_dir = name_only_match
            elif pkg_source == 'path':
                if pkg_with_version and pkg_with_version in self.pkg_details:
                    local_path = self.pkg_details[pkg_with_version].get('path', '')
                    if local_path:
                        if not os.path.isabs(local_path):
                            package_dir = os.path.join(self.input_dir, local_path)
                        else:
                            package_dir = local_path
            if not package_dir or not os.path.exists(package_dir):
                logger.debug(f"Package directory not found in cache: {package_name}-{version} (source: {pkg_source})")
                return None

            result = {}
            pubspec_path = os.path.join(package_dir, 'pubspec.yaml')
            if os.path.exists(pubspec_path):
                with open(pubspec_path, 'r', encoding='utf8') as f:
                    pubspec = yaml.safe_load(f)
                    result['homepage'] = pubspec.get('homepage', '')
                    result['repository'] = pubspec.get('repository', '')

            license_file = os.path.join(package_dir, 'LICENSE')
            if os.path.exists(license_file):
                try:
                    with open(license_file, 'r', encoding='utf8') as lf:
                        result['license_text'] = lf.read()
                except Exception as e:
                    logger.debug(f"Failed to read LICENSE file for {package_name}: {e}")

            return result

        except Exception as e:
            logger.debug(f"Failed to get package info from cache for {package_name}-{version}: {e}")
            return None

    def parse_oss_information(self, f_name=None):  # noqa: ARG002 - kept for API compatibility
        purl_dict = {}

        direct_deps = []
        if self.direct_dep and self.package_name:
            root_version = self.name_version_dict.get(self.package_name)
            if root_version:
                root_key = f"{self.package_name}({root_version})"
                if root_key in self.relation_tree:
                    direct_deps = [dep.split('(')[0] for dep in self.relation_tree[root_key]]

        for pkg_name in self.total_dep_list:
            try:
                version = self.name_version_dict.get(pkg_name)
                if not version:
                    logger.warning(f"Version not found for package: {pkg_name}")
                    continue

                pkg_with_version = f"{pkg_name}({version})"
                pkg_source = self.pkg_source_list.get(pkg_with_version, 'hosted')
                if pkg_source == 'sdk':
                    continue

                dep_item = DependencyItem()
                oss_item = OssItem()

                oss_item.name = f"{self.package_manager_name}:{pkg_name}"
                oss_item.version = version

                cache_info = self.get_package_info_from_cache(pkg_name, version, pkg_source, pkg_with_version)
                if cache_info:
                    oss_item.homepage = cache_info.get('homepage') or cache_info.get('repository') or ''
                    if cache_info.get('license_text'):
                        oss_item.license = check_license_name(cache_info['license_text'])
                else:
                    oss_item.homepage = ''
                if pkg_source == 'hosted':
                    oss_item.download_location = f"{self.dn_url}{pkg_name}/versions/{version}"
                elif pkg_source == 'git':
                    if pkg_with_version in self.pkg_details:
                        oss_item.download_location = self.pkg_details[pkg_with_version].get('url', '')
                    if not oss_item.download_location:
                        oss_item.download_location = oss_item.homepage
                    oss_item.comment = 'git package'
                elif pkg_source == 'path':
                    oss_item.download_location = oss_item.homepage
                    oss_item.comment = 'local path package'
                else:
                    oss_item.download_location = f"{self.dn_url}{pkg_name}/versions/{version}"
                dep_item.purl = get_url_to_purl(f"{self.dn_url}{pkg_name}/versions/{version}", self.package_manager_name)
                purl_dict[pkg_with_version] = dep_item.purl

                if self.direct_dep:
                    if self.package_name and pkg_name == self.package_name:
                        oss_item.comment = 'root package'
                    elif pkg_name in direct_deps:
                        oss_item.comment = 'direct'
                    else:
                        oss_item.comment = 'transitive'

                    if pkg_with_version in self.relation_tree:
                        dep_item.depends_on_raw = self.relation_tree[pkg_with_version]

                dep_item.oss_items.append(oss_item)
                self.dep_items.append(dep_item)

            except Exception as e:
                logger.error(f"Failed to parse package information for {pkg_name}: {e}")

        if self.direct_dep:
            self.dep_items = change_dependson_to_purl(purl_dict, self.dep_items)

        return

    def parse_no_dev_command_file(self, pub_deps):
        for line in pub_deps.split('\n'):
            re_result = re.findall(r'\-\s(\S+)\s', line)
            if re_result:
                self.total_dep_list.append(re_result[0])
        self.total_dep_list = list(set(self.total_dep_list))

    def parse_direct_dependencies(self):
        self.direct_dep = True
        tmp_pub_deps_file = 'tmp_deps.json'
        tmp_no_dev_deps_file = 'tmp_no_dev_deps.txt'
        encoding_list = ['utf8', 'utf16']
        if os.path.exists(tmp_pub_deps_file) and os.path.exists(tmp_no_dev_deps_file):
            for encode in encoding_list:
                try:
                    logger.info(f'Try to encode with {encode}.')
                    with open(tmp_pub_deps_file, 'r+', encoding=encode) as deps_f:
                        lines = deps_f.readlines()
                        deps_f.seek(0)
                        deps_f.truncate()
                        for num, line in enumerate(lines):
                            if line.startswith('{'):
                                first_line = num
                                break
                        deps_f.writelines(lines[first_line:])
                        deps_f.seek(0)
                        deps_l = json.load(deps_f)
                        self.parse_pub_deps_file(deps_l)
                    with open(tmp_no_dev_deps_file, 'r', encoding=encode) as no_dev_f:
                        self.parse_no_dev_command_file(no_dev_f.read())
                    logger.info('Parse tmp pub deps file.')
                except UnicodeDecodeError as e1:
                    logger.info(f'Fail to encode with {encode}: {e1}')
                except Exception as e:
                    logger.error(f'Fail to parse tmp pub deps result file: {e}')
                    return False
                else:
                    logger.info(f'Success to encode with {encode}.')
                    break
        else:
            try:
                cmd = "flutter pub get"
                ret = subprocess.call(cmd, shell=True)
                if ret != 0:
                    logger.error(f"Failed to run: {cmd}")
                    os.chdir(self.cur_path)
                    return False

                cmd = "flutter pub deps --json"
                ret_txt = subprocess.check_output(cmd, text=True, shell=True)
                if ret_txt is not None:
                    deps_l = json.loads(ret_txt)
                    self.parse_pub_deps_file(deps_l)
                else:
                    return False

                cmd = "flutter pub deps --no-dev -s compact"
                ret_no_dev = subprocess.check_output(cmd, text=True, shell=True, encoding='utf8')
                if ret_no_dev:
                    self.parse_no_dev_command_file(ret_no_dev)

            except Exception as e:
                logger.error(f'Fail to run flutter command:{e}')
        return True
