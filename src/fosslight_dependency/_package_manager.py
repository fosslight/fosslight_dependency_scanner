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
import requests
from packageurl import PackageURL
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
FOSSLIGHT_ALL_DEPS_TASK = 'fosslightAllDeps'

_GROOVY_LICENSE_REPORT_IMPORTS = (
    'import com.github.jk1.license.ModuleData\n'
    'import com.github.jk1.license.ProjectData\n'
    'import com.github.jk1.license.render.ReportRenderer\n'
    'import static com.github.jk1.license.render.LicenseDataCollector.multiModuleLicenseInfo\n'
    '\n'
)

_KTS_LICENSE_REPORT_IMPORTS = (
    'import com.github.jk1.license.ModuleData\n'
    'import com.github.jk1.license.ProjectData\n'
    'import com.github.jk1.license.render.ReportRenderer\n'
    'import com.github.jk1.license.render.LicenseDataCollector.multiModuleLicenseInfo\n'
    'import java.io.File\n'
    '\n'
)


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
        self._reset_state()

    def _reset_state(self):
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

    def _get_java_version(self):
        java_bin = os.getenv("JAVA_HOME")
        if java_bin:
            java_bin = os.path.join(java_bin, "bin", "java")
        else:
            java_bin = "java"

        try:
            cmd = [java_bin, "-version"]
            result = self._run_command(cmd)
        except FileNotFoundError:
            logger.error("[Java] 'java' command was not found in PATH.")
            return False
        except subprocess.TimeoutExpired:
            logger.error("[Java] Timeout while checking Java version.")
            return False

        version_text = result.stderr or result.stdout or ""
        match = re.search(r'version "([^"]+)"', version_text)

        if not match:
            logger.error(f"[Java] Could not parse Java version: {version_text}")
            return False

        raw_value = match.group(1).strip()
        if not raw_value:
            logger.error(f"[Java] Could not parse Java version: {version_text}")
            return False

        major = None
        text = str(raw_value).strip()
        if text.startswith('1.'):
            parts = text.split('.')
            if len(parts) >= 2:
                try:
                    major = int(parts[1])
                except ValueError:
                    pass
        if major is None:
            try:
                major = int(text)
            except ValueError:
                try:
                    major = int(text.split('.')[0])
                except ValueError:
                    pass

        if major is None:
            logger.error(f"[Java] Could not parse Java version: {version_text}")
            return False

        logger.info(
            f"Java Version : Java {major} "
            f"({version_text.splitlines()[0].strip()})"
        )
        return major

    def _resolve_wrapper_command(self):
        if self.platform == const.WINDOWS:
            return 'gradlew.bat' if os.path.isfile('gradlew.bat') else ''
        if os.path.isfile('gradlew'):
            return './gradlew'
        return ''

    def _run_command_output(self, cmd):
        return subprocess.check_output(cmd, encoding='utf-8')

    def _run_command(self, cmd):
        return subprocess.run(cmd, capture_output=True, encoding='utf-8')

    def run_plugin(self):
        ret = True

        java_ver = self._get_java_version()
        if java_ver is False:
            return False

        if self.package_manager_name in (const.GRADLE, const.ANDROID):
            gradle_ver = get_gradle_version_from_wrapper(self.input_dir)

            if gradle_ver is None:
                logger.info('Gradle wrapper version is not available. Skipping Java version check.')
            else:
                min_java_ver = 8
                max_java_ver = None
                requirement_text = 'Java 8 or higher'

                if gradle_ver >= (9, 0):
                    min_java_ver = 17
                    requirement_text = 'Java 17 or higher'
                elif gradle_ver >= (8, 5):
                    min_java_ver = 11
                    requirement_text = 'Java 11 or higher'
                elif gradle_ver >= (7, 3):
                    min_java_ver = 11
                    max_java_ver = 17
                    requirement_text = 'from Java 11 to Java 17'

                if java_ver < min_java_ver or (max_java_ver is not None and java_ver > max_java_ver):
                    logger.warning(
                        f'Gradle {gradle_ver[0]}.{gradle_ver[1]} requires {requirement_text}. '
                        'Please check your Java version.'
                    )
                    return False

        elif self.package_manager_name == const.MAVEN:
            pom_ver = get_java_version_from_pom(self.input_dir)
            maven_ver = get_maven_version()

            min_java_ver = 7
            if maven_ver is not None:
                if maven_ver >= (4, 0):
                    min_java_ver = 17
                elif maven_ver >= (3, 9):
                    min_java_ver = 8

            if pom_ver is not None and pom_ver > min_java_ver:
                min_java_ver = pom_ver

            if java_ver < min_java_ver:
                logger.warning(
                    f'Maven requires Java {min_java_ver} or higher. '
                    f'Current Java version is {java_ver}. Please check your Java version.'
                )
                return False

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

    def _run_gradle_plugin_task(self, cmd_gradle):
        if self.package_manager_name == const.ANDROID:
            cmd = [cmd_gradle, f':{self.app_name}:generateLicenseTxt']
            plugin_label = 'android-dependency-scanning'
        elif self.package_manager_name == const.GRADLE:
            cmd = [cmd_gradle, 'generateLicenseReport', '--no-parallel']
            plugin_label = 'gradle-license-report'
        else:
            return True

        logger.info(f"Execute Gradle task: {' '.join(cmd)}")
        try:
            result = self._run_command(cmd)
            if result.returncode != 0:
                logger.error(f'Cannot run Gradle task {" ".join(cmd)}: {result.stderr.strip()}')
                return False
            if os.path.isfile(self.input_file_name):
                logger.info(f'Generate output with {plugin_label} plugin.')
                self.plugin_auto_run = True
                return True

            logger.warning(f'Generate output with {plugin_label} plugin fails.')
            return False
        except Exception as e:
            logger.error(f'Cannot run Gradle task {" ".join(cmd)}: {e}')
            return False

    def _run_fosslight_all_deps_task(self, cmd_gradle):
        cmd = [cmd_gradle, FOSSLIGHT_ALL_DEPS_TASK]
        logger.info(f"Execute Gradle task: {' '.join(cmd)}")
        try:
            dep_output = self._run_command_output(cmd)
            if dep_output:
                self.parse_dependency_tree(dep_output)
                self.set_direct_dependencies(bool(self.direct_dep_list))
                return True

            self.set_direct_dependencies(False)
            logger.warning(f"Cannot run Gradle task {' '.join(cmd)}")
            return False
        except Exception as e:
            self.set_direct_dependencies(False)
            logger.warning(f"Cannot print 'depends on' information. (cannot run {cmd}: {e})")
            return False

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

                # Inject plugin first (overwrites file with write mode)
                ret_plugin = False
                if self.package_manager_name == const.ANDROID:
                    module_build_gradle = os.path.join(self.app_name, gradle_file)
                    module_gradle_backup = f'{module_build_gradle}_bk'
                    if os.path.isfile(module_build_gradle) and (not os.path.isfile(self.input_file_name)):
                        shutil.copy(module_build_gradle, module_gradle_backup)
                        ret_plugin = self.add_android_plugin_in_gradle(module_build_gradle, gradle_file)
                elif self.package_manager_name == const.GRADLE:
                    if not os.path.isfile(self.input_file_name):
                        ret_plugin = self.add_gradle_plugin_in_gradle(gradle_file)

                cmd_gradle = self._resolve_wrapper_command()
                if not cmd_gradle:
                    ret_task = False
                    self.set_direct_dependencies(False)
                    logger.warning('No gradlew file exists (Skip to find dependencies relationship.).')
                    if ret_plugin:
                        if self.package_manager_name == const.ANDROID:
                            logger.warning('Also it cannot run android-dependency-scanning plugin.')
                        else:
                            logger.warning('Also it cannot run gradle-license-report plugin.')

                if ret_task:
                    if not ret_plugin:
                        logger.warning('Skip the Gradle plugin (gradle-license-report or android-dependency-scanning).')

                    ret_alldeps = self.add_allDeps_in_gradle(gradle_file)
                    current_mode, changed_mode = ensure_executable(cmd_gradle)
                    if ret_plugin:
                        ret_task = self._run_gradle_plugin_task(cmd_gradle) and ret_task

                    if ret_alldeps:
                        self._run_fosslight_all_deps_task(cmd_gradle)
                    if changed_mode:
                        change_file_mode(cmd_gradle, current_mode)

            if os.path.isfile(self.input_file_name):
                logger.info(f'Found {self.input_file_name}.')
                self.set_direct_dependencies(bool(self.direct_dep_list))
                ret_task = True
            elif self.package_manager_name == const.GRADLE:
                ret_task = False
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

    def add_gradle_plugin_in_gradle(self, gradle_file):
        is_kts = gradle_file == 'build.gradle.kts'

        try:
            with open(gradle_file, 'r', encoding='utf-8') as f:
                data = f.read()

            plugin_declared = 'com.github.jk1.dependency-license-report' in data
            if plugin_declared:
                logger.info('Skip plugin injection because gradle-license-report is already configured.')
                return True

        except Exception as e:
            logger.warning(f"Cannot read {gradle_file}: {e}")
            return False

        gradle_ver = get_gradle_version_from_wrapper(self.input_dir)
        if gradle_ver and gradle_ver >= (9, 0):   # Gradle 9+
            plugin_version = '3.1.4'
        elif gradle_ver and gradle_ver >= (7, 0):    # Gradle 7+
            plugin_version = '2.9'
        else:
            plugin_version = '1.9'

        if is_kts:
            imports = _KTS_LICENSE_REPORT_IMPORTS
            plugin_id_line, license_report_block = _build_kts_license_report_config(plugin_version)
        else:
            imports = _GROOVY_LICENSE_REPORT_IMPORTS
            plugin_id_line, license_report_block = _build_groovy_license_report_config(plugin_version)

        try:
            data = imports + data

            if not plugin_declared:
                if 'plugins {' in data:
                    plugins_start = data.index('plugins {')
                    brace_count = 0
                    search_pos = plugins_start + len('plugins {')
                    plugins_end = -1

                    for i in range(search_pos, len(data)):
                        if data[i] == '{':
                            brace_count += 1
                        elif data[i] == '}':
                            if brace_count == 0:
                                plugins_end = i
                                break
                            brace_count -= 1

                    if plugins_end > 0:
                        data = data[:plugins_end] + plugin_id_line + data[plugins_end:]
                    else:
                        logger.warning("Could not find closing brace for plugins block")
                        return False
                else:
                    new_plugins_block = f'plugins {{\n{plugin_id_line}}}\n'
                    data = _insert_plugins_block_after_buildscript(data, new_plugins_block)

            data = data + license_report_block

            with open(gradle_file, 'w', encoding='utf-8') as f:
                f.write(data)

            logger.info(f'Injected gradle-license-report plugin (v{plugin_version}) into {gradle_file}.')
            return True

        except Exception as e:
            logger.warning(f"Cannot inject gradle-license-report plugin into {gradle_file}: {e}")
            return False

    def add_allDeps_in_gradle(self, gradle_file):
        config = android_config if self.package_manager_name == const.ANDROID else gradle_config
        is_kts = gradle_file == 'build.gradle.kts'

        try:
            with open(gradle_file, 'r', encoding='utf-8') as f:
                data = f.read()
            if (
                f'task {FOSSLIGHT_ALL_DEPS_TASK}' in data
                or f'tasks.register("{FOSSLIGHT_ALL_DEPS_TASK}"' in data
                or f"tasks.register('{FOSSLIGHT_ALL_DEPS_TASK}'" in data
            ):
                logger.info(
                    f'Skip injection because {FOSSLIGHT_ALL_DEPS_TASK} task already exists in build.gradle; '
                    'the existing task will be executed.'
                )
                return True
        except Exception as e:
            logger.warning(f"Cannot read {gradle_file}: {e}")
            return False

        allDeps = _build_kts_all_deps_block(config) if is_kts else _build_groovy_all_deps_block(config)

        try:
            with open(gradle_file, 'a', encoding='utf8') as f:
                f.write(f'\n{allDeps}\n')
            logger.info(f'Inject {FOSSLIGHT_ALL_DEPS_TASK} configuration into {gradle_file}.')
            return True
        except Exception as e:
            logger.warning(f"Cannot add the {FOSSLIGHT_ALL_DEPS_TASK} task in build.gradle: {e}")
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


def _find_block_end(content, keyword):
    start = content.find(keyword)
    if start == -1:
        return -1

    open_brace_pos = content.find('{', start)
    if open_brace_pos == -1:
        return -1

    brace_depth = 0
    quote_char = None
    escaped = False

    for idx in range(open_brace_pos, len(content)):
        char = content[idx]
        next_char = content[idx + 1] if idx + 1 < len(content) else ''

        if quote_char is not None:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote_char:
                quote_char = None
            continue

        if char == '/' and next_char == '/':
            while idx < len(content) and content[idx] != '\n':
                idx += 1
            continue

        if char == '/' and next_char == '*':
            idx += 2
            while idx + 1 < len(content) and not (content[idx] == '*' and content[idx + 1] == '/'):
                idx += 1
            continue

        if char in {"'", '"'}:
            quote_char = char
            continue

        if char == '{':
            brace_depth += 1
        elif char == '}':
            brace_depth -= 1
            if brace_depth == 0:
                return idx

    return -1


def _insert_plugins_block_after_buildscript(content, plugin_block):
    if not plugin_block:
        return content

    buildscript_keywords = ['buildscript {', 'buildscript{']
    buildscript_end = -1
    for keyword in buildscript_keywords:
        buildscript_end = _find_block_end(content, keyword)
        if buildscript_end != -1:
            break

    if buildscript_end != -1:
        return content[:buildscript_end + 1] + f'\n{plugin_block}\n' + content[buildscript_end + 1:]

    return plugin_block + '\n' + content


def _build_groovy_license_report_config(plugin_version):
    plugin_id_line = f'  id "com.github.jk1.dependency-license-report" version "{plugin_version}"\n'
    output_property = 'outputDir' if plugin_version in ('1.9', '2.9') else 'absoluteOutputDir'

    renderer_body = f'''                def outputFile = new File(
                    data.project.licenseReport.{output_property},
                    "dependency-license.json"
                )
                outputFile.parentFile.mkdirs()
                def result = []
                data.allDependencies.each {{ ModuleData module ->
                    def info = multiModuleLicenseInfo(module)
                    def licenses = info.licenses.collect {{ lic ->
                        [name: lic.name, url: lic.url]
                    }}
                    result << [
                        moduleName    : "${{module.group}}:${{module.name}}",
                        moduleVersion : module.version,
                        moduleUrls    : info.moduleUrls,
                        moduleLicenses: licenses
                    ]
                }}

                def json = groovy.json.JsonOutput.prettyPrint(groovy.json.JsonOutput.toJson(result))
                outputFile.text = json'''

    license_report_block = (
        '\nlicenseReport {\n'
        "    configurations = ['runtimeClasspath']\n"
        '    outputDir = "${project.layout.buildDirectory.get().asFile}/reports/license"\n'
        '    renderers = [\n'
        '        new ReportRenderer() {\n'
        '            @Override\n'
        '            void render(ProjectData data) {\n'
        f'{renderer_body}\n'
        '            }\n'
        '        }\n'
        '    ]\n'
        '}\n'
    )
    return plugin_id_line, license_report_block


def _build_kts_license_report_config(plugin_version):
    plugin_id_line = f'    id("com.github.jk1.dependency-license-report") version "{plugin_version}"\n'
    output_config = '    outputDir = "${project.layout.buildDirectory.get().asFile}/reports/license"'
    output_property_access = 'outputDir' if plugin_version in ('1.9', '2.9') else 'absoluteOutputDir'

    custom_renderer_body_kts = f'''                val outputFile = File(
                    data.project.licenseReport.{output_property_access},
                    "dependency-license.json"
                )
                outputFile.parentFile.mkdirs()

                val result = mutableListOf<Map<String, Any>>()

                data.allDependencies.forEach {{ module ->
                    val info = multiModuleLicenseInfo(module)
                    val moduleLicenses = info.licenses.map {{ lic ->
                        mapOf("name" to lic.name, "url" to lic.url)
                    }}

                    result.add(mapOf(
                        "moduleName" to "${{module.group}}:${{module.name}}",
                        "moduleVersion" to module.version,
                        "moduleUrls" to info.moduleUrls,
                        "moduleLicenses" to moduleLicenses
                    ))
                }}

                val json = groovy.json.JsonOutput.prettyPrint(groovy.json.JsonOutput.toJson(result))
                outputFile.writeText(json)'''

    license_report_block = (
        '\nlicenseReport {\n'
        '    configurations = arrayOf("runtimeClasspath")\n'
        f'{output_config}\n'
        '    renderers = arrayOf(\n'
        '        object : ReportRenderer {\n'
        '            override fun render(data: ProjectData) {\n'
        f'{custom_renderer_body_kts}\n'
        '            }\n'
        '        }\n'
        '    )\n'
        '}\n'
    )
    return plugin_id_line, license_report_block


def _build_groovy_all_deps_block(config):
    configuration = ','.join([f'project.configurations.{c}' for c in config])
    return f'''
                    allprojects {{
                        if (!tasks.names.contains("{FOSSLIGHT_ALL_DEPS_TASK}")) {{
                            task {FOSSLIGHT_ALL_DEPS_TASK}(type: DependencyReportTask) {{
                                doFirst{{
                                    try {{
                                        configurations = [{configuration}] as Set }}
                                    catch(UnknownConfigurationException) {{}}
                                }}
                            }}
                        }}
                    }}'''


def _build_kts_all_deps_block(config):
    configuration = '\n'.join([
        f'                try {{ cfgs.add(project.configurations.getByName("{c}")) }} catch (e: Exception) {{}}'
        for c in config
    ])
    return f'''
                    allprojects {{
                        if (!tasks.names.contains("{FOSSLIGHT_ALL_DEPS_TASK}")) {{
                            tasks.register("{FOSSLIGHT_ALL_DEPS_TASK}",
                            org.gradle.api.tasks.diagnostics.DependencyReportTask::class) {{
                                doFirst {{
                                    val cfgs = mutableSetOf<org.gradle.api.artifacts.Configuration>()
                    {configuration}
                                    setConfigurations(cfgs)
                                }}
                            }}
                        }}
                    }}'''


def get_gradle_version_from_wrapper(input_dir):
    props_path = os.path.join(input_dir, 'gradle', 'wrapper', 'gradle-wrapper.properties')
    if not os.path.isfile(props_path):
        return None
    try:
        with open(props_path, 'r', encoding='utf-8') as f:
            content = f.read()
        m = re.search(r'gradle-(\d+\.\d+(?:\.\d+)?)-', content)
        if m:
            return tuple(int(x) for x in m.group(1).split('.'))
    except Exception:
        pass
    return None


def get_java_version_from_pom(input_dir):
    pom_path = os.path.join(input_dir, 'pom.xml')
    if not os.path.isfile(pom_path):
        return None

    try:
        with open(pom_path, 'r', encoding='utf-8') as f:
            content = f.read()

        patterns = [
            r"<maven\.compiler\.release>([^<]+)</maven\.compiler\.release>",
            r"<maven\.compiler\.source>([^<]+)</maven\.compiler\.source>",
            r"<maven\.compiler\.target>([^<]+)</maven\.compiler\.target>",
            r"<java\.version>([^<]+)</java\.version>",
        ]

        candidates = []
        for pattern in patterns:
            match = re.search(pattern, content)
            if not match:
                continue

            raw_value = match.group(1).strip()
            if not raw_value:
                continue

            normalized = None
            text = str(raw_value).strip()
            if text.startswith('1.'):
                parts = text.split('.')
                if len(parts) >= 2:
                    try:
                        normalized = int(parts[1])
                    except ValueError:
                        pass
            if normalized is None:
                try:
                    normalized = int(text)
                except ValueError:
                    try:
                        normalized = int(text.split('.')[0])
                    except ValueError:
                        pass
            if normalized is not None:
                candidates.append(normalized)

        return max(candidates) if candidates else None

    except Exception:
        return None


def get_maven_version():
    try:
        result = subprocess.run(['mvn', '-version'], capture_output=True, text=True)
        if result.returncode != 0:
            return None

        version_line = next((line for line in result.stdout.splitlines() if line.startswith('Apache Maven')), None)
        if not version_line:
            return None

        match = re.search(r'(\d+(?:\.\d+){0,2})', version_line)
        if match:
            return tuple(int(x) for x in match.group(1).split('.'))
    except Exception:
        pass

    return None


def get_url_to_purl(url, pkg_manager, oss_name='', oss_version=''):
    purl_prefix = f'pkg:{pkg_manager}'

    if pkg_manager == 'swift':
        if not oss_name:
            return ''

        cleaned_name = oss_name.strip('/')
        if not cleaned_name:
            return ''

        namespace = ''
        name = cleaned_name
        if '/' in cleaned_name:
            namespace, name = cleaned_name.rsplit('/', 1)

        purl_obj = PackageURL(type='swift', namespace=namespace, name=name, version=oss_version or None)
        return str(purl_obj)

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


def ensure_executable(filepath):
    if not os.path.exists(filepath):
        logger.debug(f"The file{filepath} does not exist.")
        return '', False

    current_mode = os.stat(filepath).st_mode
    executable_bits = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH

    if os.access(filepath, os.X_OK):
        return current_mode, False

    new_mode = current_mode | executable_bits
    os.chmod(filepath, new_mode)
    return current_mode, True


def change_file_mode(filepath, mode=''):
    if not os.path.exists(filepath):
        logger.debug(f"The file{filepath} does not exist.")
        return ''

    current_mode = os.stat(filepath).st_mode
    new_mode = current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH if not mode else mode
    if current_mode != new_mode:
        os.chmod(filepath, new_mode)
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
    changed_mode = False
    if os.path.isfile('gradlew') or os.path.isfile('gradlew.bat'):
        if platform.system() == const.WINDOWS:
            cmd_gradle = "gradlew.bat"
        else:
            cmd_gradle = "./gradlew"
            current_mode, changed_mode = ensure_executable(cmd_gradle)
    return cmd_gradle, current_mode, changed_mode


def collect_gradle_download_urls(input_dir, package_manager_name, app_name=None):
    download_url_map = {}
    cmd_gradle, current_mode, changed_mode = get_gradle_cmd()
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
        if changed_mode and current_mode and os.path.exists(cmd_gradle):
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
    actual_url = download_url_map.get(actual_key) if download_url_map else None
    if actual_url:
        if any(host in actual_url for host in ("repo1.maven.org", "repo.maven.apache.org")):
            return f"{mvnrepo_url}{group_id}/{artifact_id}/{version}"
        if not any(host in actual_url for host in (
                "maven.google.com", "dl.google.com/android/maven2", "dl.google.com/dl/android/maven2")):
            return actual_url
    return get_google_maven_url(mvnrepo_url, group_id, artifact_id, version)


def get_google_maven_url(mvnrepo_url, group_id, artifact_id, version):
    group_path = group_id.replace('.', '/')
    pom_url = (f"https://dl.google.com/dl/android/maven2"
               f"/{group_path}/{artifact_id}/{version}/{artifact_id}-{version}.pom")
    try:
        resp = requests.head(pom_url, timeout=5, allow_redirects=True)
        if resp.status_code == 200:
            return f"https://maven.google.com/web/index.html#{group_id}:{artifact_id}:{version}"
    except Exception:
        logger.debug(f"Failed to check Google Maven URL: {pom_url}")
    return f"{mvnrepo_url}{group_id}/{artifact_id}/{version}"
