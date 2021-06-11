#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2020 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

from __future__ import print_function
from io import open
import os
import sys
import argparse
import platform
import shutil
import subprocess
import json
import re
from xml.etree.ElementTree import parse
from bs4 import BeautifulSoup
import yaml
from lastversion import lastversion
from fosslight_util.set_log import init_log
from datetime import datetime
from fosslight_util.write_excel import write_excel_and_csv
from fosslight_dependency._version import __version__
from fosslight_dependency._help import print_help_msg


# Check the manifest file
manifest_array = [["pip", "requirements.txt"], ["npm", "package.json"], ["maven", "pom.xml"],
                  ["gradle", "build.gradle"], ["pub", "pubspec.yaml"], ["cocoapods", "Podfile.lock"],
                  ["android", "gradlew"]]

# binary url to check license text
license_scanner_url_linux = "third_party/nomos/nomossa"
license_scanner_url_macos = "third_party/askalono/askalono_macos"
license_scanner_url_windows = "third_party\\askalono\\askalono.exe"


def check_valid_manifest_file():
    global PACKAGE

    manifest_file_name = [i[1] for i in manifest_array]

    idx = 0
    found_idx = []
    for f in manifest_file_name:
        if os.path.isfile(f):
            found_idx.append(idx)
        idx += 1

    if len(found_idx) == 1:
        PACKAGE = manifest_array[int(found_idx[0])][0]
        logger.info("### Info Message ###")
        logger.info("Found the manifest file(" + manifest_array[int(found_idx[0])][1] + ")automatically.")
        logger.warn("Set PACKAGE =" + PACKAGE)
        ret = 0
    else:
        ret = 1

    return ret


def parse_option():
    global MANUAL_DETECT, PIP_ACTIVATE, PIP_DEACTIVATE, PACKAGE, OUTPUT_CUSTOM_DIR, CUR_PATH, OUTPUT_RESULT_DIR, APPNAME

    default_unspecified = "UNSPECIFIED"

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-h', '--help', action='store_true', required=False)
    parser.add_argument('-m', '--manager', nargs=1, type=str, default=default_unspecified, required=False)
    parser.add_argument('-a', '--activate', nargs=1, type=str, default=default_unspecified, required=False)
    parser.add_argument('-d', '--deactivate', nargs=1, type=str, default=default_unspecified, required=False)
    parser.add_argument('-c', '--customized', nargs=1, type=str, required=False)
    parser.add_argument('-p', '--path', nargs=1, type=str, required=False)
    parser.add_argument('-v', '--version', action='store_true', required=False)
    parser.add_argument('-o', '--output', nargs=1, type=str, required=False)
    parser.add_argument('-n', '--appname', nargs=1, type=str, required=False)

    args = parser.parse_args()

    # -h option
    if args.help:
        print_help_msg()

    # -v option
    if args.version:
        print(__version__)
        sys.exit(0)

    # -m option
    if args.manager == default_unspecified:
        MANUAL_DETECT = 0   # It will be detected the package manager automatically with manifest file.
    else:
        MANUAL_DETECT = 1
        PACKAGE = "".join(args.manager)

    # -a option
    if args.activate:
        PIP_ACTIVATE = "".join(args.activate)

    # -d option
    if args.deactivate:
        PIP_DEACTIVATE = "".join(args.deactivate)

    # -c option
    if args.customized:
        OUTPUT_CUSTOM_DIR = "".join(args.customized)
    else:
        OUTPUT_CUSTOM_DIR = ""

    # -o option
    if args.output:
        OUTPUT_RESULT_DIR = "".join(args.output)
        if os.path.isdir(OUTPUT_RESULT_DIR):
            OUTPUT_RESULT_DIR = os.path.abspath(OUTPUT_RESULT_DIR)
        else:
            try:
                os.mkdir(OUTPUT_RESULT_DIR)
            except:
                print("You entered wrong output path(" + OUTPUT_RESULT_DIR + ") to generate output file.")
                sys.exit(1)
            OUTPUT_RESULT_DIR = os.path.abspath(OUTPUT_RESULT_DIR)
    else:
        OUTPUT_RESULT_DIR = os.getcwd()

    # -p option
    if args.path:
        CUR_PATH = "".join(args.path)
        if os.path.isdir(CUR_PATH):
            os.chdir(CUR_PATH)
            CUR_PATH = os.getcwd()
        else:
            print("You entered wrong path(" + CUR_PATH + ") to run the script.")
            sys.exit(1)
    else:
        CUR_PATH = os.getcwd()
        os.chdir(CUR_PATH)

    if args.appname:
        APPNAME = "".join(args.appname)
    else:
        APPNAME = "app"


def configure_package():
    if MANUAL_DETECT == 0:
        ret = check_valid_manifest_file()
        if ret != 0:
            logger.error("### Error Message ###")
            logger.error("Please enter the package manager with -m option.")
            logger.error("You can see the '-m' option with help messages('-h')")
            sys.exit(1)


####################
# Common functions #
####################

def check_python_version():
    if int(sys.version[0]) < 3:
        python_version = 2
    else:
        python_version = 3
    logger.info("python_version = " + str(python_version))
    return python_version


def check_virtualenv_arg():
    global PIP_ACTIVATE, PIP_DEACTIVATE, venv_tmp_dir

    if PIP_ACTIVATE == "UNSPECIFIED":
        is_requirements_file = os.path.isfile("requirements.txt")

        if is_requirements_file != 1:
            logger.error("### Error Message ###")
            logger.error("Cannot find the virtualenv directory:" + PIP_ACTIVATE)
            logger.error("Also it cannot find 'requirements.txt' file and install pip package.")
            logger.error("Please check the '-a' option argument.")
            sys.exit(1)

        python_version = check_python_version()

        venv_path = os.path.join(CUR_PATH, venv_tmp_dir)

        if python_version == 2:
            create_venv_command = "virtualenv -p python " + venv_tmp_dir
        else:
            create_venv_command = "virtualenv -p python3 " + venv_tmp_dir

        if check_os() == "Windows":
            activate_command = ".\\" + os.path.join(venv_tmp_dir, "Scripts", "activate")
        else:
            activate_command = ". " + os.path.join(venv_path, "bin", "activate")

        PIP_ACTIVATE = activate_command

        install_command = "pip install -r requirements.txt"
        deactivate_command = "deactivate"
        PIP_DEACTIVATE = deactivate_command

        logger.info("You didn't enter the '-a' option.")
        logger.info("It makes virtualenv tmp dir(" + venv_path + ") to install pip package with requirements.txt.")

        if check_os() == "Windows":
            command_separator = "&"
        else:
            command_separator = ";"
        command_list = [create_venv_command, activate_command, install_command, deactivate_command]
        command = command_separator.join(command_list)
        command_ret = subprocess.call(command, shell=True)
        if command_ret != 0:
            logger.error("### Error Message ###")
            logger.error("This command(" + command + ") returns an error")
            logger.error("Please check if you installed virtualenv.")
            sys.exit(1)


def add_plugin_in_pom():
    global pom_backup

    is_append = False

    if os.path.isfile(manifest_array[2][1]) != 1:
        logger.error(manifest_array[2][1] + " is not existed in this directory.")
        sys.exit(1)

    shutil.move(manifest_array[2][1], pom_backup)

    license_maven_plugin = '<plugin>\
                                    <groupId>org.codehaus.mojo</groupId>\
                                    <artifactId>license-maven-plugin</artifactId>\
                                    <version>2.0.0</version>\
                                    <executions>\
                                        <execution>\
                                            <id>aggregate-download-licenses</id>\
                                            <goals>\
                                                <goal>aggregate-download-licenses</goal>\
                                            </goals>\
                                        </execution>\
                                    </executions>\
                                </plugin>'

    tmp_plugin = BeautifulSoup(license_maven_plugin, 'xml')

    license_maven_plugins = '<plugins>' + license_maven_plugin + '<plugins>'
    tmp_plugins = BeautifulSoup(license_maven_plugins, 'xml')

    with open(pom_backup, 'r', encoding='utf8') as f:
        f_xml = f.read()
        f_content = BeautifulSoup(f_xml, 'xml')

        build = f_content.find('build')
        if build is not None:
            plugins = build.find('plugins')
            if plugins is not None:
                plugins.append(tmp_plugin.plugin)
                is_append = True
            else:
                build.append(tmp_plugins.plugins)
                is_append = True

    if is_append:
        with open(manifest_array[2][1], "w", encoding='utf8') as f_w:
            f_w.write(f_content.prettify(formatter="minimal").encode().decode('utf-8'))

    return is_append


def clean_run_maven_plugin_output():
    global input_file_name

    if OUTPUT_CUSTOM_DIR != "":
        input_tmp = input_file_name.split('/')
        input_rest_tmp = ''
        for i in range(len(input_tmp)):
            if i > 0:
                input_rest_tmp = input_rest_tmp + '/' + input_tmp[i]
        input_file_name = str(OUTPUT_CUSTOM_DIR) + str(input_rest_tmp)

    directory_name = os.path.dirname(input_file_name)
    licenses_path = directory_name + '/licenses'
    if os.path.isdir(licenses_path) == 1:
        shutil.rmtree(licenses_path)
        os.remove(directory_name + '/licenses.xml')
        logger.info('remove temporary directory: ' + licenses_path)

    if len(os.listdir(directory_name)) == 0:
        shutil.rmtree(directory_name)

    shutil.move(pom_backup, manifest_array[2][1])


def run_maven_plugin():
    logger.info('run maven license scanning plugin with temporary pom.xml')
    command = "mvn license:aggregate-download-licenses"

    ret = subprocess.call(command, shell=True)

    if ret != 0:
        logger.error("### Error Message ###")
        logger.error("This command(" + command + ") returns an error.")

        clean_run_maven_plugin_output()
        sys.exit(1)


def open_input_file():
    global input_file_name

    if OUTPUT_CUSTOM_DIR != "":
        input_tmp = input_file_name.split('/')
        input_rest_tmp = ''
        for i in range(len(input_tmp)):
            if i > 0:
                input_rest_tmp = input_rest_tmp + '/' + input_tmp[i]
        input_file_name = str(OUTPUT_CUSTOM_DIR) + str(input_rest_tmp)

    if os.path.isfile(input_file_name) != 1:
        logger.error("### Error Message ###")
        logger.error(input_file_name + " doesn't exist in this directory.")

        if PACKAGE == "maven":
            global is_maven_first_try

            if is_maven_first_try:
                is_append = add_plugin_in_pom()
                is_maven_first_try = False

                if is_append:
                    run_maven_plugin()
                    return open_input_file()
                else:
                    clean_run_maven_plugin_output()

        logger.error("Please check the below thing first.")
        logger.error("  1.Did you run the license-maven-plugin?")
        logger.error("  2.Or if your project has the customized build output directory, \
                    then use '-c' option with your customized build output directory name")
        logger.error("    $ fosslight_dependency -c output")
        sys.exit(1)

    input_fp = open(input_file_name, 'r', encoding='utf8')

    return input_fp


def close_input_file(input_fp):
    input_fp.close()


def make_custom_json(tmp_custom_json):
    with open(tmp_custom_json, 'w', encoding='utf8') as custom:
        custom.write(
            "{\n\t\"name\": \"\",\n\t\"version\": \"\",\n\t\"licenses\": \"\",\n\t\"repository\": \
            \"\",\n\t\"url\": \"\",\n\t\"copyright\": \"\",\n\t\"licenseText\": \"\"\n}\n".encode().decode("utf-8"))


def start_license_checker():
    tmp_custom_json = "custom.json"
    tmp_file_name = "tmp_npm_license_output.json"
    flag_tmp_node_modules = False

    if os.path.isfile(tmp_custom_json) == 1:
        os.remove(tmp_custom_json)
    if os.path.isfile(tmp_file_name) == 1:
        os.remove(tmp_file_name)

    test_command = "license-checker > test.tmp"
    ret = os.system(test_command)
    os.remove("test.tmp")
    if ret != 0:
        logger.error("### Error Message ###")
        logger.error("Running license-checker returns error. Please check if the license-checker is installed.")
        logger.error(">>Command for installing license-checker (Root permission is required to run this command.)")
        logger.error("  sudo npm install -g license-checker")
        sys.exit(1)

    if os.path.isdir("node_modules") != 1:
        logger.info("node_modules directory is not existed.it executes 'npm install'.")
        flag_tmp_node_modules = True
        command = 'npm install'
        command_ret = subprocess.call(command, shell=True)
        if command_ret != 0:
            logger.error("### Error Message ###")
            logger.error("This command(" + command + ") returns an error")
            sys.exit(1)

    # customized json file for obtaining specific items with license-checker
    make_custom_json(tmp_custom_json)

    # license-checker option
    # --production : not prints devDependencies
    # --json : prints output file with json format
    # --out : output file name with path
    # --customPath : add the specified items to the usual ones
    command = 'license-checker --production --json --out ' + tmp_file_name + ' --customPath ' + tmp_custom_json
    command_ret = os.system(command)
    os.remove(tmp_custom_json)
    if flag_tmp_node_modules:
        shutil.rmtree('node_modules')

    return tmp_file_name


def start_pip_licenses():
    global PIP_ACTIVATE

    tmp_file_name = "tmp_pip_license_output.json"

    if PIP_ACTIVATE.startswith("source "):
        tmp_activate = PIP_ACTIVATE[7:]
        PIP_ACTIVATE = ". " + tmp_activate
    elif PIP_ACTIVATE.startswith("conda "):
        if check_os() == "Linux":
            tmp_activate = "eval \"$(conda shell.bash hook)\""
            PIP_ACTIVATE = tmp_activate + PIP_ACTIVATE

    if check_os() == 'Windows':
        command_separator = "&"
    else:
        command_separator = ";"
    activate_command = PIP_ACTIVATE
    install_pip_command = "pip install pip-licenses"
    pip_licenses_command = "pip-licenses --from=mixed --with-url --format=json --with-license-file > " + tmp_file_name
    uninstall_pip_command = "pip uninstall -y pip-licenses PTable"
    deactivate_command = PIP_DEACTIVATE

    command_list = [activate_command, install_pip_command, pip_licenses_command, uninstall_pip_command,
                    deactivate_command]
    command = command_separator.join(command_list)

    ret = subprocess.call(command, shell=True)

    if ret == 0:
        return tmp_file_name
    else:
        logger.error("### Error Message ###")
        logger.error("This command(" + command + ") returns an error.")
        sys.exit(1)


def check_os():
    # return value : Linux, Windows, Darwin(Mac OS)
    return platform.system()


def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def check_license_scanner(os_name):
    global license_scanner_url, license_scanner_bin

    if os_name == 'Linux':
        license_scanner_url = license_scanner_url_linux
    elif os_name == 'Darwin':
        license_scanner_url = license_scanner_url_macos
    elif os_name == 'Windows':
        license_scanner_url = license_scanner_url_windows
    else:
        logger.info("Not supported OS to analyze license text with binary.")
        return

    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(__file__)

    data_path = os.path.join(base_path, license_scanner_url)
    license_scanner_bin = data_path


def check_and_run_license_scanner(file_dir, os_name):
    global license_scanner_bin

    try:
        tmp_output_file_name = "tmp_license_scanner_output.txt"

        if file_dir == "UNKNOWN":
            license_name = ""
        else:
            if os_name == 'Linux':
                run_license_scanner = license_scanner_bin + " " + file_dir + " > " + tmp_output_file_name
            elif os_name == 'Darwin':
                run_license_scanner = license_scanner_bin + " identify " + file_dir + " > " + tmp_output_file_name
            elif os_name == 'Windows':
                run_license_scanner = license_scanner_bin + " identify " + file_dir + " > " + tmp_output_file_name
            else:
                run_license_scanner = ''

            if run_license_scanner is None:
                license_name = ""
                return license_name
            else:
                ret = os.system(run_license_scanner)
                if ret != 0:
                    return ""

            fp = open(tmp_output_file_name, "r", encoding='utf8')
            license_output = fp.read()
            fp.close()
            os.remove(tmp_output_file_name)

            if os_name == 'Linux':
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
        logger.info("There are some errors for the license scanner binary")
        logger.info("Error:" + str(ex))
        license_name = ""

    return license_name


def check_multi_license(license_name):
    if isinstance(license_name, list):
        multi_license = 1
    else:
        multi_license = 0

    return multi_license


def parse_oss_name_version_in_filename(name):
    filename = name.rstrip('.jar')
    split_name = filename.rpartition('-')

    oss_name = split_name[0]
    oss_version = split_name[2]

    return oss_name, oss_version


def parse_oss_name_version_in_artifactid(name):
    artifact_comp = name.split(':')

    group_id = artifact_comp[0]
    artifact_id = artifact_comp[1]
    oss_version = artifact_comp[2]

    return group_id, artifact_id, oss_version


def version_refine(oss_version):
    version_cmp = oss_version.upper()

    if version_cmp.find(".RELEASE") != -1:
        oss_version = version_cmp.rstrip(".RELEASE")
    elif version_cmp.find(".FINAL") != -1:
        oss_version = version_cmp.rstrip(".FINAL")

    return oss_version


#################################################################################################################################
# Functions for parsing generated file from OSS that could scan license information about dependencies of each package manager.  #
#################################################################################################################################

def check_UNKNOWN(text):
    if text == ['UNKNOWN'] or text == 'UNKNOWN':
        text = ""

    return text


def parse_and_generate_output_pip(tmp_file_name):
    global license_scanner_bin

    os_name = check_os()
    check_license_scanner(os_name)

    sheet_list = {}

    try:
        with open(tmp_file_name, 'r', encoding='utf-8') as json_file:
            json_data = json.load(json_file)

        sheet_list["SRC"] = []

        for d in json_data:
            oss_init_name = d['Name']
            oss_name = "pypi:" + oss_init_name
            license_name = check_UNKNOWN(d['License'])
            homepage = check_UNKNOWN(d['URL'])
            oss_version = d['Version']
            dn_loc = dn_url + oss_init_name + "/" + oss_version

            license_file_dir = d['LicenseFile']
            license_name_with_license_scanner = check_and_run_license_scanner(license_file_dir, os_name)

            if license_name_with_license_scanner != "":
                license_name = license_name_with_license_scanner

            sheet_list["SRC"].append(['pip', oss_name, oss_version, license_name, dn_loc, homepage, '', '', ''])

    except Exception as ex:
        logger.error("Error:" + str(ex))

    if os.path.isdir(venv_tmp_dir):
        shutil.rmtree(venv_tmp_dir)
        logger.info("remove tmp directory: " + venv_tmp_dir)

    return sheet_list


def parse_and_generate_output_npm(tmp_file_name):
    with open(tmp_file_name, 'r', encoding='utf8') as json_file:
        json_data = json.load(json_file)

        sheet_list = {}
        sheet_list["SRC"] = []

        keys = [key for key in json_data]

        for i in range(0, len(keys)):
            d = json_data.get(keys[i - 1])
            oss_init_name = d['name']
            oss_name = "npm:" + oss_init_name

            if d['licenses']:
                license_name = d['licenses']
            else:
                license_name = ''

            oss_version = d['version']

            if d['repository']:
                dn_loc = d['repository']
            else:
                dn_loc = dn_url + oss_init_name + '/v/' + oss_version

            homepage = dn_url + oss_init_name

            multi_license = check_multi_license(license_name)

            if multi_license == 1:
                for l_idx in range(0, len(license_name)):
                    license_name = license_name[l_idx].replace(",", "")

                    sheet_list["SRC"].append(['package.json', oss_name, oss_version, license_name, dn_loc, homepage, '', '', ''])
            else:
                license_name = license_name.replace(",", "")

                sheet_list["SRC"].append(['package.json', oss_name, oss_version, license_name, dn_loc, homepage, '', '', ''])

        return sheet_list


def parse_and_generate_output_maven(input_fp):
    tree = parse(input_fp)

    root = tree.getroot()
    dependencies = root.find("dependencies")

    sheet_list = {}
    sheet_list["SRC"] = []

    for d in dependencies.iter("dependency"):
        groupid = d.findtext("groupId")
        artifactid = d.findtext("artifactId")
        version = d.findtext("version")
        oss_version = version_refine(version)

        oss_name = groupid + ":" + artifactid
        dn_loc = dn_url + groupid + "/" + artifactid + "/" + version
        homepage = dn_url + groupid + "/" + artifactid

        licenses = d.find("licenses")
        if len(licenses):
            license_names = []
            for key_license in licenses.iter("license"):
                license_names.append(key_license.findtext("name").replace(",", ""))
            license_name = ', '.join(license_names)
        else:
            # Case that doesn't include License tag value.
            license_name = ''

        sheet_list["SRC"].append(['pom.xml', oss_name, oss_version, license_name, dn_loc, homepage, '', '', ''])

    return sheet_list


def parse_and_generate_output_gradle(input_fp):
    json_data = json.load(input_fp)

    sheet_list = {}
    sheet_list["SRC"] = []

    for d in json_data['dependencies']:

        used_filename = "false"
        group_id = ""
        artifact_id = ""

        name = d['name']
        filename = d['file']

        if name != filename:
            group_id, artifact_id, oss_ini_version = parse_oss_name_version_in_artifactid(name)
            oss_name = group_id + ":" + artifact_id
        else:
            oss_name, oss_ini_version = parse_oss_name_version_in_filename(filename)
            used_filename = "true"

        oss_version = version_refine(oss_ini_version)

        license_names = []
        for licenses in d['licenses']:
            license_names.append(licenses['name'].replace(",", ""))
        license_name = ', '.join(license_names)

        if used_filename == "true" or group_id == "":
            dn_loc = 'Unknown'
            homepage = ''

        else:
            dn_loc = dn_url + group_id + "/" + artifact_id + "/" + oss_ini_version
            homepage = dn_url + group_id + "/" + artifact_id

        sheet_list["SRC"].append(['build.gradle', oss_name, oss_version, license_name, dn_loc, homepage, '', '', ''])

    return sheet_list


def preprocess_pub_result(input_file):
    matched_json = re.findall(r'final ossLicenses = <String, dynamic>({.*});', input_file.read())

    if matched_json[0] is not None:
        return matched_json[0]
    else:
        logger.error("### Error Message ###")
        logger.error("Cannot parse the result json from pub input file.")
        exit(1)


def parse_and_generate_output_pub(tmp_file_name):
    global license_scanner_bin, tmp_license_txt_file_name

    json_txt = preprocess_pub_result(tmp_file_name)
    json_data = json.loads(json_txt)

    sheet_list = {}
    sheet_list["SRC"] = []

    os_name = check_os()
    check_license_scanner(os_name)

    for key in json_data:
        oss_origin_name = json_data[key]['name']
        oss_name = "pub:" + oss_origin_name
        oss_version = json_data[key]['version']
        homepage = json_data[key]['homepage']
        # dn_loc = homepage
        dn_loc = dn_url + oss_origin_name + "/versions/" + oss_version
        license_txt = json_data[key]['license']

        tmp_license_txt = open(tmp_license_txt_file_name, 'w', encoding='utf-8')
        tmp_license_txt.write(license_txt)
        # tmp_license_txt.write(license_txt.encode().decode('utf-8'))
        tmp_license_txt.close()

        license_name_with_license_scanner = check_and_run_license_scanner(tmp_license_txt_file_name, os_name)

        if license_name_with_license_scanner != "":
            license_name = license_name_with_license_scanner
        else:
            license_name = ''

        sheet_list["SRC"].append(['pubspec.yaml', oss_name, oss_version, license_name, dn_loc, homepage, '', '', ''])

    os.remove(tmp_license_txt_file_name)

    return sheet_list


def compile_pods_item(pods_item, spec_repo_list, pod_in_sepc_list, pod_not_in_spec_list):
    pods_item_re = re.findall(r'(\S*)\s{1}\((.*)\)', pods_item)

    oss_name = pods_item_re[0][0]
    oss_version = pods_item_re[0][1]

    oss_info = []
    oss_info.append(oss_name)
    oss_info.append(oss_version)

    if oss_name in spec_repo_list:
        pod_in_sepc_list.append(oss_info)
        spec_repo_list.remove(oss_name)
    else:
        pod_not_in_spec_list.append(oss_info)

    return pod_in_sepc_list, spec_repo_list, pod_not_in_spec_list


def parse_and_generate_output_cocoapods(input_fp):
    global source_type

    pod_in_sepc_list = []
    pod_not_in_spec_list = []
    spec_repo_list = []
    podfile_yaml = yaml.load(input_fp, Loader=yaml.FullLoader)

    for spec_item_key in podfile_yaml['SPEC REPOS']:
        for spec_item in podfile_yaml['SPEC REPOS'][spec_item_key]:
            spec_repo_list.append(spec_item)

    for pods_list in podfile_yaml['PODS']:
        if not isinstance(pods_list, str):
            for pods_list_key, pods_list_item in pods_list.items():
                pod_in_sepc_list, spec_repo_list, pod_not_in_spec_list = \
                    compile_pods_item(pods_list_key, spec_repo_list, pod_in_sepc_list, pod_not_in_spec_list)
        else:
            pod_in_sepc_list, spec_repo_list, pod_not_in_spec_list = \
                compile_pods_item(pods_list, spec_repo_list, pod_in_sepc_list, pod_not_in_spec_list)

    if len(spec_repo_list) != 0:
        for spec_in_item in spec_repo_list:
            spec_oss_name_adding_core = spec_in_item + "/Core"
            for pod_not_item in pod_not_in_spec_list:
                if spec_oss_name_adding_core == pod_not_item[0]:
                    pod_in_sepc_list.append([spec_in_item, pod_not_item[1]])

    sheet_list = {}
    sheet_list["SRC"] = []

    for pod_oss in pod_in_sepc_list:

        search_oss_name = ""
        for alphabet_oss in pod_oss[0]:
            if not alphabet_oss.isalnum():
                search_oss_name += "\\\\" + alphabet_oss
            else:
                search_oss_name += alphabet_oss

        command = 'pod spec which --regex ' + '^' + search_oss_name + '$'
        spec_which = os.popen(command).readline()
        if spec_which.startswith('[!]'):
            logger.error("### Error Message ###")
            logger.error("This command(" + command + ") returns an error")
            sys.exit(1)

        file_path = spec_which.rstrip().split(os.path.sep)
        if file_path[0] == '':
            file_path_without_version = os.path.join(os.sep, *file_path[:-2])
        else:
            file_path_without_version = os.path.join(*file_path[:-2])
        spec_file_path = os.path.join(file_path_without_version, pod_oss[1], file_path[-1])

        with open(spec_file_path, 'r', encoding='utf8') as json_file:
            json_data = json.load(json_file)

            oss_origin_name = json_data['name']
            oss_name = "cocoapods:" + oss_origin_name
            oss_version = json_data['version']
            homepage = dn_url + 'pods/' + oss_origin_name

            if not isinstance(json_data['license'], str):
                if 'type' in json_data['license']:
                    license_name = json_data['license']['type']
            else:
                license_name = json_data['license']

            license_name = license_name.replace(",", "")

            source_keys = [key for key in json_data['source']]
            for src_type_i in source_type:
                if src_type_i in source_keys:
                    dn_loc = json_data['source'][src_type_i]
                    if dn_loc.endswith('.git'):
                        dn_loc = dn_loc[:-4]

            sheet_list["SRC"].append(['Podfile.lock', oss_name, oss_version, license_name, dn_loc, homepage, '', '', ''])

    return sheet_list


def parse_and_generate_output_android(input_fp):
    sheet_list = {}
    sheet_list["SRC"] = []

    for i, line in enumerate(input_fp.readlines()):
        split_str = line.strip().split("\t")
        if i < 2:
            continue

        if len(split_str) == 9:
            idx, manifest_file, oss_name, oss_version, license_name, dn_loc, homepage, NA, NA = split_str
        elif len(split_str) == 7:
            idx, manifest_file, oss_name, oss_version, license_name, dn_loc, homepage = split_str
        else:
            continue
        sheet_list["SRC"].append([manifest_file, oss_name, oss_version, license_name, dn_loc, homepage, '', '', ''])

    return sheet_list


###########################################
# Main functions for each package manager  #
###########################################
def main_pip():
    # It needs the virtualenv path that pip packages are installed.
    check_virtualenv_arg()

    # Run the command 'pip-licenses with option'.
    tmp_file_name = start_pip_licenses()

    # Make output file for OSS report using temporary output file for pip-licenses.
    sheet_list = parse_and_generate_output_pip(tmp_file_name)

    # Remove temporary output file.
    if os.path.isfile(tmp_file_name):
        os.remove(tmp_file_name)

    return sheet_list


def main_npm():
    # Install the license-checker (npm package) with global option.
    # os.system("npm install -g license-checker")

    # Run the command 'license-checker' with option'.
    tmp_file_name = start_license_checker()

    # Make output file for OSS report using temporary output file for license-checker.
    sheet_list = parse_and_generate_output_npm(tmp_file_name)

    # Remove temporary output file.
    os.remove(tmp_file_name)

    return sheet_list


def main_maven():
    # Before running this script, first you should add the maven-license-plugin in pom.xml and run it.

    # open license.xml
    input_fp = open_input_file()

    # Make output file for OSS report using temporary output file for maven-license-plugin.
    sheet_list = parse_and_generate_output_maven(input_fp)

    # close licenses.xml
    close_input_file(input_fp)

    if not is_maven_first_try:
        clean_run_maven_plugin_output()

    return sheet_list


def main_gradle():
    # Before running this script, first you should add the com.github.hierynomus.license in build.gradle and run it.

    # open dependency-license.json
    input_fp = open_input_file()

    # Make output file for OSS report using temporary output file for License Gradle Plugin.
    sheet_list = parse_and_generate_output_gradle(input_fp)

    # close dependency-license.json
    close_input_file(input_fp)

    return sheet_list


def main_pub():
    input_fp = open_input_file()

    sheet_list = parse_and_generate_output_pub(input_fp)

    close_input_file(input_fp)

    return sheet_list


def main_cocoapods():

    # open Podfile.lock
    input_fp = open_input_file()

    sheet_list = parse_and_generate_output_cocoapods(input_fp)

    close_input_file(input_fp)

    return sheet_list


def main_android():

    input_fp = open_input_file()

    sheet_list = parse_and_generate_output_android(input_fp)

    close_input_file(input_fp)

    return sheet_list


def main():

    global PACKAGE, output_file_name, input_file_name, CUR_PATH, OUTPUT_RESULT_DIR, \
        MANUAL_DETECT, OUTPUT_CUSTOM_DIR, dn_url, PIP_ACTIVATE, PIP_DEACTIVATE, APPNAME
    global license_scanner_url, license_scanner_bin, venv_tmp_dir, pom_backup, \
        is_maven_first_try, tmp_license_txt_file_name, source_type, logger

    start_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    parse_option()
    logger = init_log(os.path.join(OUTPUT_RESULT_DIR, "fosslight_dependency_log_" + start_time + ".txt"), True, 20, 10)

    # Check the latest version
    latest_version = lastversion.has_update(repo="fosslight_dependency", at='pip', current_version=__version__)
    if latest_version:
        logger.info('### Version Info ###')
        logger.info('Newer version is available:{}'.format(str(latest_version)))
        logger.info('You can update it with command (\'pip install fosslight_dependency --upgrade\')')

    # Configure global variables according to package manager.
    try:
        configure_package()
    except:
        logger.error("Error : Failed to configure package.")
        sys.exit(1)

    if PACKAGE == "pip":
        dn_url = "https://pypi.org/project/"
        output_file_name = "pip_dependency_output"
        venv_tmp_dir = "venv_osc_dep_tmp"

    elif PACKAGE == "npm":
        dn_url = "https://www.npmjs.com/package/"
        output_file_name = "npm_dependency_output"

    elif PACKAGE == "maven":
        dn_url = "https://mvnrepository.com/artifact/"
        input_file_name = "target/generated-resources/licenses.xml"
        output_file_name = "maven_dependency_output"
        pom_backup = "pom.xml_backup"
        is_maven_first_try = True

    elif PACKAGE == "gradle":
        dn_url = "https://mvnrepository.com/artifact/"
        input_file_name = "build/reports/license/dependency-license.json"
        output_file_name = "gradle_dependency_output"

    elif PACKAGE == "pub":
        dn_url = "https://pub.dev/packages/"
        input_file_name = "lib/oss_licenses.dart"
        output_file_name = "pub_dependency_output"
        tmp_license_txt_file_name = "tmp_license.txt"

    elif PACKAGE == "cocoapods":
        dn_url = "https://cocoapods.org/"
        input_file_name = "Podfile.lock"
        output_file_name = "cocoapods_dependency_output"
        source_type = ['git', 'http', 'svn', 'hg']

    elif PACKAGE == "android":
        input_file_name = os.path.join(APPNAME, "android_dependency_output.txt")
        output_file_name = "android_dependency_output"

    else:
        logger.error("### Error Message ###")
        logger.error("You enter the wrong first argument.")
        logger.error("Please enter the supported package manager. (Check the help message with (-h) option.)")
        sys.exit(1)

    if PACKAGE == "pip":
        sheet_list = main_pip()
    elif PACKAGE == "npm":
        sheet_list = main_npm()
    elif PACKAGE == "maven":
        sheet_list = main_maven()
    elif PACKAGE == "gradle":
        sheet_list = main_gradle()
    elif PACKAGE == "pub":
        sheet_list = main_pub()
    elif PACKAGE == "cocoapods":
        sheet_list = main_cocoapods()
    elif PACKAGE == "android":
        sheet_list = main_android()
    else:
        logger.error("### Error Message ###")
        logger.error("Please enter the supported package manager. (Check the help message with (-h) option.)")
        sys.exit(1)

    if sheet_list is not None:
        success, msg = write_excel_and_csv(os.path.join(OUTPUT_RESULT_DIR, output_file_name), sheet_list)
        if success:
            logger.info("Generated {0}.xlsx and {0}.csv into {1}!".format(output_file_name, OUTPUT_RESULT_DIR))
        else:
            logger.error("Fail to generate result file. msg:()", msg)
    else:
        logger.error("Fail to analyze dependency.")

    logger.info("### FINISH!! ###")

    sys.exit(0)


if __name__ == '__main__':
    main()
