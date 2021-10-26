#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import subprocess
import shutil
from bs4 import BeautifulSoup as bs
from xml.etree.ElementTree import parse
import re
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import version_refine

logger = logging.getLogger(constant.LOGGER_NAME)


class Maven(PackageManager):
    package_manager_name = const.MAVEN

    dn_url = 'https://mvnrepository.com/artifact/'
    input_file_name = os.path.join('target', 'generated-resources', 'licenses.xml')
    is_run_plugin = False
    output_custom_dir = ''
    dependency_tree = {}

    def __init__(self, input_dir, output_dir, output_custom_dir):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)

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

        return ret

    def add_plugin_in_pom(self, pom_backup):
        ret = False
        xml = 'xml'

        manifest_file = const.SUPPORT_PACKAE.get(self.package_manager_name)
        if os.path.isfile(manifest_file) != 1:
            logger.error(manifest_file + " is not existed in this directory.")
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

            license_maven_plugins = '<plugins>' + license_maven_plugin + '<plugins>'
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
            logger.error('Failed to add plugin in pom' + str(e))

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
        dependency_tree_fname = 'tmp_dependency_tree.txt'

        logger.info('Run maven license scanning plugin with temporary pom.xml')
        if os.path.isfile('mvnw') or os.path.isfile('mvnw.cmd'):
            if self.platform == const.WINDOWS:
                cmd_mvn = "mvnw.cmd"
            else:
                cmd_mvn = "./mvnw"
        else:
            cmd_mvn = "mvn"
        cmd = cmd_mvn + " license:aggregate-download-licenses"

        ret = subprocess.call(cmd, shell=True)
        if ret != 0:
            logger.error("Failed to run maven plugin: " + cmd)

        cmd = cmd_mvn + " dependency:tree > " + dependency_tree_fname
        ret = subprocess.call(cmd, shell=True)
        if ret != 0:
            logger.error("Failed to run: " + cmd)
        else:
            self.parse_dependency_tree(dependency_tree_fname)
            os.remove(dependency_tree_fname)

    def parse_dependency_tree(self, f_name):
        with open(f_name, 'r', encoding='utf8') as input_fp:
            for i, line in enumerate(input_fp.readlines()):
                try:
                    re_result = re.findall(r'[\+|\\]\-\s([^\:\s]+\:[^\:\s]+)\:(?:[^\:\s]+)\:([^\:\s]+)\:([^\:\s]+)', line)
                    if re_result:
                        dependency_key = re_result[0][0] + ':' + re_result[0][1]
                        self.dependency_tree[dependency_key] = re_result[0][2]
                except Exception as e:
                    logger.error("Failed to parse dependency tree: " + str(e))

    def parse_oss_information(self, f_name):
        with open(f_name, 'r', encoding='utf8') as input_fp:
            tree = parse(input_fp)

        root = tree.getroot()
        dependencies = root.find("dependencies")

        sheet_list = []

        for d in dependencies.iter("dependency"):
            groupid = d.findtext("groupId")
            artifactid = d.findtext("artifactId")
            version = d.findtext("version")
            oss_version = version_refine(version)

            oss_name = groupid + ":" + artifactid
            dn_loc = self.dn_url + groupid + "/" + artifactid + "/" + version
            homepage = self.dn_url + groupid + "/" + artifactid

            licenses = d.find("licenses")
            if len(licenses):
                license_names = []
                for key_license in licenses.iter("license"):
                    if key_license.findtext("name") is not None:
                        license_names.append(key_license.findtext("name").replace(",", ""))
                license_name = ', '.join(license_names)
            else:
                # Case that doesn't include License tag value.
                license_name = ''

            try:
                comment = ''
                dependency_tree_key = oss_name + ':' + version
                if dependency_tree_key in self.dependency_tree.keys():
                    comment = self.dependency_tree[dependency_tree_key]
            except Exception as e:
                logger.error("Fail to find oss scope in dependency tree: " + str(e))

            sheet_list.append([const.SUPPORT_PACKAE.get(self.package_manager_name),
                              oss_name, oss_version, license_name, dn_loc, homepage, '', '', comment])

        return sheet_list
