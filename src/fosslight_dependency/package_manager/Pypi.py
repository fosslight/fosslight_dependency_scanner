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
import requirements
import ast
import re
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import check_and_run_license_scanner

logger = logging.getLogger(constant.LOGGER_NAME)


class Pypi(PackageManager):
    package_manager_name = const.PYPI

    dn_url = 'https://pypi.org/project/'
    venv_tmp_dir = 'venv_osc_dep_tmp'
    tmp_file_name = "tmp_pip_license_output.json"
    tmp_pip_license_info_file_name = "tmp_pip_license_info_output.json"
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

    def set_pip_activate_cmd(self, pip_activate_cmd):
        self.pip_activate_cmd = pip_activate_cmd

    def set_pip_deactivate_cmd(self, pip_deactivate_cmd):
        self.pip_deactivate_cmd = pip_deactivate_cmd

    def run_plugin(self):
        ret = True

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
                if manifest_file == 'setup.py':
                    install_cmd_list.append("pip install .")
                elif manifest_file == 'requirements.txt':
                    install_cmd_list.append("pip install -r requirements.txt")
            else:
                manifest_files.remove(manifest_file)
                self.set_manifest_file(manifest_files)

        venv_path = os.path.join(self.input_dir, self.venv_tmp_dir)

        if self.platform == const.WINDOWS:
            create_venv_cmd = f"python -m venv {self.venv_tmp_dir}"
            activate_cmd = os.path.join(self.venv_tmp_dir, "Scripts", "activate.bat")
            cmd_separator = "&"
        else:
            create_venv_cmd = f"virtualenv -p python3 {self.venv_tmp_dir}"
            activate_cmd = ". " + os.path.join(venv_path, "bin", "activate")
            cmd_separator = ";"

        if install_cmd_list:
            install_cmd = cmd_separator.join(install_cmd_list)
        else:
            logger.error(const.SUPPORT_PACKAE[self.package_manager_name])
            logger.error('Cannot create virtualenv becuase it cannot find: '
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
            elif cmd_ret.stderr.decode('utf-8').rstrip().startswith('ERROR:'):
                ret = False
                err_msg = f"stderr msg({cmd_ret.stderr})"
        except Exception as e:
            ret = False
            err_msg = e
        finally:
            if ret:
                logger.info(f"It created the temporary virtualenv({venv_path}).")
            else:
                logger.error(f"Failed to create virtualenv: {err_msg}")

        return ret

    def start_pip_licenses(self):
        ret = True
        pip_licenses = 'pip-licenses'
        ptable = 'PTable'
        pip_licenses_default_options = ' --from=mixed --with-url --format=json --with-license-file'
        pip_licenses_system_option = ' --with-system -p '
        pip_license_dependency = [pip_licenses, ptable]
        tmp_pip_list = "tmp_list.txt"

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
        pip_list_command = f"pip freeze > {tmp_pip_list}"
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
        exists_ptable = False

        if os.path.isfile(tmp_pip_list):
            try:
                with open(tmp_pip_list, 'r', encoding='utf-8') as pip_list_file:
                    for pip_list in pip_list_file.readlines():
                        pip_list_name = pip_list.split('==')[0]
                        if pip_list_name == pip_licenses:
                            exists_pip_licenses = True
                        elif pip_list_name == ptable:
                            exists_ptable = True
                os.remove(tmp_pip_list)
            except Exception as e:
                logger.error(f"Failed to read freezed package list file: {e}")
                return False

        command_list = []
        command_list.append(activate_command)
        if not exists_pip_licenses:
            install_pip_command = f"pip install {pip_licenses}"
            command_list.append(install_pip_command)

        pip_licenses_command = f"{pip_licenses}{pip_licenses_default_options} > {self.tmp_file_name}"
        command_list.append(pip_licenses_command)

        if exists_ptable:
            pip_licenses_info_command = pip_licenses + pip_licenses_default_options + pip_licenses_system_option
            if exists_pip_licenses:
                pip_licenses_info_command += " ".join(pip_license_dependency)
            else:
                pip_licenses_info_command += ptable
            pip_licenses_info_command += f" > {self.tmp_pip_license_info_file_name}"
            command_list.append(pip_licenses_info_command)

        if not exists_pip_licenses:
            uninstall_pip_command = "pip uninstall -y "
            if exists_ptable:
                uninstall_pip_command += pip_licenses
            else:
                uninstall_pip_command += " ".join(pip_license_dependency)
            command_list.append(uninstall_pip_command)

        command_list.append(deactivate_command)
        command = command_separator.join(command_list)

        try:
            cmd_ret = subprocess.call(command, shell=True)
            if cmd_ret == 0:
                self.append_input_package_list_file(self.tmp_file_name)
                if exists_ptable:
                    self.append_input_package_list_file(self.tmp_pip_license_info_file_name)
            else:
                logger.error(f"Failed to run pip-licenses: {command}")
                ret = False
        except Exception as e:
            ret = False
            logger.error(f"Failed to install/uninstall pip-licenses: {e}")

        return ret

    def parse_oss_information(self, f_name):
        sheet_list = []
        comment = ''
        try:
            oss_init_name = ''
            with open(f_name, 'r', encoding='utf-8') as json_file:
                json_data = json.load(json_file)

            for d in json_data:
                oss_init_name = d['Name']
                oss_name = self.package_manager_name + ":" + oss_init_name
                license_name = check_UNKNOWN(d['License'])
                homepage = check_UNKNOWN(d['URL'])
                oss_version = d['Version']
                dn_loc = f"{self.dn_url}{oss_init_name}/{oss_version}"

                if license_name is not None:
                    license_name = license_name.replace(';', ',')

                license_file_dir = d['LicenseFile']
                license_name_with_license_scanner = check_and_run_license_scanner(self.platform,
                                                                                  self.license_scanner_bin,
                                                                                  license_file_dir)

                if license_name_with_license_scanner != "":
                    license_name = license_name_with_license_scanner

                if self.direct_dep_list:
                    if oss_init_name in self.direct_dep_list:
                        comment = 'direct'
                    else:
                        comment = 'transitive'

                sheet_list.append([', '.join(self.manifest_file_name),
                                   oss_name, oss_version,
                                   license_name, dn_loc, homepage, '', '', comment])

        except Exception as ex:
            logger.warning(f"Fail to parse oss information: {oss_init_name}({ex})")

        return sheet_list

    def parse_direct_dependencies(self):
        self.direct_dep = True
        requirements_f = 'requirements.txt'
        setup_f = 'setup.py'
        setup_key = 'setup'
        install_dep_key = 'install_requires'

        if requirements_f in self.manifest_file_name:
            with open(requirements_f, 'r') as fd:
                for req in requirements.parse(fd):
                    self.direct_dep_list.append(req.name)

        if setup_f in self.manifest_file_name:
            parse_setup = ast.parse(open(setup_f).read())
            for node in parse_setup.body:
                if not isinstance(node, ast.Expr):
                    continue
                if not isinstance(node.value, ast.Call):
                    continue
                if node.value.func.id != setup_key:
                    continue
                for keyword in node.value.keywords:
                    if keyword.arg == install_dep_key:
                        install_req_value = ast.literal_eval(keyword.value)
                        for req_key in install_req_value:
                            match_name = re.match(r'(?P<name>[\w\d]+)[\;\=\<\>]*|$', req_key)
                            self.direct_dep_list.append(match_name.group('name'))
                    if keyword.arg == 'name':
                        self.direct_dep_list.append(ast.literal_eval(keyword.value))


def check_UNKNOWN(text):
    if text == ['UNKNOWN'] or text == 'UNKNOWN':
        text = ""
    return text
