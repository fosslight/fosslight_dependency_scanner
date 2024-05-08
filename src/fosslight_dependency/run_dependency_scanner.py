#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2020 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import platform
import sys
import argparse
import pkg_resources
import warnings
from datetime import datetime
import logging
import fosslight_dependency.constant as const
from collections import defaultdict
from fosslight_util.set_log import init_log
import fosslight_util.constant as constant
from fosslight_dependency._help import print_help_msg
from fosslight_dependency._analyze_dependency import analyze_dependency
from fosslight_util.output_format import check_output_format, write_output_file
if platform.system() != 'Windows':
    from fosslight_util.write_spdx import write_spdx
from fosslight_util.cover import CoverItem

# Package Name
_PKG_NAME = "fosslight_dependency"
logger = logging.getLogger(constant.LOGGER_NAME)
warnings.filterwarnings("ignore", category=FutureWarning)
_sheet_name = "DEP_FL_Dependency"
EXTENDED_HEADER = {_sheet_name: ['ID', 'purl', 'OSS Name',
                                       'OSS Version', 'License', 'Download Location',
                                       'Homepage', 'Copyright Text', 'Exclude',
                                       'Comment', 'Depends On']}
CUSTOMIZED_FORMAT = {'excel': '.xlsx', 'csv': '.csv', 'opossum': '.json', 'yaml': '.yaml',
                     'spdx-yaml': '.yaml', 'spdx-json': '.json', 'spdx-xml': '.xml',
                     'spdx-tag': '.tag'}
_exclude_dir = ['node_moduels', 'venv']


def find_package_manager(input_dir):
    ret = True
    manifest_file_name = []
    for value in const.SUPPORT_PACKAE.values():
        if isinstance(value, list):
            manifest_file_name.extend(value)
        else:
            manifest_file_name.append(value)

    found_manifest_file = []
    for (parent, _, files) in os.walk(input_dir):
        if len(files) < 1:
            continue
        if os.path.basename(parent) in _exclude_dir:
            continue
        for file in files:
            if file in manifest_file_name:
                found_manifest_file.append(file)
        if len(found_manifest_file) > 0:
            input_dir = parent
            break
    found_package_manager = defaultdict(list)
    for f_idx in found_manifest_file:
        for key, value in const.SUPPORT_PACKAE.items():
            if isinstance(value, list):
                for v in value:
                    if f_idx == v:
                        if key in found_package_manager.keys():
                            found_package_manager[key].append(f_idx)
                        else:
                            found_package_manager[key] = [f_idx]
            else:
                if value == f_idx:
                    found_package_manager[key] = [f_idx]

    if len(found_package_manager) >= 1:
        manifest_file_w_path = map(lambda x: os.path.join(input_dir, x), found_manifest_file)
        logger.info(f"Found the manifest file({','.join(manifest_file_w_path)}) automatically.")
        logger.warning(f"### Set Package Manager = {', '.join(found_package_manager.keys())}")
    else:
        ret = False
        logger.info("It cannot find the manifest file.")

    return ret, found_package_manager, input_dir


def run_dependency_scanner(package_manager='', input_dir='', output_dir_file='', pip_activate_cmd='', pip_deactivate_cmd='',
                           output_custom_dir='', app_name=const.default_app_name, github_token='', format='', direct=True):
    global logger

    ret = True
    sheet_list = {}
    sheet_list[_sheet_name] = []
    _json_ext = ".json"
    _start_time = datetime.now().strftime('%y%m%d_%H%M')

    success, msg, output_path, output_file, output_extension = check_output_format(output_dir_file, format, CUSTOMIZED_FORMAT)
    if success:
        if output_path == "":
            output_path = os.getcwd()
        else:
            output_path = os.path.abspath(output_path)

        if output_file == "":
            if format.startswith('spdx'):
                if platform.system() != 'Windows':
                    output_file = f"fosslight_spdx_dep_{_start_time}"
                else:
                    logger.error('Windows not support spdx format.')
                    sys.exit(0)
            else:
                if output_extension == _json_ext:
                    output_file = f"fosslight_opossum_dep_{_start_time}"
                else:
                    output_file = f"fosslight_report_dep_{_start_time}"
    else:
        logger.error(msg)
        sys.exit(1)

    logger, _result_log = init_log(os.path.join(output_path, "fosslight_log_dep_" + _start_time + ".txt"),
                                   True, logging.INFO, logging.DEBUG, _PKG_NAME)

    logger.info(f"Tool Info : {_result_log['Tool Info']}")

    if not success:
        logger.error(msg)
        return False, sheet_list

    autodetect = True
    if package_manager:
        autodetect = False
        support_packagemanager = list(const.SUPPORT_PACKAE.keys())

        if package_manager not in support_packagemanager:
            logger.error(f"You entered the unsupported package manager({package_manager}).")
            logger.error("Please enter the supported package manager({0}) with '-m' option."
                         .format(", ".join(support_packagemanager)))
            return False, sheet_list

    if input_dir:
        if os.path.isdir(input_dir):
            os.chdir(input_dir)
            input_dir = os.getcwd()
        else:
            logger.error(f"You entered the wrong input path({input_dir}) to run the script.")
            logger.error("Please enter the existed input path with '-p' option.")
            return False, sheet_list
    else:
        input_dir = os.getcwd()
        os.chdir(input_dir)

    found_package_manager = {}
    if autodetect:
        try:
            ret, found_package_manager, input_dir = find_package_manager(input_dir)
            os.chdir(input_dir)
        except Exception as e:
            logger.error(f'Fail to find package manager: {e}')
            ret = False
        finally:
            if not ret:
                logger.warning("Dependency scanning terminated because the package manager was not found.")
                ret = False
    else:
        found_package_manager[package_manager] = ["manual detect ('-m option')"]

    pass_key = 'PASS'
    success_pm = []
    fail_pm = []
    for pm, manifest_file_name in found_package_manager.items():
        if manifest_file_name == pass_key:
            continue
        ret, package_sheet_list = analyze_dependency(pm, input_dir, output_path, pip_activate_cmd, pip_deactivate_cmd,
                                                     output_custom_dir, app_name, github_token, manifest_file_name, direct)
        if ret:
            success_pm.append(f"{pm} ({', '.join(manifest_file_name)})")
            sheet_list[_sheet_name].extend(package_sheet_list)
            if pm == const.GRADLE:
                if const.ANDROID in found_package_manager.keys():
                    found_package_manager[const.ANDROID] = pass_key
                    if f"{const.ANDROID} ({', '.join(manifest_file_name)})" in fail_pm:
                        fail_pm.remove(f"{const.ANDROID} ({', '.join(manifest_file_name)})")
            elif pm == const.ANDROID:
                if const.GRADLE in found_package_manager.keys():
                    found_package_manager[const.GRADLE] = pass_key
                    if f"{const.GRADLE} ({', '.join(manifest_file_name)})" in fail_pm:
                        fail_pm.remove(f"{const.GRADLE} ({', '.join(manifest_file_name)})")
        else:
            fail_pm.append(f"{pm} ({', '.join(manifest_file_name)})")
    cover = CoverItem(tool_name=_PKG_NAME,
                      start_time=_start_time,
                      input_path=input_dir)
    cover_comment_arr = []
    if len(found_package_manager.keys()) > 0:
        if len(success_pm) > 0:
            cover_comment_arr.append(f"Analyzed Package manager: {', '.join(success_pm)}")
        if len(fail_pm) > 0:
            info_msg = 'Check https://fosslight.org/fosslight-guide-en/scanner/3_dependency.html#-prerequisite.'
            cover_comment_arr.append(f"Analysis failed Package manager: {', '.join(fail_pm)} ({info_msg})")
    else:
        cover_comment_arr.append("No Package manager detected.")

    cover.comment = ' / '.join(cover_comment_arr)

    output_file_without_ext = os.path.join(output_path, output_file)
    if format.startswith('spdx'):
        if platform.system() != 'Windows':
            success_write, err_msg, result_file = write_spdx(output_file_without_ext, output_extension, sheet_list,
                                                             _PKG_NAME, pkg_resources.get_distribution(_PKG_NAME).version,
                                                             spdx_version=(2, 3))
        else:
            logger.error('Windows not support spdx format.')
    else:
        success_write, err_msg, result_file = write_output_file(output_file_without_ext, output_extension,
                                                                sheet_list, EXTENDED_HEADER, '', cover)
    if success_write:
        if result_file:
            logger.info(f"Output file: {result_file}")
        else:
            logger.warning(f"{err_msg}")
        for i in cover_comment_arr:
            logger.info(i.strip())
    else:
        ret = False
        logger.error(f"Fail to generate result file. msg:({err_msg})")

    logger.warning("### FINISH ###")
    return ret, sheet_list


def main():
    package_manager = ''
    input_dir = ''
    output_dir = ''
    pip_activate_cmd = ''
    pip_deactivate_cmd = ''
    output_custom_dir = ''
    app_name = const.default_app_name
    github_token = ''
    format = ''
    direct = True

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-h', '--help', action='store_true', required=False)
    parser.add_argument('-v', '--version', action='store_true', required=False)
    parser.add_argument('-m', '--manager', nargs=1, type=str, default='', required=False)
    parser.add_argument('-p', '--path', nargs=1, type=str, required=False)
    parser.add_argument('-o', '--output', nargs=1, type=str, required=False)
    parser.add_argument('-a', '--activate', nargs=1, type=str, default='', required=False)
    parser.add_argument('-d', '--deactivate', nargs=1, type=str, default='', required=False)
    parser.add_argument('-c', '--customized', nargs=1, type=str, required=False)
    parser.add_argument('-n', '--appname', nargs=1, type=str, required=False)
    parser.add_argument('-t', '--token', nargs=1, type=str, required=False)
    parser.add_argument('-f', '--format', nargs=1, type=str, required=False)
    parser.add_argument('--direct', choices=('true', 'false'), default='True', required=False)
    parser.add_argument('--notice', action='store_true', required=False)

    args = parser.parse_args()

    if args.help:  # -h option
        print_help_msg()

    if args.version:  # -v option
        cur_version = pkg_resources.get_distribution(_PKG_NAME).version
        print(f"FOSSLight Dependency Scanner Version: {cur_version}")
        sys.exit(0)

    if args.manager:  # -m option
        package_manager = ''.join(args.manager)
    if args.path:  # -p option
        input_dir = ''.join(args.path)
    if args.output:  # -o option
        output_dir = ''.join(args.output)
    if args.activate:  # -a option
        pip_activate_cmd = ''.join(args.activate)
    if args.deactivate:  # -d option
        pip_deactivate_cmd = ''.join(args.deactivate)
    if args.customized:  # -c option
        output_custom_dir = ''.join(args.customized)
    if args.appname:  # -n option
        app_name = ''.join(args.appname)
    if args.token:  # -t option
        github_token = ''.join(args.token)
    if args.format:  # -f option
        format = ''.join(args.format)
    if args.direct:  # --direct option
        if args.direct == 'true':
            direct = True
        elif args.direct == 'false':
            direct = False
    if args.notice:  # --notice option
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.dirname(__file__)

        data_path = os.path.join(base_path, 'LICENSES')
        print(f"*** {_PKG_NAME} open source license notice ***")
        for ff in os.listdir(data_path):
            f = open(os.path.join(data_path, ff), 'r', encoding='utf8')
            print(f.read())
        sys.exit(0)

    run_dependency_scanner(package_manager, input_dir, output_dir, pip_activate_cmd, pip_deactivate_cmd,
                           output_custom_dir, app_name, github_token, format, direct)


if __name__ == '__main__':
    main()
