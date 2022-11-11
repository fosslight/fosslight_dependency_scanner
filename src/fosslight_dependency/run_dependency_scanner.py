#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2020 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import sys
import argparse
import pkg_resources
import warnings
from datetime import datetime
import logging
import fosslight_dependency.constant as const
import traceback
from collections import defaultdict
from fosslight_util.set_log import init_log
import fosslight_util.constant as constant
from fosslight_dependency._help import print_help_msg
from fosslight_dependency._analyze_dependency import analyze_dependency
from fosslight_util.output_format import check_output_format, write_output_file

# Package Name
_PKG_NAME = "fosslight_dependency"
logger = logging.getLogger(constant.LOGGER_NAME)
warnings.filterwarnings("ignore", category=FutureWarning)
_sheet_name = "SRC_FL_Dependency"


def find_package_manager():
    ret = True
    manifest_file_name = []
    for value in const.SUPPORT_PACKAE.values():
        if isinstance(value, list):
            manifest_file_name.extend(value)
        else:
            manifest_file_name.append(value)

    found_manifest_file = []
    for f in manifest_file_name:
        if os.path.isfile(f):
            found_manifest_file.append(f)

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
        logger.info(f"Found the manifest file({','.join(found_manifest_file)}) automatically.")
        logger.warning(f"### Set Package Manager = {', '.join(found_package_manager.keys())}")
    else:
        ret = False
        logger.info("It cannot find the manifest file.")

    return ret, found_package_manager


def run_dependency_scanner(package_manager='', input_dir='', output_dir_file='', pip_activate_cmd='', pip_deactivate_cmd='',
                           output_custom_dir='', app_name=const.default_app_name, github_token='', format='', direct=True):
    global logger

    ret = True
    sheet_list = {}
    sheet_list[_sheet_name] = []
    _json_ext = ".json"
    _start_time = datetime.now().strftime('%y%m%d_%H%M')

    success, msg, output_path, output_file, output_extension = check_output_format(output_dir_file, format)
    if success:
        if output_path == "":
            output_path = os.getcwd()
        else:
            output_path = os.path.abspath(output_path)

        if output_file == "":
            if output_extension == _json_ext:
                output_file = f"fosslight_opossum_{_start_time}"
            else:
                output_file = f"fosslight_report_{_start_time}"
    else:
        logger.error(msg)
        sys.exit(1)

    logger, _result_log = init_log(os.path.join(output_path, "fosslight_log_" + _start_time + ".txt"),
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
            ret, found_package_manager = find_package_manager()
        except Exception as e:
            logger.error(str(e))
            logger.error(traceback.format_exc())
            ret = False
        finally:
            if not ret:
                logger.warning("Dependency scanning terminated because the package manager was not found.")
                return False, sheet_list
    else:
        found_package_manager[package_manager] = ''

    pass_key = 'PASS'
    for pm, manifest_file_name in found_package_manager.items():
        if manifest_file_name == pass_key:
            continue
        ret, package_sheet_list = analyze_dependency(pm, input_dir, output_path, pip_activate_cmd, pip_deactivate_cmd,
                                                     output_custom_dir, app_name, github_token, manifest_file_name, direct)
        if ret:
            sheet_list[_sheet_name].extend(package_sheet_list)
            if pm == const.GRADLE:
                if const.ANDROID in found_package_manager.keys():
                    found_package_manager[const.ANDROID] = pass_key

    output_file_without_ext = os.path.join(output_path, output_file)
    success_to_write, writing_msg, result_file = write_output_file(output_file_without_ext, output_extension,
                                                                   sheet_list)
    if success_to_write:
        if result_file:
            logger.info(f"Writing Output file({result_file}), success:{success_to_write}")
        else:
            logger.warning(f"{writing_msg}")
    else:
        ret = False
        logger.error(f"Fail to generate result file. msg:({writing_msg})")

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
        print(f"FOSSLight Dependency Scanner Version : {cur_version}")
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
