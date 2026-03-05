#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import subprocess
import shutil
from bs4 import BeautifulSoup as bs
from defusedxml.ElementTree import parse
import re
from pathlib import Path
import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import version_refine, get_url_to_purl, change_file_mode, get_download_location
from fosslight_dependency.dependency_item import DependencyItem, change_dependson_to_purl
from fosslight_util.get_pom_license import get_license_from_pom
from fosslight_util.oss_item import OssItem

logger = logging.getLogger(constant.LOGGER_NAME)


class Maven(PackageManager):
    package_manager_name = const.MAVEN

    dn_url = 'https://mvnrepository.com/artifact/'
    input_file_name = os.path.join('target', 'generated-resources', 'licenses.xml')
    is_run_plugin = False
    output_custom_dir = ''

    def __init__(self, input_dir, output_dir, output_custom_dir):
        super().__init__(self.package_manager_name, self.dn_url, input_dir, output_dir)
        self.is_run_plugin = False
        self.download_url_map = {}

        if output_custom_dir:
            self.output_custom_dir = output_custom_dir
            self.input_file_name = os.path.join(output_custom_dir, os.sep.join(self.input_file_name.split(os.sep)[1:]))

        self.append_input_package_list_file(self.input_file_name)

    def __del__(self):
        if self.is_run_plugin:
            self.clean_run_maven_plugin_output()

    def run_plugin(self):
        ret = True

        if not os.path.isfile(self.input_file_name):
            pom_backup = 'pom.xml_backup'

            ret = self.add_plugin_in_pom(pom_backup)
            if ret:
                ret_plugin = self.run_maven_plugin()
                if ret_plugin:
                    self.is_run_plugin = True

            if os.path.isfile(pom_backup):
                shutil.move(pom_backup, const.SUPPORT_PACKAE.get(self.package_manager_name))
        else:
            self.set_direct_dependencies(False)

        return ret

    def add_plugin_in_pom(self, pom_backup):
        ret = False
        xml = 'xml'
        f_content = None

        manifest_file = const.SUPPORT_PACKAE.get(self.package_manager_name)
        if os.path.isfile(manifest_file) != 1:
            logger.error(f"{manifest_file} is not existed in this directory.")
            return ret

        try:
            shutil.move(manifest_file, pom_backup)

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
                                            <configuration>\
                                                <excludedScopes>test</excludedScopes>\
                                            </configuration>\
                                        </plugin>'

            tmp_plugin = bs(license_maven_plugin, xml)

            license_maven_plugins = f"<plugins>{license_maven_plugin}</plugins>"
            tmp_plugins = bs(license_maven_plugins, xml)

            with open(pom_backup, 'r', encoding='utf8') as f:
                f_xml = f.read()
                f_content = bs(f_xml, xml)

            build = f_content.find('build')
            if build is not None:
                plugins = build.find('plugins')
                if plugins is not None:
                    plugins.append(tmp_plugin.plugin)
                    ret = True
                else:
                    build.append(tmp_plugins.plugins)
                    ret = True
            else:
                project = f_content.find('project')
                if project is not None:
                    build_with_plugins = f"<build>{license_maven_plugins}</build>"
                    tmp_build = bs(build_with_plugins, xml)
                    project.append(tmp_build.build)
                    ret = True
        except Exception as e:
            ret = False
            logger.warning(f"Failed to add plugin in pom : {e}")

        if ret:
            with open(manifest_file, "w", encoding='utf8') as f_w:
                f_w.write(f_content.prettify(formatter="minimal").encode().decode('utf-8'))

        return ret

    def clean_run_maven_plugin_output(self):
        directory_name = os.path.dirname(self.input_file_name)
        licenses_path = os.path.join(directory_name, 'licenses')
        if os.path.isdir(directory_name):
            if os.path.isdir(licenses_path):
                shutil.rmtree(licenses_path)
                os.remove(self.input_file_name)

            if len(os.listdir(directory_name)) == 0:
                shutil.rmtree(directory_name)

        top_path = self.input_file_name.split(os.sep)[0]
        if len(os.listdir(top_path)) == 0:
            shutil.rmtree(top_path)

    def run_maven_plugin(self):
        ret_plugin = True
        logger.info('Run maven license scanning plugin with temporary pom.xml')
        cmd_mvn, current_mode = self._get_mvn_cmd()
        cmd = f"{cmd_mvn} license:aggregate-download-licenses"

        ret = subprocess.call(cmd, shell=True)
        if ret != 0:
            logger.error(f"Failed to run maven plugin: {cmd}")
            ret_plugin = False

        if ret_plugin:
            cmd = f"{cmd_mvn} dependency:tree"
            try:
                ret_txt = subprocess.check_output(cmd, text=True, shell=True)
                if ret_txt is not None:
                    self.parse_dependency_tree(ret_txt)
                    self.set_direct_dependencies(True)
                else:
                    logger.error(f"Failed to run: {cmd}")
                    self.set_direct_dependencies(False)
            except Exception as e:
                logger.error(f"Failed to run '{cmd}': {e}")
                self.set_direct_dependencies(False)
        if current_mode:
            change_file_mode(cmd_mvn, current_mode)
        return ret_plugin

    def _get_mvn_cmd(self):
        current_mode = ''
        if os.path.isfile('mvnw') or os.path.isfile('mvnw.cmd'):
            if self.platform == const.WINDOWS:
                cmd_mvn = "mvnw.cmd"
            else:
                cmd_mvn = "./mvnw"
            current_mode = change_file_mode(cmd_mvn)
        else:
            cmd_mvn = "mvn"
        return cmd_mvn, current_mode

    def collect_source_download_urls(self, include_groups=None, include_artifacts=None):
        cmd_mvn, current_mode = self._get_mvn_cmd()
        try:
            flags = "-B -Dorg.slf4j.simpleLogger.log.org.apache.maven.cli.transfer.Slf4jMavenTransferListener=info"
            includes = []
            if include_groups:
                includes.append(f"-DincludeGroupIds={','.join(sorted(set(include_groups)))}")
            if include_artifacts:
                includes.append(f"-DincludeArtifactIds={','.join(sorted(set(include_artifacts)))}")
            cmd = f"{cmd_mvn} {flags} dependency:sources {' '.join(includes)}".strip()
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=self.input_dir)
            if proc.returncode == 0:
                self._parse_downloaded_from_lines_mvn(proc.stdout)
            else:
                logger.debug(f"dependency:sources failed (rc={proc.returncode}), trying dependency:resolve")
                cmd = f"{cmd_mvn} {flags} dependency:resolve {' '.join(includes)}".strip()
                proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=self.input_dir)
                if proc.returncode == 0:
                    self._parse_downloaded_from_lines_mvn(proc.stdout)
                else:
                    logger.debug(f"dependency:resolve failed (rc={proc.returncode})")
            if not self.download_url_map and (include_groups and include_artifacts):
                logger.debug("No download URLs found, attempting to reconstruct from local repository")
                self._collect_urls_from_local_repository(include_groups, include_artifacts)
        except Exception as e:
            logger.debug(f"Error occurred while collecting source download URLs: {e}")
        finally:
            if current_mode:
                change_file_mode(cmd_mvn, current_mode)

    def _collect_urls_from_local_repository(self, include_groups=None, include_artifacts=None):
        try:
            m2_repo = Path.home() / ".m2" / "repository"
            if not m2_repo.exists():
                return
            repo_map = self._parse_pom_repositories()
            if include_groups and include_artifacts:
                for group_id in include_groups:
                    group_path = group_id.replace('.', '/')
                    for artifact_id in include_artifacts:
                        artifact_path = m2_repo / group_path / artifact_id
                        if artifact_path.exists():
                            self._scan_artifact_versions(artifact_path, group_id, artifact_id, repo_map)
        except Exception as e:
            logger.debug(f"Failed to collect URLs from local repository: {e}")

    def _parse_pom_repositories(self):
        repo_map = {}
        try:
            pom_file = os.path.join(self.input_dir, 'pom.xml')
            if not os.path.exists(pom_file):
                return repo_map
            with open(pom_file, 'r', encoding='utf8') as f:
                soup = bs(f.read(), 'xml')
                repositories = soup.find_all('repository')
                for repo in repositories:
                    repo_id = repo.find('id')
                    repo_url = repo.find('url')
                    if repo_id and repo_url:
                        repo_map[repo_id.text.strip()] = repo_url.text.strip().rstrip('/')
        except Exception as e:
            logger.debug(f"Failed to parse pom repositories: {e}")
        return repo_map

    def _scan_artifact_versions(self, artifact_path, group_id, artifact_id, repo_map):
        try:
            for version_dir in artifact_path.iterdir():
                if not version_dir.is_dir():
                    continue
                version = version_dir.name
                remote_repos_file = version_dir / "_remote.repositories"

                if remote_repos_file.exists():
                    with open(remote_repos_file, 'r') as f:
                        for line in f:
                            if line.startswith('#') or '>' not in line:
                                continue
                            parts = line.strip().split('>')
                            if len(parts) != 2:
                                continue
                            filename = parts[0]
                            repo_id = parts[1].rstrip('=')

                            if '-sources.jar' in filename:
                                if repo_id in repo_map:
                                    repo_url = repo_map[repo_id]
                                elif repo_id == 'central':
                                    repo_url = 'https://repo.maven.apache.org/maven2'
                                else:
                                    continue
                                group_path = group_id.replace('.', '/')
                                url = f"{repo_url}/{group_path}/{artifact_id}/{version}/{filename}"
                                key = f"{group_id}:{artifact_id}:{version}"
                                self.download_url_map[key] = url
                                logger.debug(f"Reconstructed URL from local repo: {key} -> {url}")
                                break
        except Exception as e:
            logger.debug(f"Failed to scan artifact versions: {e}")

    def _parse_downloaded_from_lines_mvn(self, stdout_text: str):
        current_gav = None
        tld_roots = {'com', 'org', 'io', 'net', 'edu', 'gov', 'mil', 'co', 'de', 'fr', 'uk', 'kr', 'jp', 'cn'}

        for raw in stdout_text.splitlines():
            line = raw.strip()
            try:
                if 'Resolving ' in line:
                    m = re.search(r'Resolving\s+([^:]+):([^:]+):[^:]+:([^\s:]+)', line)
                    if m:
                        current_gav = (m.group(1), m.group(2), m.group(3))
                        continue
                if ('Downloading from' in line) or ('Downloaded from' in line):
                    m = re.search(r'(https?://\S+)', line)
                    if not m:
                        continue
                    url = m.group(1)

                    if not current_gav:
                        parts = url.split('/')
                        if len(parts) >= 6 and parts[0].startswith('http'):
                            filename = parts[-1]
                            version = parts[-2]
                            artifactid = parts[-3]

                            if filename.startswith(f"{artifactid}-{version}"):
                                artifact_idx = len(parts) - 3
                                group_start_idx = -1
                                for i in range(artifact_idx - 1, 2, -1):
                                    if parts[i] in tld_roots:
                                        group_start_idx = i
                                        break
                                if group_start_idx > 0:
                                    group_parts = parts[group_start_idx:artifact_idx]
                                    groupid = '.'.join(group_parts)
                                    current_gav = (groupid, artifactid, version)

                    if not current_gav:
                        continue
                    groupid, artifactid, version = current_gav
                    tail = url.split('/')[-1]

                    if not tail.startswith(f"{artifactid}-{version}"):
                        continue
                    key = f"{groupid}:{artifactid}:{version}"
                    prev = self.download_url_map.get(key)
                    if (prev is None) or (('-sources.' in url) and ('-sources.' not in (prev or ''))):
                        self.download_url_map[key] = url

                    current_gav = None
            except Exception as e:
                logger.debug(f"Failed to parse mvn line: {line} ({e})")

    def create_dep_stack(self, dep_line):
        dep_stack = []
        cur_flag = ''
        dep_level = -1
        dep_level_plus = False
        for line in dep_line.split('\n'):
            try:
                if not re.search(r'[.*INFO.*]', line):
                    continue
                if len(line) <= 7:
                    continue
                line = line[7:]

                prev_flag = cur_flag
                prev_dep_level = dep_level
                dep_level = line.count("|")

                re_result = re.findall(r'([\+|\\]\-)\s([^\:\s]+\:[^\:\s]+)\:(?:[^\:\s]+)\:([^\:\s]+)\:([^\:\s]+)', line)
                if re_result:
                    cur_flag = re_result[0][0]
                    if (prev_flag == '\\-') and (prev_dep_level == dep_level):
                        dep_level_plus = True
                    if dep_level_plus and (prev_flag == '\\-') and (prev_dep_level != dep_level):
                        dep_level_plus = False
                    if dep_level_plus:
                        dep_level += 1
                    if re_result[0][3] == 'test':
                        continue
                    dep_name = f'{re_result[0][1]}({re_result[0][2]})'
                    dep_stack = dep_stack[:dep_level] + [dep_name]
                    yield dep_stack[:dep_level], dep_name
                else:
                    cur_flag = ''
            except Exception as e:
                logger.warning(f"Failed to parse dependency tree: {e}")

    def parse_dependency_tree(self, f_name):
        try:
            for stack, name in self.create_dep_stack(f_name):
                if len(stack) == 0:
                    self.direct_dep_list.append(name)
                else:
                    if stack[-1] not in self.relation_tree:
                        self.relation_tree[stack[-1]] = []
                    self.relation_tree[stack[-1]].append(name)
        except Exception as e:
            logger.warning(f'Fail to parse maven dependency tree:{e}')

    def parse_oss_information(self, f_name):
        with open(f_name, 'r', encoding='utf8') as input_fp:
            tree = parse(input_fp)
        root = tree.getroot()
        dependencies = root.find("dependencies")
        purl_dict = {}

        if not getattr(self, 'download_url_map', None):
            self.download_url_map = {}
        if not self.download_url_map:
            groups, arts = set(), set()
            for d in dependencies.iter("dependency"):
                g = d.findtext("groupId") or ""
                a = d.findtext("artifactId") or ""
                if g:
                    groups.add(g)
                if a:
                    arts.add(a)
            try:
                self.collect_source_download_urls(include_groups=groups, include_artifacts=arts)
            except Exception as e:
                logger.debug(f"Skip collecting source URLs: {e}")

        for d in dependencies.iter("dependency"):
            dep_item = DependencyItem()
            oss_item = OssItem()
            groupid = d.findtext("groupId")
            artifactid = d.findtext("artifactId")
            version = d.findtext("version")
            oss_item.version = version_refine(version)

            oss_item.name = f"{groupid}:{artifactid}"
            oss_item.download_location = get_download_location(
                self.download_url_map, groupid, artifactid, version, self.dn_url
            )
            oss_item.homepage = f"{self.dn_url}{groupid}/{artifactid}"
            mvn_dn_url = f"{oss_item.homepage}/{version}"
            dep_item.purl = get_url_to_purl(mvn_dn_url, self.package_manager_name)
            purl_dict[f'{oss_item.name}({version})'] = dep_item.purl

            licenses = d.find("licenses")
            if len(licenses):
                license_names = []
                for key_license in licenses.iter("license"):
                    if key_license.findtext("name") is not None:
                        license_names.append(key_license.findtext("name").replace(",", ""))
                oss_item.license = ', '.join(license_names)
            if not oss_item.license:
                license_names = get_license_from_pom(groupid, artifactid, version)
                if license_names:
                    oss_item.license = license_names

            dep_key = f"{oss_item.name}({version})"

            if self.direct_dep:
                if len(self.direct_dep_list) > 0:
                    if dep_key in self.direct_dep_list:
                        oss_item.comment = 'direct'
                    else:
                        oss_item.comment = 'transitive'
                try:
                    if dep_key in self.relation_tree:
                        dep_item.depends_on_raw = self.relation_tree[dep_key]
                except Exception as e:
                    logger.error(f"Fail to find oss scope in dependency tree: {e}")

            dep_item.oss_items.append(oss_item)
            self.dep_items.append(dep_item)

        if self.direct_dep:
            self.dep_items = change_dependson_to_purl(purl_dict, self.dep_items)
        return
