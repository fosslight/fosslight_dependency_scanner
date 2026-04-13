#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import platform
import re
import base64
import subprocess
import shutil
import stat
from packageurl.contrib import url2purl
from askalono import identify
import fosslight_util.constant as constant
import fosslight_dependency.constant as const

try:
    from github import Github
except Exception:
    pass

logger = logging.getLogger(constant.LOGGER_NAME)

gradle_config = ['runtimeClasspath', 'runtime']
android_config = ['releaseRuntimeClasspath']
ASKALONO_THRESHOLD = 0.7


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
        self.relation_tree = {}
        self.package_name = ''
        self.cover_comment = ''
        self.dep_items = []

        self.platform = platform.system()

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
        self.relation_tree = {}
        self.package_name = ''
        self.dep_items = []

    def run_plugin(self):
        ret = True
        if self.package_manager_name in (const.GRADLE, const.ANDROID):
            ret = self.run_gradle_task()
        else:
            logger.info(f"This package manager({self.package_manager_name}) skips the step to run plugin.")
        return ret

    def append_input_package_list_file(self, input_package_file):
        self.input_package_list_file.append(input_package_file)

    def set_manifest_file(self, manifest_file_name):
        self.manifest_file_name = manifest_file_name

    def set_direct_dependencies(self, direct):
        self.direct_dep = direct

    def parse_direct_dependencies(self):
        pass

    def run_gradle_task(self):
        ret_task = True
        prev_dir = os.getcwd()
        gradle_file = ''
        gradle_backup = ''
        module_build_gradle = ''
        module_gradle_backup = ''
        os.chdir(self.input_dir)
        try:
            candidates = const.SUPPORT_PACKAGE.get(self.package_manager_name, '')
            if isinstance(candidates, list):
                gradle_file = next((f for f in candidates if os.path.isfile(f)), '')
            else:
                gradle_file = candidates
            if os.path.isfile(gradle_file):
                gradle_backup = f'{gradle_file}_bk'

                shutil.copy(gradle_file, gradle_backup)
                ret_alldeps = self.add_allDeps_in_gradle(gradle_file)

                ret_plugin = False
                if self.package_manager_name == const.ANDROID:
                    module_build_gradle = os.path.join(self.app_name, gradle_file)
                    module_gradle_backup = f'{module_build_gradle}_bk'
                    if os.path.isfile(module_build_gradle) and (not os.path.isfile(self.input_file_name)):
                        shutil.copy(module_build_gradle, module_gradle_backup)
                        ret_plugin = self.add_android_plugin_in_gradle(module_build_gradle, gradle_file)

                cmd_gradle = ''
                if os.path.isfile('gradlew') or os.path.isfile('gradlew.bat'):
                    if self.platform == const.WINDOWS:
                        cmd_gradle = "gradlew.bat"
                    else:
                        cmd_gradle = "./gradlew"
                else:
                    ret_task = False
                    self.set_direct_dependencies(False)
                    logger.warning('No gradlew file exists (Skip to find dependencies relationship.).')
                    if ret_plugin:
                        logger.warning('Also it cannot run android-dependency-scanning plugin.')

                if ret_task:
                    current_mode = change_file_mode(cmd_gradle)
                    if ret_alldeps:
                        cmd = [cmd_gradle, 'allDeps']
                        try:
                            ret = subprocess.check_output(cmd, encoding='utf-8')
                            if ret:
                                self.parse_dependency_tree(ret)
                            else:
                                self.set_direct_dependencies(False)
                                logger.warning(f"Fail to run {cmd}")
                        except Exception as e:
                            self.set_direct_dependencies(False)
                            logger.warning(f"Cannot print 'depends on' information. (fail {cmd}: {e})")

                    if ret_plugin:
                        cmd = [cmd_gradle, f':{self.app_name}:generateLicenseTxt']
                        try:
                            result = subprocess.run(cmd, capture_output=True, encoding='utf-8')
                            if result.returncode != 0:
                                ret_task = False
                                logger.error(f'Fail to run {cmd}: {result.stderr.strip()}')
                            if os.path.isfile(self.input_file_name):
                                logger.info('Automatically run android-dependency-scanning plugin and generate output.')
                                self.plugin_auto_run = True
                            else:
                                logger.warning(
                                    'Automatically run android-dependency-scanning plugin, but fail to generate output.'
                                )
                        except Exception as e:
                            logger.error(f'Fail to run {cmd}: {e}')
                            ret_task = False
                    change_file_mode(cmd_gradle, current_mode)

            if os.path.isfile(self.input_file_name):
                logger.info(f'Found {self.input_file_name}, skip to run plugin.')
                self.set_direct_dependencies(False)
                ret_task = True
        except Exception as e:
            logger.error(f'Unexpected error in run_gradle_task: {e}')
            ret_task = False
        finally:
            if gradle_backup and os.path.isfile(gradle_backup):
                if gradle_file and os.path.isfile(gradle_file):
                    os.remove(gradle_file)
                shutil.move(gradle_backup, gradle_file)
            if module_gradle_backup and os.path.isfile(module_gradle_backup):
                if module_build_gradle and os.path.isfile(module_build_gradle):
                    os.remove(module_build_gradle)
                shutil.move(module_gradle_backup, module_build_gradle)
            os.chdir(prev_dir)

        return ret_task

    def add_android_plugin_in_gradle(self, module_build_gradle, gradle_file):
        is_kts = gradle_file == 'build.gradle.kts'
        if is_kts:
            apply = 'apply(plugin = "org.fosslight")\n'
            plugin_classpath = '        classpath("org.fosslight:android-dependency-scanning:+")'
        else:
            apply = "apply plugin: 'org.fosslight'\n"
            plugin_classpath = "        classpath 'org.fosslight:android-dependency-scanning:+'"

        complete_buildscript = (
            "buildscript {\n"
            "    repositories {\n"
            "        mavenCentral()\n"
            "    }\n"
            "    dependencies {\n"
            f"{plugin_classpath}\n"
            "    }\n"
            "}\n"
        )
        try:
            with open(gradle_file, 'r', encoding='utf-8') as f:
                data = f.read()
            if 'buildscript {' in data:
                bs_start = data.index('buildscript {')
                bs_block = data[bs_start:]
                if 'dependencies {' in bs_block:
                    dep_pos = bs_start + bs_block.index('dependencies {') + len('dependencies {')
                    data = data[:dep_pos] + f'\n{plugin_classpath}' + data[dep_pos:]
                else:
                    data = data.replace(
                        'buildscript {',
                        f'buildscript {{\n    dependencies {{\n{plugin_classpath}\n    }}',
                        1
                    )
            else:
                data = complete_buildscript + data
            with open(gradle_file, 'w', encoding='utf-8') as f:
                f.write(data)
        except Exception as e:
            logging.warning(f"Cannot add the buildscript task in build.gradle: {e}")
            return False

        try:
            with open(module_build_gradle, 'a', encoding='utf-8') as f:
                f.write(f'\n{apply}\n')
            return True
        except Exception as e:
            logging.warning(f"Cannot add the apply plugin in {module_build_gradle}: {e}")
            return False

    def add_allDeps_in_gradle(self, gradle_file):
        config = android_config if self.package_manager_name == const.ANDROID else gradle_config
        is_kts = gradle_file == 'build.gradle.kts'
        if is_kts:
            configuration = '\n'.join([
                f'                try {{ cfgs.add(project.configurations.getByName("{c}")) }} catch (e: Exception) {{}}'
                for c in config
            ])
            allDeps = f'''
                    allprojects {{
                        tasks.register("allDeps", org.gradle.api.tasks.diagnostics.DependencyReportTask::class) {{
                            doFirst {{
                                val cfgs = mutableSetOf<org.gradle.api.artifacts.Configuration>()
                    {configuration}
                                setConfigurations(cfgs)
                            }}
                        }}
                    }}'''
        else:
            configuration = ','.join([f'project.configurations.{c}' for c in config])
            allDeps = f'''
                    allprojects {{
                        task allDeps(type: DependencyReportTask) {{
                            doFirst{{
                                try {{
                                    configurations = [{configuration}] as Set }}
                                catch(UnknownConfigurationException) {{}}
                            }}
                        }}
                    }}'''
        try:
            with open(gradle_file, 'a', encoding='utf8') as f:
                f.write(f'\n{allDeps}\n')
            return True
        except Exception as e:
            logging.warning(f"Cannot add the allDeps task in build.gradle: {e}")
            return False

    def create_dep_stack(self, dep_line, config):
        packages_in_config = False
        dep_stack = []
        cur_flag = ''
        dep_level = -1
        dep_level_plus = False
        for line in dep_line.split('\n'):
            try:
                if not packages_in_config:
                    filtered = next(filter(lambda c: re.findall(rf'^{c}\s\-', line), config), None)
                    if filtered:
                        packages_in_config = True
                else:
                    if line == '':
                        packages_in_config = False
                    prev_flag = cur_flag
                    prev_dep_level = dep_level
                    dep_level = line.count("|")

                    re_result = re.findall(r'([\+|\\])\-\-\-\s([^\:\s]+\:[^\:\s]+)\:([^\:\s]+)', line)
                    if re_result:
                        cur_flag = re_result[0][0]
                        if (prev_flag == '\\') and (prev_dep_level == dep_level):
                            dep_level_plus = True
                        if dep_level_plus and (prev_flag == '\\') and (prev_dep_level != dep_level):
                            dep_level_plus = False
                        if dep_level_plus:
                            dep_level += 1
                        dep_name = f'{re_result[0][1]}({re_result[0][2]})'
                        dep_stack = dep_stack[:dep_level] + [dep_name]
                        yield dep_stack[:dep_level], dep_name
                    else:
                        cur_flag = ''
            except Exception as e:
                logger.warning(f"Failed to parse dependency tree: {e}")

    def parse_dependency_tree(self, f_name):
        config = android_config if self.package_manager_name == const.ANDROID else gradle_config

        try:
            for stack, name in self.create_dep_stack(f_name, config):
                self.total_dep_list.append(name)
                if len(stack) == 0:
                    self.direct_dep_list.append(name)
                else:
                    if stack[-1] not in self.relation_tree:
                        self.relation_tree[stack[-1]] = []
                    self.relation_tree[stack[-1]].append(name)
        except Exception as e:
            logger.warning(f'Fail to parse gradle dependency tree:{e}')


def get_url_to_purl(url, pkg_manager, oss_name='', oss_version=''):
    purl_prefix = f'pkg:{pkg_manager}'
    purl = str(url2purl.get_purl(url))
    if not re.match(purl_prefix, purl):
        match = re.match(constant.PKG_PATTERN.get(pkg_manager, 'not_support'), url)
        try:
            if match and (match != ''):
                if pkg_manager == 'maven':
                    purl = f'{purl_prefix}/{match.group(1)}/{match.group(2)}@{match.group(3)}'
                elif pkg_manager == 'pub':
                    purl = f'{purl_prefix}/{match.group(1)}@{match.group(2)}'
                elif pkg_manager == 'cocoapods':
                    match = re.match(r'([^\/]+)\/?([^\/]*)', oss_name)  # ex, GoogleUtilities/NSData+zlib
                    purl = f'{purl_prefix}/{match.group(1)}@{oss_version}'
                    if match.group(2):
                        purl = f'{purl}#{match.group(2)}'
                elif pkg_manager == 'go':
                    purl = f'{purl_prefix}lang/{match.group(1)}@{match.group(2)}'
                elif pkg_manager == 'cargo':
                    purl = f'{purl_prefix}/{oss_name}@{oss_version}'
            else:
                if pkg_manager == 'swift':
                    if oss_version:
                        purl = f'{purl_prefix}/{oss_name}@{oss_version}'
                    else:
                        purl = f'{purl_prefix}/{oss_name}'
                elif pkg_manager == 'carthage':
                    if oss_version:
                        purl = f'{purl}@{oss_version}'
        except Exception:
            logger.debug('Fail to get purl. So use the link purl({purl}).')
    return purl


def version_refine(oss_version):
    version_cmp = oss_version.upper()

    if version_cmp.find(".RELEASE") != -1:
        oss_version = version_cmp.rstrip(".RELEASE")
    elif version_cmp.find(".FINAL") != -1:
        oss_version = version_cmp.rstrip(".FINAL")

    return oss_version


def connect_github(github_token):
    if len(github_token) > 0:
        g = Github(github_token)
    else:
        g = Github()

    return g


def get_github_license(g, github_repo):
    license_name = ''

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
                    license_name = check_license_name(license_txt_data)
                except Exception:
                    logger.info("Cannot find the license name with askalono.")
        except Exception:
            logger.info("Cannot find the license name with github api.")

    return license_name


def check_license_name(license_txt, is_filepath=False):
    license_name = ''
    if is_filepath:
        with open(license_txt, 'r', encoding='utf-8') as f:
            license_content = f.read()
    else:
        license_content = license_txt

    detect_askalono = identify(license_content)
    if detect_askalono.score > ASKALONO_THRESHOLD:
        license_name = detect_askalono.name
    return license_name


def change_file_mode(filepath, mode=''):
    current_mode = ''

    if not os.path.exists(filepath):
        logger.debug(f"The file{filepath} does not exist.")
    else:
        current_mode = os.stat(filepath).st_mode
        if not mode:
            new_mode = current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        else:
            new_mode = mode
        os.chmod(filepath, new_mode)
        logger.debug(f"File mode of {filepath} has been changed to {oct(new_mode)}.")
    return current_mode


def deduplicate_dep_items(dep_items):
    if not dep_items:
        return dep_items

    unique_items = []
    seen = set()

    for item in dep_items:
        first_oss = item.oss_items[0] if getattr(item, "oss_items", None) else None
        oss_name = getattr(first_oss, "name", None) if first_oss else None
        oss_ver = getattr(first_oss, "version", None) if first_oss else None
        comment = getattr(first_oss, "comment", None) if first_oss else None

        depends_on = None
        if getattr(item, "depends_on", None):
            depends_on = tuple(sorted(item.depends_on))

        key = (getattr(item, "purl", None), oss_name, oss_ver, comment, depends_on)
        if key in seen:
            continue
        seen.add(key)
        unique_items.append(item)

    return unique_items


def get_gradle_cmd():
    cmd_gradle = ''
    current_mode = ''
    if os.path.isfile('gradlew') or os.path.isfile('gradlew.bat'):
        if platform.system() == const.WINDOWS:
            cmd_gradle = "gradlew.bat"
        else:
            cmd_gradle = "./gradlew"
            current_mode = change_file_mode(cmd_gradle)
    return cmd_gradle, current_mode


def collect_gradle_download_urls(input_dir, package_manager_name, app_name=None):
    download_url_map = {}
    cmd_gradle, current_mode = get_gradle_cmd()
    if not cmd_gradle:
        return download_url_map
    try:
        if app_name:
            cmd = [cmd_gradle, f':{app_name}:dependencies', '--refresh-dependencies', '--debug']
        else:
            cmd = [cmd_gradle, 'dependencies', '--debug']
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=input_dir, timeout=600)
        if proc.returncode == 0:
            download_url_map = parse_gradle_download_lines(proc.stdout, package_manager_name)
        else:
            logger.debug(f"[{package_manager_name}] Command '{cmd}' failed (rc={proc.returncode})")
    except subprocess.TimeoutExpired:
        logger.warning(f"[{package_manager_name}] Gradle dependencies command timed out")
    finally:
        if current_mode:
            change_file_mode(cmd_gradle, current_mode)

    return download_url_map


def parse_gradle_download_lines(stdout_text, package_manager_name=''):
    download_url_map = {}
    for raw in stdout_text.splitlines():
        line = raw.strip()
        try:
            if "Download " not in line and "Metadata of " not in line:
                continue
            m = re.search(r'(?:Download|Metadata of) (https?://\S+)', line)
            if not m:
                continue
            url = m.group(1)
            url = url.rstrip("'\")>,")
            m2 = re.match(r'([^-]+)-([0-9][^-]*?)(?:-sources)?\.(?:jar|pom|aar)', url.split('/')[-1])
            if not m2:
                continue
            artifactid = m2.group(1)
            version = m2.group(2)

            parts = url.split('/')
            art_idx = None
            for i, p in enumerate(parts):
                if p == artifactid and i + 1 < len(parts) and parts[i + 1] == version:
                    art_idx = i
                    break
            if art_idx is None or art_idx < 4:
                continue

            common_roots = ['com', 'org', 'io', 'net', 'edu', 'gov']
            group_start_idx = None
            for i in range(3, art_idx):
                if parts[i] in common_roots:
                    group_start_idx = i
                    break

            if group_start_idx is None:
                repo_keywords = [
                    'maven2', 'maven', 'repository', 'nexus', 'content',
                    'groups', 'public', 'releases', 'snapshots'
                ]
                group_parts = []
                for i in range(art_idx - 1, 2, -1):
                    part = parts[i]
                    if part.lower() in repo_keywords:
                        break
                    if part and re.match(r'^[a-z][a-z0-9\-]*$', part.lower()):
                        group_parts.insert(0, part)
                    else:
                        break
                if not group_parts:
                    continue
                groupid = '.'.join(group_parts)
            else:
                group_parts = parts[group_start_idx:art_idx]
                groupid = '.'.join(group_parts)

            key = f"{groupid}:{artifactid}:{version}"
            if '.pom' in url.split('/')[-1]:
                extension = '.aar' if package_manager_name == const.ANDROID else '.jar'
                url = url.replace('.pom', extension)
            tail = url.split('/')[-1]
            if '-sources.jar' in tail:
                download_url_map[key] = url
            elif key not in download_url_map or '-sources.jar' not in download_url_map[key]:
                if '.jar' in tail or '.aar' in tail:
                    download_url_map[key] = url
        except Exception as e:
            logger.debug(f"Failed to parse gradle URL: {url} ({e})")
            continue

    return download_url_map


def get_download_location(download_url_map, group_id, artifact_id, version, mvnrepo_url):
    actual_key = f"{group_id}:{artifact_id}:{version}"
    if download_url_map:
        try:
            actual_url = download_url_map.get(actual_key)

            use_mvnrepo = True
            if actual_url:
                central_like = ("repo1.maven.org" in actual_url) or ("repo.maven.apache.org" in actual_url)
                google_like = (("maven.google.com" in actual_url) or
                               ("dl.google.com/android/maven2" in actual_url) or
                               ("dl.google.com/dl/android/maven2" in actual_url))
                if central_like or google_like:
                    use_mvnrepo = True
                else:
                    use_mvnrepo = False
        except Exception as e:
            logger.debug(f"Failed to get download location from download_url_map: {e}")
            use_mvnrepo = True
    else:
        use_mvnrepo = True
    if use_mvnrepo:
        return f"{mvnrepo_url}{group_id}/{artifact_id}/{version}"
    else:
        return actual_url
