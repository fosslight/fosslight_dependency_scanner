#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import sys
import logging
import platform
import re
import base64
import subprocess
import shutil
import copy
import fosslight_util.constant as constant
import fosslight_dependency.constant as const

try:
    from github import Github
except Exception:
    pass

logger = logging.getLogger(constant.LOGGER_NAME)

# binary url to check license text
_license_scanner_linux = os.path.join('third_party', 'nomos', 'nomossa')
_license_scanner_macos = os.path.join('third_party', 'askalono', 'askalono_macos')
_license_scanner_windows = os.path.join('third_party', 'askalono', 'askalono.exe')

gradle_config = ['runtimeClasspath', 'runtime']
android_config = ['releaseRuntimeClasspath']


class PackageManager:
    input_package_list_file = []
    direct_dep = False
    total_dep_list = []
    direct_dep_list = []

    def __init__(self, package_manager_name, dn_url, input_dir, output_dir):
        self.input_package_list_file = []
        self.direct_dep = False
        self.total_dep_list = []
        self.direct_dep_list = []
        self.package_manager_name = package_manager_name
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.dn_url = dn_url
        self.manifest_file_name = []

        self.platform = platform.system()
        self.license_scanner_bin = check_license_scanner(self.platform)

    def __del__(self):
        self.input_package_list_file = []
        self.direct_dep = False
        self.total_dep_list = []
        self.direct_dep_list = []
        self.package_manager_name = ''
        self.input_dir = ''
        self.output_dir = ''
        self.dn_url = ''
        self.manifest_file_name = []

    def run_plugin(self):
        if self.package_manager_name == const.GRADLE or self.package_manager_name == const.ANDROID:
            self.run_gradle_task()
        else:
            logger.info(f"This package manager({self.package_manager_name}) skips the step to run plugin.")
        return True

    def append_input_package_list_file(self, input_package_file):
        self.input_package_list_file.append(input_package_file)

    def set_manifest_file(self, manifest_file_name):
        self.manifest_file_name = manifest_file_name

    def set_direct_dependencies(self, direct):
        self.direct_dep = direct

    def parse_direct_dependencies(self):
        pass

    def run_gradle_task(self):
        dependency_tree_fname = 'tmp_dependency_tree.txt'
        if os.path.isfile(const.SUPPORT_PACKAE.get(self.package_manager_name)):
            gradle_backup = f'{const.SUPPORT_PACKAE.get(self.package_manager_name)}_bk'

            shutil.copy(const.SUPPORT_PACKAE.get(self.package_manager_name), gradle_backup)
            ret = self.add_allDeps_in_gradle()
            if not ret:
                return

            ret = self.exeucte_gradle_task(dependency_tree_fname)
            if ret != 0:
                self.set_direct_dependencies(False)
                logger.warning("Failed to run allDeps task.")
            else:
                self.parse_dependency_tree(dependency_tree_fname)

            if os.path.isfile(dependency_tree_fname):
                os.remove(dependency_tree_fname)

            if os.path.isfile(gradle_backup):
                os.remove(const.SUPPORT_PACKAE.get(self.package_manager_name))
                shutil.move(gradle_backup, const.SUPPORT_PACKAE.get(self.package_manager_name))

    def add_allDeps_in_gradle(self):
        ret = False
        config = android_config if self.package_manager_name == 'android' else gradle_config
        configuration = ','.join([f'project.configurations.{c}' for c in config])

        allDeps = f'''allprojects {{
                   task allDeps(type: DependencyReportTask) {{
                        doFirst{{
                            try {{
                                configurations = [{configuration}] as Set }}
                            catch(UnknownConfigurationException) {{}}
                        }}
                    }}
                    }}'''
        try:
            with open(const.SUPPORT_PACKAE.get(self.package_manager_name), 'a', encoding='utf8') as f:
                f.write(allDeps)
                ret = True
        except Exception as e:
            logging.warning(f"Cannot add the allDeps task in build.gradle: {e}")

        return ret

    def exeucte_gradle_task(self, dependency_tree_fname):
        if os.path.isfile('gradlew') or os.path.isfile('gradlew.bat'):
            if self.platform == const.WINDOWS:
                cmd_gradle = "gradlew.bat"
            else:
                cmd_gradle = "./gradlew"
        else:
            return 1
        cmd = f"{cmd_gradle} allDeps > {dependency_tree_fname}"

        ret = subprocess.call(cmd, shell=True)
        return ret

    def parse_dependency_tree(self, f_name):
        config = android_config if self.package_manager_name == 'android' else gradle_config
        with open(f_name, 'r', encoding='utf8') as input_fp:
            packages_in_config = False
            for i, line in enumerate(input_fp.readlines()):
                try:
                    line_bk = copy.deepcopy(line)
                    if not packages_in_config:
                        filtered = next(filter(lambda c: re.findall(rf'^{c}\s\-', line), config), None)
                        if filtered:
                            packages_in_config = True
                    else:
                        if line == '':
                            packages_in_config = False
                        re_result = re.findall(r'\-\-\-\s([^\:\s]+\:[^\:\s]+)\:([^\:\s]+)', line)
                        if re_result:
                            self.total_dep_list.append(re_result[0][0])
                            if re.match(r'^[\+|\\]\-\-\-\s([^\:\s]+\:[^\:\s]+)\:([^\:\s]+)', line_bk):
                                self.direct_dep_list.append(re_result[0][0])
                except Exception as e:
                    logger.error(f"Failed to parse dependency tree: {e}")


def version_refine(oss_version):
    version_cmp = oss_version.upper()

    if version_cmp.find(".RELEASE") != -1:
        oss_version = version_cmp.rstrip(".RELEASE")
    elif version_cmp.find(".FINAL") != -1:
        oss_version = version_cmp.rstrip(".FINAL")

    return oss_version


def connect_github(github_token):
    if github_token is not None:
        g = Github(github_token)
    else:
        g = Github()

    return g


def get_github_license(g, github_repo, platform, license_scanner_bin):
    license_name = ''
    tmp_license_txt_file_name = 'tmp_license.txt'

    try:
        repository = g.get_repo(github_repo)
    except Exception:
        logger.info("It cannot find the license name. Please use '-t' option with github token.")
        logger.info("{0}{1}".format("refer:https://docs.github.com/en/github/authenticating-to-github/",
                    "keeping-your-account-and-data-secure/creating-a-personal-access-token"))
        repository = ''

    if repository != '':
        try:
            license_name = repository.get_license().license.spdx_id
            if license_name == "" or license_name == "NOASSERTION":
                try:
                    license_txt_data = base64.b64decode(repository.get_license().content).decode('utf-8')
                    tmp_license_txt = open(tmp_license_txt_file_name, 'w', encoding='utf-8')
                    tmp_license_txt.write(license_txt_data)
                    tmp_license_txt.close()
                    license_name = check_and_run_license_scanner(platform, license_scanner_bin, tmp_license_txt_file_name)
                except Exception:
                    logger.info("Cannot find the license name with license scanner binary.")

                if os.path.isfile(tmp_license_txt_file_name):
                    os.remove(tmp_license_txt_file_name)
        except Exception:
            logger.info("Cannot find the license name with github api.")

    return license_name


def check_license_scanner(platform):
    license_scanner_bin = ''

    if platform == const.LINUX:
        license_scanner = _license_scanner_linux
    elif platform == const.MACOS:
        license_scanner = _license_scanner_macos
    elif platform == const.WINDOWS:
        license_scanner = _license_scanner_windows
    else:
        logger.debug("Not supported OS to analyze license text with binary.")

    if license_scanner:
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.dirname(__file__)

        data_path = os.path.join(base_path, license_scanner)
        license_scanner_bin = data_path

    return license_scanner_bin


def check_and_run_license_scanner(platform, license_scanner_bin, file_dir):
    license_name = ''

    if not license_scanner_bin:
        logger.error('Not supported OS for license scanner binary.')

    try:
        tmp_output_file_name = "tmp_license_scanner_output.txt"

        if file_dir == "UNKNOWN":
            license_name = ""
        else:
            if platform == const.LINUX:
                run_license_scanner = f"{license_scanner_bin} {file_dir} > {tmp_output_file_name}"
            elif platform == const.MACOS:
                run_license_scanner = f"{license_scanner_bin} identify {file_dir} > {tmp_output_file_name}"
            elif platform == const.WINDOWS:
                run_license_scanner = f"{license_scanner_bin} identify {file_dir} > {tmp_output_file_name}"
            else:
                run_license_scanner = ''

            if run_license_scanner is None:
                license_name = ""
                return license_name
            else:
                ret = subprocess.run(run_license_scanner, shell=True, stderr=subprocess.PIPE)
                if ret.returncode != 0 or ret.stderr:
                    os.remove(tmp_output_file_name)
                    return ""

            fp = open(tmp_output_file_name, "r", encoding='utf8')
            license_output = fp.read()
            fp.close()

            if platform == const.LINUX:
                license_output_re = re.findall(r'.*contains license\(s\)\s(.*)', license_output)
            else:
                license_output_re = re.findall(r"License:\s{1}(\S*)\s{1}", license_output)

            if len(license_output_re) == 1:
                license_name = license_output_re[0]
                if license_name == "No_license_found":
                    license_name = ""
            else:
                license_name = ""
            os.remove(tmp_output_file_name)

    except Exception as ex:
        logger.error(f"Failed to run license scan binary. {ex}")
        license_name = ""

    return license_name
