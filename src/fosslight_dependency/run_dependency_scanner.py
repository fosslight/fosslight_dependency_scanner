#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2020 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import platform
import re
import sys
import warnings
import logging
import fosslight_dependency.constant as const
from collections import defaultdict
from fosslight_util.set_log import init_log
import fosslight_util.constant as constant
from fosslight_dependency._analyze_dependency import analyze_dependency
from fosslight_util.output_format import check_output_formats_v2, write_output_file
from fosslight_util.cover import dump_result_log
from fosslight_util.time import current_timestamp_utc, format_running_time, timestamp_for_filename
from fosslight_util.oss_item import ScannerItem
from fosslight_dependency._graph_convertor import GraphConvertor
from fosslight_util.exclude import get_excluded_paths

# Package Name
_PKG_NAME = "fosslight_dependency"
logger = logging.getLogger(constant.LOGGER_NAME)
warnings.filterwarnings("ignore", category=FutureWarning)
_sheet_name = "DEP_FL_Dependency"
EXTENDED_HEADER = {_sheet_name: ['ID', 'Package URL', 'OSS Name',
                                       'OSS Version', 'License', 'Download Location',
                                       'Homepage', 'Copyright Text', 'Exclude',
                                       'Comment', 'Depends On']}

# Definitive Android signals — any single match is enough to classify the
# file as Android. Combines explicit AGP plugin IDs and version-catalog
# aliases; all `libs.plugins.android.*` aliases are covered by the prefix.
_ANDROID_DEFINITIVE_PATTERNS = (
    "com.android.application",
    "com.android.library",
    "com.android.test",
    "com.android.dynamic-feature",
    "com.android.tools.build:gradle",
    "alias(libs.plugins.android.",   # covers all AGP aliases in libs.versions.toml
)

# DSL keys that are Android-specific *only* inside an `android { … }` block.
# Matching them against the full file would produce false positives because
# they are ordinary words that appear in non-Android build logic too.
_ANDROID_BLOCK_MARKERS = (
    "compilesdk",
    "minsdk",
    "targetsdk",
    "namespace",
    "applicationid",
    "buildfeatures",
    "signingconfigs",
    "productflavors",
    "defaultconfig",
)

# Locates every `android { … }` block in the normalized source.
# The negative lookbehind (?<![a-z]) prevents matching identifiers that
# merely end with 'android' (e.g. 'testandroid{').
_ANDROID_BLOCK_RE = re.compile(r'(?<![a-z])android\{')


def _iter_android_block_contents(normalized):
    for m in _ANDROID_BLOCK_RE.finditer(normalized):
        pos = m.end()
        depth = 1
        start = pos
        while pos < len(normalized) and depth > 0:
            if normalized[pos] == '{':
                depth += 1
            elif normalized[pos] == '}':
                depth -= 1
            pos += 1
        if depth == 0:
            yield normalized[start:pos - 1]


def classify_gradle_build_file(build_content):
    if not build_content:
        return False, False

    normalized = ''.join(build_content.lower().split())

    # 1) Definitive: explicit AGP plugin ID or version-catalog alias
    if any(p in normalized for p in _ANDROID_DEFINITIVE_PATTERNS):
        return False, True

    # 2) Contextual: android { } block containing Android-specific DSL
    if any(
        any(marker in block for marker in _ANDROID_BLOCK_MARKERS)
        for block in _iter_android_block_contents(normalized)
    ):
        return False, True

    # 3) Default: treat as Gradle so the scanner can still attempt analysis
    return True, False


def find_package_manager(input_dir, path_to_exclude=[], manifest_file_name=[], recursive=False, excluded_files=[]):
    ret = True
    if not manifest_file_name:
        for value in const.SUPPORT_PACKAGE.values():
            if isinstance(value, list):
                manifest_file_name.extend(value)
            else:
                manifest_file_name.append(value)

    found_manifest_file = []
    found_manifest_set = set()
    suggested_files = []
    for parent, dirs, files in os.walk(input_dir):
        rel_parent = os.path.relpath(parent, input_dir)
        if rel_parent != '.' and rel_parent in path_to_exclude:
            dirs[:] = []
            continue
        for file in files:
            file_path = os.path.join(parent, file)
            rel_file_path = os.path.relpath(file_path, input_dir)
            if rel_file_path in excluded_files:
                continue
            if file in manifest_file_name:
                candidate = os.path.join(parent, file)
                norm_candidate = os.path.normpath(candidate)
                if norm_candidate not in found_manifest_set:
                    found_manifest_set.add(norm_candidate)
                    found_manifest_file.append(candidate)
            for manifest_f in manifest_file_name:
                candidate = os.path.join(parent, manifest_f)
                norm_candidate = os.path.normpath(candidate)
                if norm_candidate in found_manifest_set:
                    continue
                rel_candidate = os.path.relpath(candidate, input_dir)
                if rel_candidate in excluded_files:
                    logger.debug(f'Skipping excluded manifest: {rel_candidate}')
                    continue
                if os.path.exists(candidate):
                    found_manifest_set.add(norm_candidate)
                    found_manifest_file.append(candidate)
            if file in const.SUGGESTED_PACKAGE.keys():
                suggested_files.append(os.path.join(parent, file))

        for dir in dirs:
            for manifest_f in manifest_file_name:
                manifest_l = manifest_f.split(os.path.sep)
                if len(manifest_l) > 1 and manifest_l[0] == dir:
                    candidate = os.path.join(parent, manifest_f)
                    norm_candidate = os.path.normpath(candidate)
                    if norm_candidate in found_manifest_set:
                        continue
                    rel_candidate = os.path.relpath(candidate, input_dir)
                    if rel_candidate in excluded_files:
                        logger.debug(f'Skipping excluded manifest in dir: {rel_candidate}')
                        continue
                    if os.path.exists(candidate):
                        found_manifest_set.add(norm_candidate)
                        found_manifest_file.append(candidate)

        if not recursive:
            if len(found_manifest_file) > 0:
                input_dir = parent
                break

    found_package_manager = defaultdict(lambda: defaultdict(list))
    for f_with_path in found_manifest_file:
        f_name = os.path.basename(f_with_path)
        dir_path = os.path.dirname(f_with_path)
        for key, value in const.SUPPORT_PACKAGE.items():
            manifest_patterns = value if isinstance(value, list) else [value]

            for pattern in manifest_patterns:
                if os.path.sep not in pattern:
                    if f_name == pattern:
                        if pattern not in found_package_manager[key][dir_path]:
                            found_package_manager[key][dir_path].append(pattern)
                else:
                    rel_dir, rel_file = os.path.split(pattern)
                    expected_path = os.path.join(dir_path, rel_file)

                    if f_name == rel_file:
                        candidate = os.path.join(os.path.dirname(dir_path), rel_dir, rel_file) if rel_dir else expected_path
                        if os.path.normpath(candidate) == os.path.normpath(f_with_path):
                            if pattern not in found_package_manager[key][dir_path]:
                                found_package_manager[key][dir_path].append(pattern)
    found_package_manager = {k: dict(v) for k, v in found_package_manager.items()}

    # both npm and pnpm are detected, remove npm.
    if 'npm' in found_package_manager.keys() and 'pnpm' in found_package_manager.keys():
        del found_package_manager['npm']

    # both npm and yarn are detected, check which one to use based on lock file
    if 'npm' in found_package_manager.keys() and 'yarn' in found_package_manager.keys():
        # Remove npm from directories where yarn.lock exists
        dirs_to_remove_from_npm = []
        for yarn_dir in found_package_manager['yarn'].keys():
            if yarn_dir in found_package_manager['npm']:
                dirs_to_remove_from_npm.append(yarn_dir)

        for dir_to_remove in dirs_to_remove_from_npm:
            del found_package_manager['npm'][dir_to_remove]

        # If npm has no directories left, remove it entirely
        if not found_package_manager['npm']:
            del found_package_manager['npm']

    found_package_manager_bk = found_package_manager
    if 'gradle' in found_package_manager and 'android' in found_package_manager:
        for d in found_package_manager['gradle'].keys() & found_package_manager['android'].keys():
            gradle_ret = False
            android_ret = False
            build_files_to_check = []
            gradle_files = found_package_manager['gradle'][d]
            android_files = found_package_manager['android'][d]
            for build_file in ['build.gradle', 'build.gradle.kts']:
                if build_file in gradle_files and build_file in android_files:
                    build_files_to_check.append(build_file)
            for build_file in build_files_to_check:
                check_gradle = os.path.join(d, build_file)
                try:
                    with open(check_gradle, 'r', encoding='utf-8') as gradle_temp:
                        data = gradle_temp.read()
                        is_gradle, is_android = classify_gradle_build_file(data)
                        gradle_ret = gradle_ret or is_gradle
                        android_ret = android_ret or is_android
                except Exception as e:
                    logger.warning(f"Cannot open {build_file}: {e}")

            if gradle_ret and not android_ret:
                found_package_manager_bk["android"].pop(d, None)
            elif not gradle_ret and android_ret:
                found_package_manager_bk["gradle"].pop(d, None)

    found_package_manager_bk = {
        k: v for k, v in found_package_manager.items() if not ((isinstance(v, dict) and not v) or (isinstance(v, list) and not v))
    }
    found_package_manager = found_package_manager_bk

    if len(found_package_manager) >= 1:
        log_lines = [f"\nDetected Manifest Files automatically\nAnalyzed path: {input_dir}"]
        log_lines = print_package_info(found_package_manager, log_lines, base_dir=input_dir)
        logger.info('\n'.join(log_lines))
    else:
        ret = False
        logger.info("Cannot find the manifest file.")

    return ret, found_package_manager, input_dir, suggested_files


def print_package_info(pm, log_lines, status='', base_dir=''):
    if pm:
        if status:
            status = f"[{status}] "
        for pm, dir_dict in pm.items():
            log_lines.append(f"- {status} {pm}:")
            for path, files in dir_dict.items():
                file_list = ', '.join(files)
                if base_dir:
                    rel_path = os.path.relpath(path, base_dir)
                    if rel_path == '.':
                        log_lines.append(f"  {file_list}")
                    else:
                        log_lines.append(f"  {rel_path}{os.sep}{file_list}")
                else:
                    log_lines.append(f"  {path}: {file_list}")
    return log_lines


def run_dependency_scanner(package_manager='', input_dir='', output_dir_file='', pip_activate_cmd='',
                           pip_deactivate_cmd='', output_custom_dir='', app_name=const.default_app_name,
                           github_token='', formats=[], direct=True, path_to_exclude=[], graph_path='',
                           graph_size=(600, 600), recursive=False, all_exclude_mode=()):
    os.environ['PYTHONUTF8'] = '1'
    os.environ['PYTHONIOENCODING'] = 'utf-8'

    global logger

    ret = True
    _json_ext = ".json"
    _start_time = current_timestamp_utc()
    _file_time = timestamp_for_filename(_start_time)
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
                                output_files[i] = f"fosslight_spdx_dep_{_file_time}"
                            elif formats[i].startswith('cyclonedx'):
                                output_files[i] = f'fosslight_cyclonedx_dep_{_file_time}'
                    else:
                        if output_extension == _json_ext:
                            output_files[i] = f"fosslight_opossum_dep_{_file_time}"
                        else:
                            output_files[i] = f"fosslight_report_dep_{_file_time}"
                else:
                    if output_extension == _json_ext:
                        output_files[i] = f"fosslight_opossum_dep_{_file_time}"
                    else:
                        output_files[i] = f"fosslight_report_dep_{_file_time}"
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

    logger, _result_log = init_log(os.path.join(output_path, "fosslight_log_dep_" + _file_time + ".txt"),
                                   True, logging.INFO, logging.DEBUG, _PKG_NAME, "", path_to_exclude)

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

    base_path = input_dir

    autodetect = True
    found_package_manager = {}
    if package_manager:
        scan_item.set_cover_comment(f"Manual detect mode (-m {package_manager})")
        autodetect = False
        support_packagemanager = list(const.SUPPORT_PACKAGE.keys())

        if package_manager not in support_packagemanager:
            logger.error(f"(-m option) You entered the unsupported package manager({package_manager}).")
            logger.error("Please enter the supported package manager({0}) with '-m' option."
                         .format(", ".join(support_packagemanager)))
            return False, scan_item
        manifest_file_name = []
        value = const.SUPPORT_PACKAGE[package_manager]
        if isinstance(value, list):
            manifest_file_name.extend(value)
        else:
            manifest_file_name.append(value)
    else:
        manifest_file_name = []

    suggested_files = []
    try:
        if all_exclude_mode and len(all_exclude_mode) == 4:
            excluded_path_with_default_exclusion, excluded_path_without_dot, excluded_files, _ = all_exclude_mode
        else:
            excluded_path_with_default_exclusion, excluded_path_without_dot, excluded_files, _ = (
                get_excluded_paths(input_dir, path_to_exclude))
            logger.debug(f"Skipped paths: {excluded_path_with_default_exclusion}")

        scan_item.set_cover_pathinfo(input_dir, excluded_path_without_dot)
        ret, found_package_manager, input_dir, suggested_files = find_package_manager(input_dir,
                                                                                      excluded_path_with_default_exclusion,
                                                                                      manifest_file_name,
                                                                                      recursive,
                                                                                      excluded_files)
    except Exception as e:
        if autodetect:
            logger.error(f'Fail to find package manager: {e}')
            ret = False
    finally:
        if not ret:
            if not autodetect:
                logger.info('Try to analyze dependency without manifest file. (Manual mode)')
                found_package_manager[package_manager] = {}
            else:
                ret = False
                if suggested_files:
                    suggested_files_str = []
                    suggested_files_str.append("Please check the following files and try again:")
                    for f in suggested_files:
                        pm = const.SUGGESTED_PACKAGE[f.split(os.path.sep)[-1]]
                        suggested_files_str.append(f"\t\t\t{f} ({pm}) detected, but {const.SUPPORT_PACKAGE[pm]} missing.")

                    suggested_files_str.append("\t\t\tRefer: https://fosslight.org/fosslight-guide-en/scanner/1_dependency.html")
                    scan_item.set_cover_comment('\n'.join(suggested_files_str))
                else:
                    scan_item.set_cover_comment("No Package manager detected.")

    pass_key = ['PASS']
    success_pm = defaultdict(lambda: defaultdict(list))
    fail_pm = defaultdict(lambda: defaultdict(list))
    cover_comment = ''
    for pm, manifest_file_name_list in found_package_manager.items():
        if not manifest_file_name_list and not autodetect:
            ret, package_dep_item_list, cover_comment, actual_pm = analyze_dependency(pm, input_dir, output_path,
                                                                                      pip_activate_cmd, pip_deactivate_cmd,
                                                                                      output_custom_dir, app_name, github_token,
                                                                                      [], direct)
            if ret:
                success_pm[actual_pm][input_dir].extend(['manual mode (-m option)'])
                scan_item.append_file_items(package_dep_item_list)
            else:
                fail_pm[actual_pm][input_dir].extend(['manual mode (-m option)'])
        else:
            for manifest_dir, manifest_file_name in manifest_file_name_list.items():
                input_dir = manifest_dir
                if manifest_file_name == pass_key:
                    continue
                os.chdir(input_dir)
                ret, package_dep_item_list, cover_comment, actual_pm = analyze_dependency(pm, input_dir, output_path,
                                                                                          pip_activate_cmd, pip_deactivate_cmd,
                                                                                          output_custom_dir, app_name,
                                                                                          github_token,
                                                                                          manifest_file_name, direct)
                if ret:
                    success_pm[actual_pm][input_dir].extend(manifest_file_name)
                    scan_item.append_file_items(package_dep_item_list)

                    dup_pm = None
                    if actual_pm == const.GRADLE and const.ANDROID in found_package_manager:
                        dup_pm = const.ANDROID
                    elif actual_pm == const.ANDROID and const.GRADLE in found_package_manager:
                        dup_pm = const.GRADLE

                    if dup_pm:
                        if dup_pm in fail_pm and input_dir in fail_pm[dup_pm]:
                            fail_pm[dup_pm].pop(input_dir, None)
                            if not fail_pm[dup_pm]:
                                fail_pm.pop(dup_pm, None)
                        else:
                            found_package_manager[dup_pm][manifest_dir] = pass_key
                else:
                    fail_pm[actual_pm][input_dir].extend(manifest_file_name)

    success_pm = {k: dict(v) for k, v in success_pm.items()}
    fail_pm = {k: dict(v) for k, v in fail_pm.items()}
    if len(found_package_manager.keys()) > 0:
        log_lines = ["Dependency Analysis Summary"]
        if len(success_pm) > 0:
            log_lines = print_package_info(success_pm, log_lines, 'Success', base_path)
        if len(fail_pm) > 0:
            log_lines = print_package_info(fail_pm, log_lines, 'Fail', base_path)
            log_lines.append('If analysis fails, see fosslight_log*.txt and the prerequisite guide: '
                             'https://fosslight.org/fosslight-guide-en/scanner/1_dependency.html#how-to-run-and-output')
        scan_item.set_cover_comment('\n'.join(log_lines))

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

    finish_time = current_timestamp_utc()
    scan_item.set_cover_finish_time(finish_time)

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

    _result_log["Running time"] = format_running_time(_start_time, finish_time)
    logger.info(dump_result_log(_result_log))

    return ret, scan_item
