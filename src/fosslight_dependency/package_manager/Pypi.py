#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import subprocess
import json
import shutil
import copy
import re
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import check_license_name, get_url_to_purl
from fosslight_dependency.dependency_item import DependencyItem, change_dependson_to_purl
from fosslight_util.oss_item import OssItem

logger = logging.getLogger(constant.LOGGER_NAME)


class Pypi(PackageManager):
    package_manager_name = const.PYPI

    dn_url = 'https://pypi.org/project/'
    venv_tmp_dir = 'venv_osc_dep_tmp'
    tmp_file_name = "tmp_pip_license_output.json"
    tmp_pip_license_info_file_name = "tmp_pip_license_info_output.json"
    tmp_deptree_file = "tmp_pipdeptree.json"
    pip_activate_cmd = ''
    pip_deactivate_cmd = ''

    def __init__(self, input_dir, output_dir, pip_activate_cmd, pip_deactivate_cmd):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)

        self.pip_activate_cmd = pip_activate_cmd
        self.pip_deactivate_cmd = pip_deactivate_cmd

    def __del__(self):
        if os.path.isfile(self.tmp_file_name):
            os.remove(self.tmp_file_name)

        if os.path.isfile(self.tmp_pip_license_info_file_name):
            os.remove(self.tmp_pip_license_info_file_name)

        shutil.rmtree(self.venv_tmp_dir, ignore_errors=True)

        if os.path.isfile(self.tmp_deptree_file):
            os.remove(self.tmp_deptree_file)

    def set_pip_activate_cmd(self, pip_activate_cmd):
        self.pip_activate_cmd = pip_activate_cmd

    def set_pip_deactivate_cmd(self, pip_deactivate_cmd):
        self.pip_deactivate_cmd = pip_deactivate_cmd

    def run_plugin(self):
        ret = True

        req_f = 'requirements.txt'
        if os.path.exists(req_f):
            with open(req_f, encoding='utf8') as rf:
                for rf_line in rf.readlines():
                    ret_find = rf_line.find('--extra-index-url ')
                    if ret_find == -1:
                        ret_find = rf_line.find('--index-url ')
                    if ret_find == -1:
                        continue
                    self.cover_comment += rf_line

        if not self.pip_activate_cmd and not self.pip_deactivate_cmd:
            ret = self.create_virtualenv()

        if ret:
            ret = self.start_pip_licenses()

        return ret

    def create_virtualenv(self):
        ret = True

        manifest_files = self.manifest_file_name
        if not manifest_files:
            manifest_files = copy.deepcopy(const.SUPPORT_PACKAE[self.package_manager_name])
            self.set_manifest_file(manifest_files)

        install_cmd_list = []
        for manifest_file in manifest_files:
            if os.path.exists(manifest_file):
                if manifest_file == 'requirements.txt':
                    install_cmd_list.append("pip install -r requirements.txt")
                else:
                    install_cmd_list.append("pip install .")
            else:
                manifest_files.remove(manifest_file)
                self.set_manifest_file(manifest_files)

        venv_path = os.path.join(self.input_dir, self.venv_tmp_dir)

        if self.platform == const.WINDOWS:
            create_venv_cmd = f"python -m venv {self.venv_tmp_dir}"
            activate_cmd = os.path.join(self.venv_tmp_dir, "Scripts", "activate.bat")
            cmd_separator = "&"
        else:
            create_venv_cmd = f"python3 -m venv {self.venv_tmp_dir}"
            activate_cmd = ". " + os.path.join(venv_path, "bin", "activate")
            cmd_separator = ";"

        if install_cmd_list:
            install_cmd = cmd_separator.join(install_cmd_list)
        else:
            logger.error(const.SUPPORT_PACKAE[self.package_manager_name])
            logger.error('Cannot create virtualenv because it cannot find: '
                         + ', '.join(const.SUPPORT_PACKAE[self.package_manager_name]))
            logger.error("Please run with '-a' and '-d' option.")
            return False

        deactivate_cmd = "deactivate"

        self.set_pip_activate_cmd(activate_cmd)
        self.set_pip_deactivate_cmd(deactivate_cmd)

        cmd_list = [create_venv_cmd, activate_cmd, install_cmd, deactivate_cmd]
        cmd = cmd_separator.join(cmd_list)

        try:
            cmd_ret = subprocess.run(cmd, shell=True, stderr=subprocess.PIPE)
            if cmd_ret.returncode != 0:
                ret = False
                err_msg = f"return code({cmd_ret.returncode})"
            elif cmd_ret.stderr.decode('utf-8').strip().lower().startswith('error:'):
                ret = False
                err_msg = f"stderr msg({cmd_ret.stderr})"
        except Exception as e:
            ret = False
            err_msg = e
        finally:
            try:
                if (not ret) and (self.platform != const.WINDOWS):
                    ret = True
                    create_venv_cmd = f"virtualenv -p python3 {self.venv_tmp_dir}"

                    cmd_list = [create_venv_cmd, activate_cmd, install_cmd, deactivate_cmd]
                    cmd = cmd_separator.join(cmd_list)
                    cmd_ret = subprocess.run(cmd, shell=True, stderr=subprocess.PIPE)
                    if cmd_ret.returncode != 0:
                        ret = False
                        err_msg = f"return code({cmd_ret.returncode})"
                    elif cmd_ret.stderr.decode('utf-8').strip().lower().startswith('error:'):
                        ret = False
                        err_msg = f"stderr msg({cmd_ret.stderr})"
            except Exception as e:
                ret = False
                err_msg = e
            if ret:
                logger.info(f"Created the temporary virtualenv({venv_path}).")
            else:
                logger.error(f"Failed to create virtualenv: {err_msg}")

        return ret

    def start_pip_licenses(self):
        ret = True
        pip_licenses = 'pip-licenses'
        prettytable = 'prettytable'
        wcwidth = 'wcwidth'
        pipdeptree = 'pipdeptree'
        pip_licenses_default_options = ' --from=mixed --with-url --format=json --with-license-file'
        pip_licenses_system_option = ' --with-system -p '
        tmp_pip_list = "tmp_list.txt"
        python_cmd = "python -m"

        if self.pip_activate_cmd.startswith("source "):
            tmp_activate = self.pip_activate_cmd[7:]
            pip_activate_cmd = f". {tmp_activate}"
        elif self.pip_activate_cmd.startswith("conda "):
            if self.platform == const.LINUX:
                tmp_activate = "eval \"$(conda shell.bash hook)\";"
                pip_activate_cmd = tmp_activate + self.pip_activate_cmd
        else:
            pip_activate_cmd = self.pip_activate_cmd

        if self.platform == const.WINDOWS:
            command_separator = "&"
        else:
            command_separator = ";"

        activate_command = pip_activate_cmd
        pip_list_command = f"{python_cmd} pip freeze > {tmp_pip_list}"
        deactivate_command = self.pip_deactivate_cmd

        command_list = [activate_command, pip_list_command, deactivate_command]
        command = command_separator.join(command_list)

        try:
            cmd_ret = subprocess.call(command, shell=True)
            if cmd_ret != 0:
                ret = False
                err_msg = f"cmd ret code({cmd_ret})"
        except Exception as e:
            ret = False
            err_msg = str(e)
        finally:
            if not ret:
                logger.error(f"Failed to freeze dependencies ({command}): {err_msg})")
                return False

        exists_pip_licenses = False
        exists_prettytable = False
        exists_wcwidth = False
        pip_license_pkg_list = []
        uninstall_pkg_list = []
        exists_pipdeptree = False

        if os.path.isfile(tmp_pip_list):
            try:
                with open(tmp_pip_list, 'r', encoding='utf-8') as pip_list_file:
                    for pip_list in pip_list_file.readlines():
                        pip_list_name = pip_list.split('==')[0]
                        if pip_list_name == pip_licenses:
                            exists_pip_licenses = True
                        if pip_list_name == prettytable:
                            exists_prettytable = True
                        if pip_list_name == wcwidth:
                            exists_wcwidth = True
                        if pip_list_name == pipdeptree:
                            exists_pipdeptree = True
                os.remove(tmp_pip_list)
            except Exception as e:
                logger.error(f"Failed to read freezed package list file: {e}")
                return False
        if exists_pip_licenses:
            pip_license_pkg_list.append(pip_licenses)
        else:
            uninstall_pkg_list.append(pip_licenses)
        if exists_prettytable:
            pip_license_pkg_list.append(prettytable)
        else:
            uninstall_pkg_list.append(prettytable)
        if exists_wcwidth:
            pip_license_pkg_list.append(wcwidth)
        else:
            uninstall_pkg_list.append(wcwidth)

        command_list = []
        command_list.append(activate_command)
        if not exists_pip_licenses:
            install_pip_command = f"{python_cmd} pip install {pip_licenses}"
            command_list.append(install_pip_command)

        pip_licenses_command = f"{pip_licenses}{pip_licenses_default_options} > {self.tmp_file_name}"
        command_list.append(pip_licenses_command)

        if len(pip_license_pkg_list) != 0:
            pip_licenses_info_command = f"{pip_licenses}{pip_licenses_default_options}{pip_licenses_system_option}"
            pip_licenses_info_command += " ".join(pip_license_pkg_list)

            pip_licenses_info_command += f" > {self.tmp_pip_license_info_file_name}"
            command_list.append(pip_licenses_info_command)

        if len(uninstall_pkg_list) > 0:
            uninstall_pip_command = f"{python_cmd} pip uninstall -y "
            uninstall_pip_command += ' '.join(uninstall_pkg_list)
            command_list.append(uninstall_pip_command)

        if not exists_pipdeptree:
            install_deptree_command = f"{python_cmd} pip install {pipdeptree}"
            command_list.append(install_deptree_command)
            uninstall_deptree_command = f"{python_cmd} pip uninstall -y {pipdeptree}"
        pipdeptree_command = f"{pipdeptree} --json-tree -e 'pipdeptree,pip,wheel,setuptools' > {self.tmp_deptree_file}"
        command_list.append(pipdeptree_command)
        command_list.append(uninstall_deptree_command)
        command_list.append(deactivate_command)
        command = command_separator.join(command_list)

        try:
            cmd_ret = subprocess.call(command, shell=True)
            if cmd_ret == 0:
                self.append_input_package_list_file(self.tmp_file_name)
                with open(self.tmp_file_name, 'r', encoding='utf-8') as json_f:
                    json_data = json.load(json_f)
                    for d in json_data:
                        self.total_dep_list.append(re.sub(r"[-_.]+", "-", d['Name']).lower())
                if len(pip_license_pkg_list) != 0:
                    self.append_input_package_list_file(self.tmp_pip_license_info_file_name)
                    with open(self.tmp_pip_license_info_file_name, 'r', encoding='utf-8') as json_f:
                        json_data = json.load(json_f)
                        for d in json_data:
                            self.total_dep_list.append(re.sub(r"[-_.]+", "-", d['Name']).lower())
            else:
                logger.error(f"Failed to run command: {command}")
                ret = False
        except Exception as e:
            ret = False
            logger.error(f"Failed to install/uninstall pypi packages: {e}")

        return ret

    def parse_oss_information(self, f_name):
        purl_dict = {}
        try:
            oss_init_name = ''
            with open(f_name, 'r', encoding='utf-8') as json_file:
                json_data = json.load(json_file)

            for d in json_data:
                dep_item = DependencyItem()
                oss_item = OssItem()
                oss_init_name = d['Name']
                oss_init_name = re.sub(r"[-_.]+", "-", oss_init_name).lower()
                oss_item.name = f"{self.package_manager_name}:{oss_init_name}"
                license_name = check_UNKNOWN(d['License'])
                oss_item.homepage = check_UNKNOWN(d['URL'])
                oss_item.version = d['Version']
                oss_item.download_location = f"{self.dn_url}{oss_init_name}/{oss_item.version}"
                dep_item.purl = get_url_to_purl(oss_item.download_location, self.package_manager_name)
                purl_dict[f'{oss_init_name}({oss_item.version})'] = dep_item.purl
                if license_name is not None:
                    license_name = license_name.replace(';', ',')
                else:
                    license_name = check_license_name(d['LicenseFile'], True)
                oss_item.license = license_name

                if oss_init_name == self.package_name:
                    oss_item.comment = 'root package'
                elif self.direct_dep and len(self.direct_dep_list) > 0:
                    if f'{oss_init_name}({oss_item.version})' in self.direct_dep_list:
                        oss_item.comment = 'direct'
                    else:
                        oss_item.comment = 'transitive'
                    if f'{oss_init_name}({oss_item.version})' in self.relation_tree:
                        dep_item.depends_on_raw = self.relation_tree[f'{oss_init_name}({oss_item.version})']

                dep_item.oss_items.append(oss_item)
                self.dep_items.append(dep_item)

        except Exception as ex:
            logger.warning(f"Fail to parse oss information: {oss_init_name}({ex})")
        if self.direct_dep:
            self.dep_items = change_dependson_to_purl(purl_dict, self.dep_items)
        return

    def get_dependencies(self, dependencies, package):
        package_name = 'package_name'
        deps = 'dependencies'
        installed_ver = 'installed_version'

        pkg_name = re.sub(r"[-_.]+", "-", package[package_name]).lower()
        pkg_ver = package[installed_ver]
        dependency_list = package[deps]
        dependencies[f"{pkg_name}({pkg_ver})"] = []
        for dependency in dependency_list:
            dep_name = re.sub(r"[-_.]+", "-", dependency[package_name]).lower()
            dep_version = dependency[installed_ver]
            dependencies[f"{pkg_name}({pkg_ver})"].append(f"{dep_name}({dep_version})")
            if dependency[deps] != []:
                dependencies = self.get_dependencies(dependencies, dependency)
        return dependencies

    def parse_direct_dependencies(self):
        self.direct_dep = True
        if not os.path.exists(self.tmp_deptree_file):
            self.direct_dep = False
            return
        try:
            with open(self.tmp_deptree_file, 'r', encoding='utf8') as f:
                json_f = json.load(f)
                root_package = json_f
                if ('pyproject.toml' in self.manifest_file_name) or ('setup.py' in self.manifest_file_name):
                    direct_without_system_package = 0
                    for package in root_package:
                        package_name = re.sub(r"[-_.]+", "-", package['package_name']).lower()
                        if package_name in self.total_dep_list:
                            direct_without_system_package += 1
                    if direct_without_system_package == 1:
                        self.package_name = re.sub(r"[-_.]+", "-", json_f[0]['package_name']).lower()
                        root_package = json_f[0]['dependencies']

                for package in root_package:
                    package_name = re.sub(r"[-_.]+", "-", package['package_name']).lower()
                    self.direct_dep_list.append(f"{package_name}({package['installed_version']})")
                    if package['dependencies'] == []:
                        continue
                    self.relation_tree = self.get_dependencies(self.relation_tree, package)
        except Exception as e:
            logger.warning(f'Fail to parse direct dependency: {e}')


def check_UNKNOWN(text):
    if text == ['UNKNOWN'] or text == 'UNKNOWN':
        text = ""
    return text
