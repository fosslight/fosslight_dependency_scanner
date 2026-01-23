#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2020 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import sys
import argparse
import shutil
import fosslight_dependency.constant as const
from fosslight_dependency._help import print_version, print_help_msg
from fosslight_dependency.run_dependency_scanner import run_dependency_scanner, _PKG_NAME


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
    recursive = False

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
    parser.add_argument('-r', '--recursive', action='store_true', required=False)

    args = parser.parse_args()

    if args.help:  # -h option
        print_help_msg()

    if args.version:  # -v option
        print_version(_PKG_NAME)

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
    if args.recursive:  # -r option
        recursive = True

    run_dependency_scanner(package_manager, input_dir, output_dir, pip_activate_cmd, pip_deactivate_cmd,
                           output_custom_dir, app_name, github_token, format, direct, path_to_exclude,
                           graph_path, graph_size, recursive)


if __name__ == '__main__':
    main()
