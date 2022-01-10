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
import fosslight_util.constant as constant
import fosslight_dependency.constant as const

try:
    from github import Github
except Exception:
    pass

logger = logging.getLogger(constant.LOGGER_NAME)

# binary url to check license text
_license_scanner_linux = "third_party/nomos/nomossa"
_license_scanner_macos = "third_party/askalono/askalono_macos"
_license_scanner_windows = "third_party\\askalono\\askalono.exe"


class PackageManager:
    input_package_list_file = []

    def __init__(self, package_manager_name, dn_url, input_dir, output_dir):
        self.input_package_list_file = []
        self.package_manager_name = package_manager_name
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.dn_url = dn_url
        self.manifest_file_name = []

        self.platform = platform.system()
        self.license_scanner_bin = check_license_scanner(self.platform)

    def run_plugin(self):
        logger.info('This package manager(' + self.package_manager_name + ') skips the step to run plugin.')
        return True

    def append_input_package_list_file(self, input_package_file):
        self.input_package_list_file.append(input_package_file)

    def set_manifest_file(self, manifest_file_name):
        self.manifest_file_name = manifest_file_name


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
                run_license_scanner = license_scanner_bin + " " + file_dir + " > " + tmp_output_file_name
            elif platform == const.MACOS:
                run_license_scanner = license_scanner_bin + " identify " + file_dir + " > " + tmp_output_file_name
            elif platform == const.WINDOWS:
                run_license_scanner = license_scanner_bin + " identify " + file_dir + " > " + tmp_output_file_name
            else:
                run_license_scanner = ''

            if run_license_scanner is None:
                license_name = ""
                return license_name
            else:
                ret = os.system(run_license_scanner)
                if ret != 0:
                    logger.info("=> (No error) This is the information that the license was not found.")
                    return ""

            fp = open(tmp_output_file_name, "r", encoding='utf8')
            license_output = fp.read()
            fp.close()
            os.remove(tmp_output_file_name)

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

    except Exception as ex:
        logger.error("Failed to run license scan binary." + str(ex))
        license_name = ""

    return license_name
