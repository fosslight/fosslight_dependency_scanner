#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import subprocess
import shutil
from bs4 import BeautifulSoup as bs
from defusedxml.ElementTree import parse
import re
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import version_refine, get_url_to_purl, change_file_mode
from fosslight_dependency.dependency_item import DependencyItem, change_dependson_to_purl
from fosslight_util.oss_item import OssItem

logger = logging.getLogger(constant.LOGGER_NAME)


class Maven(PackageManager):
    package_manager_name = const.MAVEN

    dn_url = 'https://mvnrepository.com/artifact/'
    input_file_name = os.path.join('target', 'generated-resources', 'licenses.xml')
    is_run_plugin = False
    output_custom_dir = ''

    def __init__(self, input_dir, output_dir, output_custom_dir):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)
        self.is_run_plugin = False

        if output_custom_dir:
            self.output_custom_dir = output_custom_dir
            self.input_file_name = os.path.join(output_custom_dir, os.sep.join(self.input_file_name.split(os.sep)[1:]))

        self.append_input_package_list_file(self.input_file_name)

    def __del__(self):
        if self.is_run_plugin:
            self.clean_run_maven_plugin_output()

    def run_plugin(self):
        ret = True

        if not os.path.isfile(self.input_file_name):
            self.is_run_plugin = True
            pom_backup = 'pom.xml_backup'

            ret = self.add_plugin_in_pom(pom_backup)
            if ret:
                self.run_maven_plugin()

            if os.path.isfile(pom_backup):
                shutil.move(pom_backup, const.SUPPORT_PACKAE.get(self.package_manager_name))
        else:
            self.set_direct_dependencies(False)

        return ret

    def add_plugin_in_pom(self, pom_backup):
        ret = False
        xml = 'xml'

        manifest_file = const.SUPPORT_PACKAE.get(self.package_manager_name)
        if os.path.isfile(manifest_file) != 1:
            logger.error(f"{manifest_file} is not existed in this directory.")
            return ret

        try:
            shutil.move(manifest_file, pom_backup)

            license_maven_plugin = '<plugin>\
                                            <groupId>org.codehaus.mojo</groupId>\
                                            <artifactId>license-maven-plugin</artifactId>\
                                            <version>2.0.0</version>\
                                            <executions>\
                                                <execution>\
                                                    <id>aggregate-download-licenses</id>\
                                                    <goals>\
                                                        <goal>aggregate-download-licenses</goal>\
                                                    </goals>\
                                                </execution>\
                                            </executions>\
                                            <configuration>\
                                                <excludedScopes>test</excludedScopes>\
                                            </configuration>\
                                        </plugin>'

            tmp_plugin = bs(license_maven_plugin, xml)

            license_maven_plugins = f"<plugins>{license_maven_plugin}<plugins>"
            tmp_plugins = bs(license_maven_plugins, xml)

            with open(pom_backup, 'r', encoding='utf8') as f:
                f_xml = f.read()
                f_content = bs(f_xml, xml)

                build = f_content.find('build')
                if build is not None:
                    plugins = build.find('plugins')
                    if plugins is not None:
                        plugins.append(tmp_plugin.plugin)
                        ret = True
                    else:
                        build.append(tmp_plugins.plugins)
                        ret = True
        except Exception as e:
            ret = False
            logger.error(f"Failed to add plugin in pom : {e}")

        if ret:
            with open(manifest_file, "w", encoding='utf8') as f_w:
                f_w.write(f_content.prettify(formatter="minimal").encode().decode('utf-8'))

        return ret

    def clean_run_maven_plugin_output(self):
        directory_name = os.path.dirname(self.input_file_name)
        licenses_path = os.path.join(directory_name, 'licenses')
        if os.path.isdir(directory_name):
            if os.path.isdir(licenses_path):
                shutil.rmtree(licenses_path)
                os.remove(self.input_file_name)

            if len(os.listdir(directory_name)) == 0:
                shutil.rmtree(directory_name)

        top_path = self.input_file_name.split(os.sep)[0]
        if len(os.listdir(top_path)) == 0:
            shutil.rmtree(top_path)

    def run_maven_plugin(self):
        logger.info('Run maven license scanning plugin with temporary pom.xml')
        current_mode = ''
        if os.path.isfile('mvnw') or os.path.isfile('mvnw.cmd'):
            if self.platform == const.WINDOWS:
                cmd_mvn = "mvnw.cmd"
            else:
                cmd_mvn = "./mvnw"
            current_mode = change_file_mode(cmd_mvn)
        else:
            cmd_mvn = "mvn"
        cmd = f"{cmd_mvn} license:aggregate-download-licenses"

        ret = subprocess.call(cmd, shell=True)
        if ret != 0:
            logger.error(f"Failed to run maven plugin: {cmd}")

        cmd = f"{cmd_mvn} dependency:tree"
        try:
            ret_txt = subprocess.check_output(cmd, text=True, shell=True)
            if ret_txt is not None:
                self.parse_dependency_tree(ret_txt)
                self.set_direct_dependencies(True)
            else:
                logger.error(f"Failed to run: {cmd}")
                self.set_direct_dependencies(False)
        except Exception as e:
            logger.error(f"Failed to run '{cmd}': {e}")
            self.set_direct_dependencies(False)
        if current_mode:
            change_file_mode(cmd_mvn, current_mode)

    def create_dep_stack(self, dep_line):
        dep_stack = []
        cur_flag = ''
        dep_level = -1
        dep_level_plus = False
        for line in dep_line.split('\n'):
            try:
                if not re.search(r'[.*INFO.*]', line):
                    continue
                if len(line) <= 7:
                    continue
                line = line[7:]

                prev_flag = cur_flag
                prev_dep_level = dep_level
                dep_level = line.count("|")

                re_result = re.findall(r'([\+|\\]\-)\s([^\:\s]+\:[^\:\s]+)\:(?:[^\:\s]+)\:([^\:\s]+)\:([^\:\s]+)', line)
                if re_result:
                    cur_flag = re_result[0][0]
                    if (prev_flag == '\\-') and (prev_dep_level == dep_level):
                        dep_level_plus = True
                    if dep_level_plus and (prev_flag == '\\-') and (prev_dep_level != dep_level):
                        dep_level_plus = False
                    if dep_level_plus:
                        dep_level += 1
                    if re_result[0][3] == 'test':
                        continue
                    dep_name = f'{re_result[0][1]}({re_result[0][2]})'
                    dep_stack = dep_stack[:dep_level] + [dep_name]
                    yield dep_stack[:dep_level], dep_name
                else:
                    cur_flag = ''
            except Exception as e:
                logger.warning(f"Failed to parse dependency tree: {e}")

    def parse_dependency_tree(self, f_name):
        try:
            for stack, name in self.create_dep_stack(f_name):
                if len(stack) == 0:
                    self.direct_dep_list.append(name)
                else:
                    if stack[-1] not in self.relation_tree:
                        self.relation_tree[stack[-1]] = []
                    self.relation_tree[stack[-1]].append(name)
        except Exception as e:
            logger.warning(f'Fail to parse maven dependency tree:{e}')

    def parse_oss_information(self, f_name):
        with open(f_name, 'r', encoding='utf8') as input_fp:
            tree = parse(input_fp)

        root = tree.getroot()
        dependencies = root.find("dependencies")
        purl_dict = {}

        for d in dependencies.iter("dependency"):
            dep_item = DependencyItem()
            oss_item = OssItem()
            groupid = d.findtext("groupId")
            artifactid = d.findtext("artifactId")
            version = d.findtext("version")
            oss_item.version = version_refine(version)

            oss_item.name = f"{groupid}:{artifactid}"
            oss_item.download_location = f"{self.dn_url}{groupid}/{artifactid}/{version}"
            oss_item.homepage = f"{self.dn_url}{groupid}/{artifactid}"
            dep_item.purl = get_url_to_purl(oss_item.download_location, self.package_manager_name)
            purl_dict[f'{oss_item.name}({oss_item.version})'] = dep_item.purl

            licenses = d.find("licenses")
            if len(licenses):
                license_names = []
                for key_license in licenses.iter("license"):
                    if key_license.findtext("name") is not None:
                        license_names.append(key_license.findtext("name").replace(",", ""))
                oss_item.license = ', '.join(license_names)

            dep_key = f"{oss_item.name}({version})"

            if self.direct_dep:
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
