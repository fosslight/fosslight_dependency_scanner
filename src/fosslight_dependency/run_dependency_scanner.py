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
import shutil
import fosslight_dependency.constant as const
from collections import defaultdict
from fosslight_util.set_log import init_log
import fosslight_util.constant as constant
from fosslight_dependency._help import print_help_msg
from fosslight_dependency._analyze_dependency import analyze_dependency
from fosslight_util.output_format import check_output_formats_v2, write_output_file
from fosslight_util.oss_item import ScannerItem
from fosslight_dependency._graph_convertor import GraphConvertor

# Package Name
_PKG_NAME = "fosslight_dependency"
logger = logging.getLogger(constant.LOGGER_NAME)
warnings.filterwarnings("ignore", category=FutureWarning)
_sheet_name = "DEP_FL_Dependency"
EXTENDED_HEADER = {_sheet_name: ['ID', 'Package URL', 'OSS Name',
                                       'OSS Version', 'License', 'Download Location',
                                       'Homepage', 'Copyright Text', 'Exclude',
                                       'Comment', 'Depends On']}
_exclude_dir = ['node_moduels', 'venv']


def get_terminal_size():
    size = shutil.get_terminal_size()
    return size.lines


def paginate_file(file_path):
    lines_per_page = get_terminal_size() - 1
    with open(file_path, 'r', encoding='utf8') as file:
        lines = file.readlines()

    for i in range(0, len(lines), lines_per_page):
        os.system('clear' if os.name == 'posix' else 'cls')
        print(''.join(lines[i: i + lines_per_page]))
        if i + lines_per_page < len(lines):
            input("Press Enter to see the next page...")


def find_package_manager(input_dir, abs_path_to_exclude=[], manifest_file_name=[]):
    ret = True
    if not manifest_file_name:
        for value in const.SUPPORT_PACKAE.values():
            if isinstance(value, list):
                manifest_file_name.extend(value)
            else:
                manifest_file_name.append(value)

    found_manifest_file = []
    suggested_files = []
    for parent, dirs, files in os.walk(input_dir):
        if len(files) < 1:
            continue
        if os.path.basename(parent) in _exclude_dir:
            continue
        if os.path.abspath(parent) in abs_path_to_exclude:
            continue
        for file in files:
            file_path = os.path.join(parent, file)
            file_abs_path = os.path.abspath(file_path)
            if any(os.path.commonpath([file_abs_path, exclude_path]) == exclude_path
                   for exclude_path in abs_path_to_exclude):
                continue
            if file in manifest_file_name:
                found_manifest_file.append(file)
            if file in const.SUGGESTED_PACKAGE.keys():
                suggested_files.append(os.path.join(parent, file))
        for dir in dirs:
            for manifest_f in manifest_file_name:
                manifest_l = manifest_f.split(os.path.sep)
                if len(manifest_l) > 1:
                    if manifest_l[0] == dir:
                        if os.path.exists(os.path.join(parent, manifest_f)):
                            found_manifest_file.append(manifest_f)
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

    # both npm and pnpm are detected, remove npm.
    if 'npm' in found_package_manager and 'pnpm' in found_package_manager:
        del found_package_manager['npm']
    if len(found_package_manager) >= 1:
        manifest_file_w_path = [os.path.join(input_dir, file) for pkg, files in found_package_manager.items() for file in files]
        logger.info(f"Found the manifest file({','.join(manifest_file_w_path)}) automatically.")
        logger.warning(f"### Set Package Manager = {', '.join(found_package_manager.keys())}")
    else:
        ret = False
        logger.info("Cannot find the manifest file.")

    return ret, found_package_manager, input_dir, suggested_files


def run_dependency_scanner(package_manager='', input_dir='', output_dir_file='', pip_activate_cmd='',
                           pip_deactivate_cmd='', output_custom_dir='', app_name=const.default_app_name,
                           github_token='', formats=[], direct=True, path_to_exclude=[], graph_path='',
                           graph_size=(600, 600)):
    global logger

    ret = True
    _json_ext = ".json"
    _start_time = datetime.now().strftime('%y%m%d_%H%M')
    scan_item = ScannerItem(_PKG_NAME, _start_time)

    success, msg, output_path, output_files, output_extensions, formats = check_output_formats_v2(output_dir_file, formats)
    if success:
        if output_path == "":
            output_path = os.getcwd()
        else:
            output_path = os.path.abspath(output_path)

        if not output_files:
            while len(output_files) < len(output_extensions):
                output_files.append(None)
            to_remove = []  # elements of spdx format on windows that should be removed
            for i, output_extension in enumerate(output_extensions):
                if formats:
                    if formats[i].startswith('spdx') or formats[i].startswith('cyclonedx'):
                        if platform.system() == 'Windows':
                            logger.warning(f'{formats[i]} is not supported on Windows.Please remove {formats[i]} from format.')
                            to_remove.append(i)
                        else:
                            if formats[i].startswith('spdx'):
                                output_files[i] = f"fosslight_spdx_dep_{_start_time}"
                            elif formats[i].startswith('cyclonedx'):
                                output_files[i] = f'fosslight_cyclonedx_dep_{_start_time}'
                    else:
                        if output_extension == _json_ext:
                            output_files[i] = f"fosslight_opossum_dep_{_start_time}"
                        else:
                            output_files[i] = f"fosslight_report_dep_{_start_time}"
                else:
                    if output_extension == _json_ext:
                        output_files[i] = f"fosslight_opossum_dep_{_start_time}"
                    else:
                        output_files[i] = f"fosslight_report_dep_{_start_time}"
            for index in sorted(to_remove, reverse=True):
                # remove elements of spdx format on windows
                del output_files[index]
                del output_extensions[index]
                del formats[index]
            if len(output_extensions) < 1:
                sys.exit(0)
    else:
        logger.error(msg)
        sys.exit(1)

    logger, _result_log = init_log(os.path.join(output_path, "fosslight_log_dep_" + _start_time + ".txt"),
                                   True, logging.INFO, logging.DEBUG, _PKG_NAME, "", path_to_exclude)
    abs_path_to_exclude = [os.path.abspath(os.path.join(input_dir, path)) for path in path_to_exclude]

    logger.info(f"Tool Info : {_result_log['Tool Info']}")

    if not success:
        logger.error(msg)
        return False, scan_item

    if input_dir:
        if os.path.isdir(input_dir):
            os.chdir(input_dir)
            input_dir = os.getcwd()
        else:
            logger.error(f"(-p option) You entered the wrong input path({input_dir}) to run the script.")
            logger.error("Please enter the existed input path with '-p' option.")
            return False, scan_item
    else:
        input_dir = os.getcwd()
        os.chdir(input_dir)
    scan_item.set_cover_pathinfo(input_dir, path_to_exclude)

    autodetect = True
    found_package_manager = {}
    if package_manager:
        autodetect = False
        support_packagemanager = list(const.SUPPORT_PACKAE.keys())

        if package_manager not in support_packagemanager:
            logger.error(f"(-m option) You entered the unsupported package manager({package_manager}).")
            logger.error("Please enter the supported package manager({0}) with '-m' option."
                         .format(", ".join(support_packagemanager)))
            return False, scan_item
        manifest_file_name = []
        value = const.SUPPORT_PACKAE[package_manager]
        if isinstance(value, list):
            manifest_file_name.extend(value)
        else:
            manifest_file_name.append(value)
        scan_item.set_cover_comment(f"Manual detect mode (-m {package_manager})")
    else:
        manifest_file_name = []

    try:
        ret, found_package_manager, input_dir, suggested_files = find_package_manager(input_dir,
                                                                                      abs_path_to_exclude,
                                                                                      manifest_file_name)
        if ret:
            os.chdir(input_dir)
    except Exception as e:
        if autodetect:
            logger.error(f'Fail to find package manager: {e}')
            ret = False
    finally:
        if not ret:
            if not autodetect:
                logger.info('Try to analyze dependency without manifest file. (Manual mode)')
                found_package_manager[package_manager] = []
            else:
                ret = False
                if suggested_files:
                    suggested_files_str = []
                    suggested_files_str.append("Please check the following files and try again:")
                    for f in suggested_files:
                        pm = const.SUGGESTED_PACKAGE[f.split(os.path.sep)[-1]]
                        suggested_files_str.append(f"\t\t\t{f} ({pm}) detected, but {const.SUPPORT_PACKAE[pm]} missing.")

                    suggested_files_str.append("\t\t\tRefer: https://fosslight.org/fosslight-guide-en/scanner/3_dependency.html.")
                    scan_item.set_cover_comment('\n'.join(suggested_files_str))
                else:
                    scan_item.set_cover_comment("No Package manager detected.")

    pass_key = 'PASS'
    success_pm = []
    fail_pm = []
    cover_comment = ''
    for pm, manifest_file_name in found_package_manager.items():
        if manifest_file_name == pass_key:
            continue
        ret, package_dep_item_list, cover_comment = analyze_dependency(pm, input_dir, output_path,
                                                                       pip_activate_cmd, pip_deactivate_cmd,
                                                                       output_custom_dir, app_name, github_token,
                                                                       manifest_file_name, direct)
        if ret:
            success_pm.append(f"{pm} ({', '.join(manifest_file_name)})")
            scan_item.append_file_items(package_dep_item_list)
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

    if len(found_package_manager.keys()) > 0:
        if len(success_pm) > 0:
            scan_item.set_cover_comment(f"Analyzed Package manager: {', '.join(success_pm)}")
        if len(fail_pm) > 0:
            info_msg = 'Check log file(fosslight_log*.txt) ' \
                       'and https://fosslight.org/fosslight-guide-en/scanner/3_dependency.html#-prerequisite.'
            scan_item.set_cover_comment(f"Analysis failed Package manager: {', '.join(fail_pm)} ({info_msg})")

    if ret and graph_path:
        graph_path = os.path.abspath(graph_path)
        try:
            converter = GraphConvertor(scan_item.file_items[_PKG_NAME])
            growth_factor_per_node = 10
            node_count_threshold = 20
            node_count = len(scan_item.file_items[_PKG_NAME])
            if node_count > node_count_threshold:
                new_size = tuple(x + (node_count * growth_factor_per_node) for x in graph_size)
            else:
                new_size = graph_size
            new_size = tuple((((x + 99) // 100) * 100) for x in new_size)
            converter.save(graph_path, new_size)
            logger.info(f"Output graph image file: {graph_path}")
        except Exception as e:
            logger.error(f'Fail to make graph image: {e}')

    if cover_comment:
        scan_item.set_cover_comment(cover_comment)

    combined_paths_and_files = [os.path.join(output_path, file) for file in output_files]
    results = []
    for i, output_extension in enumerate(output_extensions):
        results.append(write_output_file(combined_paths_and_files[i], output_extension, scan_item,
                                         EXTENDED_HEADER, '', formats[i]))
    for success_write, err_msg, result_file in results:
        if success_write:
            if result_file:
                logger.info(f"Output file: {result_file}")
            else:
                logger.warning(f"{err_msg}")
            for i in scan_item.get_cover_comment():
                if ret:
                    logger.info(i)
                else:
                    logger.warning(i)
        else:
            ret = False
            logger.error(f"Fail to generate result file. msg:({err_msg})")

    return ret, scan_item


def main():
    package_manager = ''
    input_dir = ''
    output_dir = ''
    path_to_exclude = []
    pip_activate_cmd = ''
    pip_deactivate_cmd = ''
    output_custom_dir = ''
    app_name = const.default_app_name
    github_token = ''
    format = []
    graph_path = ''
    graph_size = (600, 600)
    direct = True

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-h', '--help', action='store_true', required=False)
    parser.add_argument('-v', '--version', action='store_true', required=False)
    parser.add_argument('-m', '--manager', nargs=1, type=str, default='', required=False)
    parser.add_argument('-p', '--path', nargs=1, type=str, required=False)
    parser.add_argument('-e', '--exclude', nargs='*', required=False, default=[])
    parser.add_argument('-o', '--output', nargs=1, type=str, required=False)
    parser.add_argument('-a', '--activate', nargs=1, type=str, default='', required=False)
    parser.add_argument('-d', '--deactivate', nargs=1, type=str, default='', required=False)
    parser.add_argument('-c', '--customized', nargs=1, type=str, required=False)
    parser.add_argument('-n', '--appname', nargs=1, type=str, required=False)
    parser.add_argument('-t', '--token', nargs=1, type=str, required=False)
    parser.add_argument('-f', '--format', nargs="*", type=str, required=False)
    parser.add_argument('--graph-path', nargs=1, type=str, required=False)
    parser.add_argument('--graph-size', nargs=2, type=int, metavar=("WIDTH", "HEIGHT"), required=False)
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
    if args.exclude:  # -e option
        path_to_exclude = args.exclude
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
        format = list(args.format)
    if args.graph_path:
        graph_path = ''.join(args.graph_path)
    if args.graph_size:
        graph_size = args.graph_size
    if args.direct:  # --direct option
        if args.direct == 'true' or args.direct == 'True':
            direct = True
        elif args.direct == 'false' or args.direct == 'False':
            direct = False
    if args.notice:  # --notice option
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.dirname(__file__)

        data_path = os.path.join(base_path, 'LICENSES')
        print(f"*** {_PKG_NAME} open source license notice ***")
        for ff in os.listdir(data_path):
            source_file = os.path.join(data_path, ff)
            destination_file = os.path.join(base_path, ff)
            paginate_file(source_file)
            shutil.copyfile(source_file, destination_file)
        sys.exit(0)

    run_dependency_scanner(package_manager, input_dir, output_dir, pip_activate_cmd, pip_deactivate_cmd,
                           output_custom_dir, app_name, github_token, format, direct, path_to_exclude,
                           graph_path, graph_size)


if __name__ == '__main__':
    main()
