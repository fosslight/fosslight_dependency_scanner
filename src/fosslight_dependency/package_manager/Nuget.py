#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2022 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import logging
import re
import os
import subprocess
from defusedxml.ElementTree import parse, fromstring
import json
import requests
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import check_license_name, get_url_to_purl
from fosslight_dependency.dependency_item import DependencyItem, change_dependson_to_purl
from fosslight_util.oss_item import OssItem

logger = logging.getLogger(constant.LOGGER_NAME)


class Nuget(PackageManager):
    package_manager_name = const.NUGET

    dn_url = "https://nuget.org/packages/"
    packageReference = False
    directory_packages_props = 'Directory.Packages.props'
    nuget_api_url = 'https://api.nuget.org/v3-flatcontainer/'
    dotnet_ver = []
    _exclude_dirs = {"test", "tests", "sample", "samples", "example", "examples"}

    def __init__(self, input_dir, output_dir):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)

        for manifest_i in const.SUPPORT_PACKAE.get(self.package_manager_name):
            if os.path.exists(os.path.basename(manifest_i)):
                self.append_input_package_list_file(os.path.basename(manifest_i))
                if manifest_i != 'packages.config':
                    self.packageReference = True

    def run_plugin(self):
        ret = True
        directory_packages_props_path = os.path.join(self.input_dir, self.directory_packages_props)
        if not os.path.isfile(directory_packages_props_path):
            return ret

        logger.info(f"Found {self.directory_packages_props}. Using NuGet CPM flow.")
        self.packageReference = True

        restore_targets = self._find_restore_targets()
        if restore_targets:
            logger.info("Found .sln or .csproj files. Running 'dotnet restore'...")
            for target_path, target_file in restore_targets:
                logger.info(f"Restoring: {os.path.relpath(target_file, self.input_dir)}")
                try:
                    result = subprocess.run(
                        ['dotnet', 'restore', target_file, '/p:EnableWindowsTargeting=true'],
                        cwd=target_path,
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    if result.returncode == 0:
                        logger.info(f"Successfully restored {os.path.relpath(target_file, self.input_dir)}")
                    else:
                        logger.warning(f"'dotnet restore' failed for {target_file} with return code {result.returncode}")
                        if result.stderr:
                            logger.warning(result.stderr)
                except FileNotFoundError:
                    logger.error("'dotnet' command not found. Please install .NET SDK.")
                except subprocess.TimeoutExpired:
                    logger.warning(f"'dotnet restore' timed out for {target_file}.")
                except Exception as e:
                    logger.warning(f"Failed to run 'dotnet restore' for {target_file}: {e}")
        else:
            logger.warning("No .sln or .csproj files found to restore.")

        self.project_dirs = []
        found_projects = False

        for root, dirs, files in os.walk(self.input_dir):
            rel_root = os.path.relpath(root, self.input_dir)
            parts = rel_root.split(os.sep) if rel_root != os.curdir else []
            if any(p.lower() in self._exclude_dirs for p in parts):
                continue
            assets_json = os.path.join(root, 'obj', 'project.assets.json')
            if os.path.isfile(assets_json):
                found_projects = True

                rel_path = os.path.relpath(assets_json, self.input_dir)
                logger.info(f"Found project.assets.json at: {rel_path}")

                if rel_path not in self.input_package_list_file:
                    self.append_input_package_list_file(rel_path)

                project_dir = os.path.dirname(assets_json)
                if project_dir.endswith(os.sep + 'obj'):
                    project_dir = project_dir[: -len(os.sep + 'obj')]

                if project_dir and project_dir not in self.project_dirs:
                    self.project_dirs.append(project_dir)

        if not found_projects:
            logger.warning(
                "Directory.Packages.props found and 'dotnet restore' completed, "
                "but no obj/project.assets.json files were discovered."
            )

        return ret

    def parse_oss_information(self, f_name):
        tmp_license_txt_file_name = 'tmp_license.txt'
        if f_name == self.directory_packages_props:
            return

        relation_tree = {}
        direct_dep_list = []
        if not hasattr(self, 'global_purl_dict'):
            self.global_purl_dict = {}
        if not hasattr(self, 'processed_packages'):
            self.processed_packages = {}

        file_path = os.path.join(self.input_dir, f_name) if not os.path.isabs(f_name) else f_name
        with open(file_path, 'r', encoding='utf8') as input_fp:
            package_list = []
            if self.packageReference:
                package_list = self.get_package_info_in_packagereference(input_fp, relation_tree, direct_dep_list)
            else:
                package_list = self.get_package_list_in_packages_config(input_fp)

        for oss_origin_name, oss_version in package_list:
            try:
                pkg_key = f'{oss_origin_name}({oss_version})'
                if pkg_key in self.processed_packages:
                    existing_idx = self.processed_packages[pkg_key]
                    existing_dep_item = self.dep_items[existing_idx]

                    if pkg_key in relation_tree:
                        new_deps = relation_tree[pkg_key]
                        if existing_dep_item.depends_on_raw:
                            existing_deps_set = set(existing_dep_item.depends_on_raw)
                            new_deps_set = set(new_deps)
                            merged_deps = sorted(existing_deps_set | new_deps_set)
                            existing_dep_item.depends_on_raw = merged_deps
                        else:
                            existing_dep_item.depends_on_raw = new_deps
                    if self.direct_dep and self.packageReference:
                        if oss_origin_name in direct_dep_list:
                            if 'direct' not in existing_dep_item.oss_items[0].comment:
                                existing_dep_item.oss_items[0].comment = 'direct'
                    continue

                dep_item = DependencyItem()
                oss_item = OssItem()
                oss_item.name = f'{self.package_manager_name}:{oss_origin_name}'
                oss_item.version = oss_version

                license_name = ''
                response = requests.get(f'{self.nuget_api_url.lower()}{oss_origin_name.lower()}/'
                                        f'{oss_item.version.lower()}/{oss_origin_name.lower()}.nuspec')
                if response.status_code == 200:
                    root = fromstring(response.text)
                    xmlns = ''
                    m = re.search('{.*}', root.tag)
                    if m:
                        xmlns = m.group(0)
                    nupkg_metadata = root.find(f'{xmlns}metadata')

                    license_name_id = nupkg_metadata.find(f'{xmlns}license')
                    if license_name_id is not None:
                        license_name, license_comment = self.check_multi_license(license_name_id.text)
                        if license_comment != '':
                            oss_item.comment = license_comment
                    else:
                        license_url = nupkg_metadata.find(f'{xmlns}licenseUrl')
                        if license_url is not None:
                            url_res = requests.get(license_url.text)
                            if url_res.status_code == 200:
                                license_name_with_scanner = check_license_name(url_res.text)
                                if license_name_with_scanner != "":
                                    license_name = license_name_with_scanner
                                else:
                                    license_name = license_url.text
                    oss_item.license = license_name
                    repo_id = nupkg_metadata.find(f'{xmlns}repository')
                    if repo_id is not None:
                        oss_item.download_location = repo_id.get("url")
                    else:
                        proj_url_id = nupkg_metadata.find(f'{xmlns}projectUrl')
                        if proj_url_id is not None:
                            oss_item.download_location = proj_url_id.text
                    oss_item.homepage = f'{self.dn_url}{oss_origin_name}'
                    if not oss_item.download_location:
                        oss_item.download_location = f'{oss_item.homepage}/{oss_item.version}'
                    else:
                        if oss_item.download_location.endswith('.git'):
                            oss_item.download_location = oss_item.download_location[:-4]
                    dep_item.purl = get_url_to_purl(f'{oss_item.homepage}/{oss_item.version}', self.package_manager_name)
                else:
                    oss_item.comment = 'Fail to response for nuget api'
                    dep_item.purl = f'pkg:nuget/{oss_origin_name}@{oss_item.version}'
                self.global_purl_dict[f'{oss_origin_name}({oss_item.version})'] = dep_item.purl

                if self.direct_dep and self.packageReference:
                    if oss_origin_name in direct_dep_list:
                        oss_item.comment = 'direct'
                    else:
                        oss_item.comment = 'transitive'

                    key = f'{oss_origin_name}({oss_item.version})'
                    if key in relation_tree:
                        dep_item.depends_on_raw = relation_tree[key]

                dep_item.oss_items.append(oss_item)
                self.dep_items.append(dep_item)
                self.processed_packages[pkg_key] = len(self.dep_items) - 1

            except Exception as e:
                logger.warning(f"Failed to parse oss information: {e}")
        if self.direct_dep:
            self.dep_items = change_dependson_to_purl(self.global_purl_dict, self.dep_items)

        if os.path.isfile(tmp_license_txt_file_name):
            os.remove(tmp_license_txt_file_name)

        return

    def get_package_list_in_packages_config(self, input_fp):
        package_list = []
        root = parse(input_fp).getroot()
        for p in root.findall("package"):
            package_list.append([p.get("id"), p.get("version")])
        return package_list

    def get_package_info_in_packagereference(self, input_fp, relation_tree, direct_dep_list):
        json_f = json.load(input_fp)

        dotnet_ver = self.get_dotnet_ver_list(json_f)
        package_list = self.get_package_list_in_packages_assets(json_f)
        self.get_dependency_tree(json_f, relation_tree, dotnet_ver)
        self.get_direct_dependencies_from_assets_json(json_f, direct_dep_list)
        self.get_direct_package_in_packagereference(direct_dep_list)

        return package_list

    def get_package_list_in_packages_assets(self, json_f):
        package_list = []
        for item in json_f['libraries']:
            if json_f['libraries'][item]['type'] == 'package':
                oss_info = item.split('/')
                package_list.append([oss_info[0], oss_info[1]])
        return package_list

    def get_dotnet_ver_list(self, json_f):
        dotnet_ver = []
        json_project_group = json_f['projectFileDependencyGroups']
        for ver in json_project_group:
            dotnet_ver.append(ver)
        return dotnet_ver

    def get_direct_dependencies_from_assets_json(self, json_f, direct_dep_list):
        try:
            json_project_group = json_f.get('projectFileDependencyGroups', {})
            for _, dependencies in json_project_group.items():
                if not dependencies:
                    continue
                for dep_string in dependencies:
                    package_name = dep_string.split()[0] if dep_string else ''
                    if package_name and package_name not in direct_dep_list:
                        direct_dep_list.append(package_name)
        except Exception as e:
            logger.warning(f"Failed to extract direct dependencies from project.assets.json: {e}")

    def get_dependency_tree(self, json_f, relation_tree, dotnet_ver):
        actual_versions = {}
        for lib_key in json_f.get('libraries', {}):
            if '/' in lib_key:
                lib_name, lib_version = lib_key.split('/', 1)
                actual_versions[lib_name.lower()] = lib_version

        json_target = json_f['targets']
        for item in json_target:
            if item not in dotnet_ver:
                continue
            json_item = json_target[item]
            for pkg in json_item:
                json_pkg = json_item[pkg]
                if 'type' not in json_pkg:
                    continue
                if 'dependencies' not in json_pkg:
                    continue
                if json_pkg['type'] != 'package':
                    continue
                oss_info = pkg.split('/')
                relation_tree[f'{oss_info[0]}({oss_info[1]})'] = []
                for dep in json_pkg['dependencies']:
                    oss_name = dep
                    dep_ver_in_spec = json_pkg['dependencies'][dep]
                    actual_ver = actual_versions.get(oss_name.lower(), dep_ver_in_spec)
                    relation_tree[f'{oss_info[0]}({oss_info[1]})'].append(f'{oss_name}({actual_ver})')

    def get_direct_package_in_packagereference(self, direct_dep_list):
        if hasattr(self, 'project_dirs') and self.project_dirs:
            for project_dir in self.project_dirs:
                for f in os.listdir(project_dir):
                    f_path = os.path.join(project_dir, f)
                    if os.path.isfile(f_path) and ((f.split('.')[-1] == 'csproj') or (f.split('.')[-1] == 'xproj')):
                        with open(f_path, 'r', encoding='utf8') as input_fp:
                            root = parse(input_fp).getroot()
                        itemgroups = root.findall('ItemGroup')
                        for itemgroup in itemgroups:
                            for item in itemgroup.findall('PackageReference'):
                                pkg_name = item.get('Include')
                                if pkg_name and pkg_name not in direct_dep_list:
                                    direct_dep_list.append(pkg_name)
        else:
            for f in os.listdir(self.input_dir):
                f_path = os.path.join(self.input_dir, f)
                if os.path.isfile(f_path) and ((f.split('.')[-1] == 'csproj') or (f.split('.')[-1] == 'xproj')):
                    with open(f_path, 'r', encoding='utf8') as input_fp:
                        root = parse(input_fp).getroot()
                    itemgroups = root.findall('ItemGroup')
                    for itemgroup in itemgroups:
                        for item in itemgroup.findall('PackageReference'):
                            pkg_name = item.get('Include')
                            if pkg_name and pkg_name not in direct_dep_list:
                                direct_dep_list.append(pkg_name)

    def check_multi_license(self, license_name):
        multi_license = license_name
        license_comment = ''
        try:
            if license_name.startswith('(') and license_name.endswith(')'):
                license_name = license_name.lstrip('(').rstrip(')')
                license_comment = license_name
                multi_license = ','.join(re.split(r'OR|AND', license_name))
        except Exception as e:
            logger.warning(f'Fail to parse multi license in npm: {e}')

        return multi_license, license_comment

    def _find_restore_targets(self):
        sln_files = []
        csproj_files = []

        for root, dirs, files in os.walk(self.input_dir):
            rel_root = os.path.relpath(root, self.input_dir)
            parts = rel_root.split(os.sep) if rel_root != os.curdir else []
            if any(p.lower() in self._exclude_dirs for p in parts):
                continue

            depth = len(parts) if parts and parts[0] != '.' else 0

            for f in files:
                if f.endswith('.sln'):
                    sln_files.append((depth, root, os.path.join(root, f)))
                elif f.endswith('.csproj'):
                    csproj_files.append((depth, root, os.path.join(root, f)))

        result = []
        if sln_files:
            result.extend([(d, f) for _, d, f in sln_files])

        if csproj_files:
            result.extend([(d, f) for _, d, f in csproj_files])

        return result
