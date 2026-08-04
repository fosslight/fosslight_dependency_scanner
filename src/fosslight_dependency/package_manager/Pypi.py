#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import io
import logging
import subprocess
import json
import shutil
import copy
import re
import sys
import urllib.request
import urllib.error
import zipfile

try:
    import tomli as tomllib
except ModuleNotFoundError:
    tomllib = None

from packaging.requirements import Requirement, InvalidRequirement
from packaging.markers import Marker

import fosslight_util.constant as constant
import fosslight_dependency.constant as const
from fosslight_dependency._package_manager import PackageManager
from fosslight_dependency._package_manager import get_url_to_purl, check_license_name
from fosslight_dependency.dependency_item import DependencyItem, change_dependson_to_purl
from fosslight_util.oss_item import OssItem

logger = logging.getLogger(constant.LOGGER_NAME)


class Pypi(PackageManager):
    package_manager_name = const.PYPI

    dn_url = 'https://pypi.org/project/'
    venv_tmp_dir = 'venv_osc_dep_tmp'
    tmp_file_name = "tmp_pip_license_output.json"
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

        shutil.rmtree(self.venv_tmp_dir, ignore_errors=True)

        if os.path.isfile(self.tmp_deptree_file):
            os.remove(self.tmp_deptree_file)

    def set_pip_activate_cmd(self, pip_activate_cmd):
        self.pip_activate_cmd = pip_activate_cmd

    def set_pip_deactivate_cmd(self, pip_deactivate_cmd):
        self.pip_deactivate_cmd = pip_deactivate_cmd

    def get_virtualenv_site_packages(self):
        site_packages = ''
        try:
            venv_path = os.path.join(self.input_dir, self.venv_tmp_dir)
            if os.path.exists(venv_path):
                site_packages = os.path.join(
                    venv_path, 'lib',
                    f"python{sys.version_info.major}.{sys.version_info.minor}",
                    'site-packages'
                )
                if os.path.exists(site_packages):
                    return site_packages

            if self.pip_activate_cmd:
                activate_cmd = self.pip_activate_cmd
                if activate_cmd.startswith('. '):
                    activate_cmd = activate_cmd[2:]
                elif activate_cmd.startswith('source '):
                    activate_cmd = activate_cmd[7:]

                if 'bin/activate' in activate_cmd or 'Scripts/activate' in activate_cmd:
                    venv_path = activate_cmd.replace('/bin/activate', '')
                    venv_path = venv_path.replace('\\Scripts\\activate.bat', '')
                    venv_path = venv_path.replace('\\Scripts\\activate', '')

                    if not os.path.isabs(venv_path):
                        venv_path = os.path.join(self.input_dir, venv_path)

                    if os.path.exists(venv_path):
                        for lib_dir in ['lib', 'Lib']:
                            site_packages = os.path.join(
                                venv_path, lib_dir,
                                f"python{sys.version_info.major}.{sys.version_info.minor}",
                                'site-packages'
                            )
                            if os.path.exists(site_packages):
                                return site_packages
                        site_packages = os.path.join(venv_path, 'Lib', 'site-packages')
                        if os.path.exists(site_packages):
                            return site_packages

                if 'conda' in activate_cmd:
                    site_packages = ''
        except Exception as e:
            logger.debug(f"Failed to get virtualenv site-packages: {e}")
            site_packages = ''
        return site_packages

    def get_license_from_file(self, package_name, version, license_files_metadata=None):
        license_names = []
        try:
            if not license_files_metadata:
                return []
            normalized_name = re.sub(r"[-_.]+", "_", package_name)
            dist_info_name = f"{normalized_name}-{version}.dist-info"

            site_packages = self.get_virtualenv_site_packages()
            if not site_packages:
                logger.debug("Could not find site-packages directory")
                return []

            dist_info_path = os.path.join(site_packages, dist_info_name)
            if not os.path.exists(dist_info_path):
                return []

            metadata_path = os.path.join(dist_info_path, 'METADATA')
            if os.path.isfile(metadata_path):
                with open(metadata_path, 'r', encoding='utf-8', errors='ignore') as metadata_file:
                    metadata_text = metadata_file.read()
                metadata_license = self._extract_license_from_metadata(metadata_text)
                if metadata_license and metadata_license not in license_names:
                    license_names.append(metadata_license)

            for license_file in license_files_metadata:
                license_file_path = os.path.join(dist_info_path, license_file)
                if os.path.isfile(license_file_path):
                    license_name = check_license_name(license_file_path, is_filepath=True)
                    if license_name and license_name not in license_names:
                        license_names.append(license_name)
                else:
                    if '/' not in license_file:
                        for root, _, files in os.walk(dist_info_path):
                            if license_file in files:
                                found_path = os.path.join(root, license_file)
                                license_name = check_license_name(found_path, is_filepath=True)
                                if license_name and license_name not in license_names:
                                    license_names.append(license_name)
        except Exception as e:
            logger.debug(f"Failed to read license file for {package_name}: {e}")
        return license_names

    def _extract_license_from_metadata(self, metadata_text):
        if not metadata_text:
            return ''

        for line in metadata_text.splitlines():
            if not line.startswith('License:'):
                continue
            license_value = line.split(':', 1)[1].strip()
            if not license_value:
                continue
            return check_UNKNOWN(check_license_name(license_value)) or license_value
        return ''

    def _normalize_package_name(self, package_name):
        return re.sub(r"[-_.]+", "-", package_name).strip().lower()

    def _get_pyproject_root_packages(self):
        """Extract direct dependency names from pyproject.toml."""
        root_packages = []
        pyproject_path = os.path.join(self.input_dir, 'pyproject.toml')
        if not os.path.isfile(pyproject_path):
            return root_packages

        try:
            with open(pyproject_path, 'rb') as fh:
                pyproject_data = tomllib.load(fh)
        except Exception as e:
            logger.warning(f'Failed to parse pyproject.toml: {e}')
            return root_packages

        # PEP 621 [project].dependencies (list of PEP 508 requirement strings)
        project_data = pyproject_data.get('project', {})
        dependencies = project_data.get('dependencies', [])
        for dependency in dependencies:
            if not isinstance(dependency, str):
                continue
            try:
                req = Requirement(dependency)
            except InvalidRequirement:
                # Fall back to the legacy regex extraction for non-PEP 508 entries.
                match = re.match(r'^\s*([A-Za-z0-9_.-]+)', dependency)
                if match:
                    root_packages.append(self._normalize_package_name(match.group(1)))
                continue
            # Evaluate environment markers against the current platform.
            if req.marker is not None and not req.marker.evaluate():
                continue
            root_packages.append(self._normalize_package_name(req.name))

        # Poetry fallback: [tool.poetry].dependencies is a mapping (name -> spec)
        if not root_packages:
            poetry_dependencies = pyproject_data.get('tool', {}).get('poetry', {}).get('dependencies', {})
            if isinstance(poetry_dependencies, dict):
                for dependency_name, dependency_spec in poetry_dependencies.items():
                    if dependency_name in {'python', 'build-system'}:
                        continue
                    root_packages.append(self._normalize_package_name(dependency_name))

        return root_packages

    def _get_uv_lock_package_wheels(self, package_entry):
        """Normalize wheel entries from a uv.lock package entry."""
        wheels = package_entry.get('wheels', []) or []
        if not isinstance(wheels, list):
            return []

        normalized_wheels = []
        for wheel_entry in wheels:
            if not isinstance(wheel_entry, dict):
                continue

            wheel_url = wheel_entry.get('url', '') or ''
            if not isinstance(wheel_url, str) or not wheel_url:
                continue

            packagetype = wheel_entry.get('packagetype', '') or ''
            if not isinstance(packagetype, str):
                packagetype = ''

            normalized_wheels.append({
                'url': wheel_url,
                'packagetype': packagetype or 'bdist_wheel',
            })

        return normalized_wheels

    def _build_uv_lock_package_info(self, package_entry):
        """Create a normalized package-info entry from a uv.lock package entry."""
        package_name = self._normalize_package_name(
            package_entry.get('name', '')
        )
        if not package_name:
            return None

        if not self.package_name:
            source_info = package_entry.get('source', {}) or {}
            if isinstance(source_info, dict) and source_info.get('editable') == '.':
                self.package_name = package_name

        return {
            'name': package_name,
            'version': package_entry.get('version', ''),
            'dependencies': [],
            'optional_dependencies': {},
            'wheels': self._get_uv_lock_package_wheels(package_entry),
        }

    def _build_uv_lock_package_map(self, package_entries):
        """Create a normalized package lookup table from uv.lock entries."""
        package_map = {}

        for package_entry in package_entries:
            package_info = self._build_uv_lock_package_info(package_entry)
            if not package_info:
                continue

            package_map[package_info['name']] = package_info

        return package_map

    def _parse_uv_lock_dependency(self, dependency, package_map):
        """Normalize a single uv.lock dependency entry for traversal."""
        if isinstance(dependency, dict):
            dependency_name = dependency.get('name') or dependency.get('package')

            marker_str = dependency.get('marker')
            if marker_str:
                try:
                    if not Marker(marker_str).evaluate():
                        return None
                except Exception as e:
                    logger.debug(
                        f"Failed to evaluate marker '{marker_str}': {e}"
                    )

            requested_extras = dependency.get('extra', []) or []
            if isinstance(requested_extras, str):
                requested_extras = [requested_extras]
            elif not isinstance(requested_extras, list):
                requested_extras = list(requested_extras)
        else:
            dependency_name = dependency
            requested_extras = []

        if not dependency_name:
            return None

        normalized_name = self._normalize_package_name(dependency_name)
        if normalized_name not in package_map:
            return None

        normalized_extras = []
        for extra_name in requested_extras:
            if not isinstance(extra_name, str):
                continue

            normalized_extra = self._normalize_package_name(extra_name)
            if normalized_extra not in normalized_extras:
                normalized_extras.append(normalized_extra)

        return {
            'name': normalized_name,
            'extras': normalized_extras,
        }

    def _populate_uv_lock_package_dependencies(self, package_entries, package_map):
        """Fill dependency and optional-dependency info for each uv.lock package."""
        for package_entry in package_entries:
            package_name = self._normalize_package_name(
                package_entry.get('name', '')
            )

            if not package_name or package_name not in package_map:
                continue

            dependency_items = []
            for dependency in package_entry.get('dependencies', []) or []:
                parsed_dependency = self._parse_uv_lock_dependency(
                    dependency,
                    package_map,
                )
                if parsed_dependency:
                    dependency_items.append(parsed_dependency)

            package_map[package_name]['dependencies'] = dependency_items

            optional_dependency_map = {}
            raw_optional_dependencies = (
                package_entry.get('optional-dependencies', {}) or {}
            )

            if isinstance(raw_optional_dependencies, dict):
                for extra_name, extra_dependencies in raw_optional_dependencies.items():
                    normalized_extra_name = self._normalize_package_name(extra_name)
                    parsed_extra_dependencies = []

                    for dependency in extra_dependencies or []:
                        parsed_dependency = self._parse_uv_lock_dependency(
                            dependency,
                            package_map,
                        )
                        if parsed_dependency:
                            parsed_extra_dependencies.append(parsed_dependency)

                    optional_dependency_map[normalized_extra_name] = parsed_extra_dependencies

            package_map[package_name]['optional_dependencies'] = optional_dependency_map

        return package_map

    def _infer_uv_lock_direct_packages_from_editable_project(self, package_entries, package_map):
        """Infer direct dependencies from the editable project entry in uv.lock."""
        editable_project_candidates = []
        for package_entry in package_entries:
            package_name = self._normalize_package_name(
                package_entry.get('name', '')
            )
            if not package_name:
                continue

            source_info = package_entry.get('source', {}) or {}
            if isinstance(source_info, dict) and source_info.get('editable') == '.':
                editable_project_candidates.append(package_name)

        if self.package_name and self.package_name in package_map:
            editable_project_candidates.append(self.package_name)

        for package_name in editable_project_candidates:
            package_info = package_map.get(package_name, {})
            if not package_info:
                continue

            dependency_names = []
            for dependency_info in package_info.get('dependencies', []) or []:
                dependency_name = dependency_info.get('name', '')
                if dependency_name and dependency_name in package_map:
                    dependency_names.append(dependency_name)

            if dependency_names:
                return dependency_names

        return []

    def _infer_uv_lock_root_candidates_from_graph(self, package_map):
        """Use dependency-in-degree to infer root candidates when uv.lock is the only source."""
        incoming_dependency_counts = {
            package_name: 0
            for package_name in package_map.keys()
        }

        for package_name, package_info in package_map.items():
            for dependency_info in package_info.get('dependencies', []) or []:
                dependency_name = dependency_info.get('name', '')
                if dependency_name in incoming_dependency_counts:
                    incoming_dependency_counts[dependency_name] += 1

        return [
            package_name
            for package_name, count in incoming_dependency_counts.items()
            if count == 0
        ]

    def _infer_uv_lock_traversal_roots(self, package_entries, package_map, direct_root_packages):
        """Determine traversal roots and direct dependency candidates for uv.lock analysis."""
        effective_direct_root_packages = list(direct_root_packages)

        if not effective_direct_root_packages:
            inferred_direct_packages = self._infer_uv_lock_direct_packages_from_editable_project(
                package_entries,
                package_map,
            )
            if not inferred_direct_packages:
                inferred_direct_packages = self._infer_uv_lock_root_candidates_from_graph(
                    package_map
                )
            effective_direct_root_packages = inferred_direct_packages

        traversal_roots = list(effective_direct_root_packages)
        if (
            self.package_name
            and self.package_name in package_map
            and self.package_name not in traversal_roots
        ):
            traversal_roots.insert(0, self.package_name)

        if not traversal_roots:
            traversal_roots = list(package_map.keys())

        return traversal_roots, effective_direct_root_packages

    def _build_uv_lock_metadata(self, uv_lock_data):
        """Build scanner metadata from pyproject.toml and uv.lock"""
        # 1. Read direct dependencies and project name from pyproject.toml.
        direct_root_packages = self._get_pyproject_root_packages()

        self.package_name = ''
        pyproject_project_name = self._get_pyproject_project_name()
        if pyproject_project_name:
            self.package_name = self._normalize_package_name(
                pyproject_project_name
            )

        # 2. Build package lookup table from uv.lock.
        package_entries = (
            uv_lock_data.get('package', [])
            if uv_lock_data
            else []
        )
        if not package_entries:
            return {}, []

        package_map = self._build_uv_lock_package_map(package_entries)
        package_map = self._populate_uv_lock_package_dependencies(package_entries, package_map, )

        # 3. Determine traversal roots.
        traversal_roots, effective_direct_root_packages = self._infer_uv_lock_traversal_roots(
            package_entries,
            package_map,
            direct_root_packages,
        )

        # 4. Traverse base dependencies and activated extras.
        selected_packages = []
        selected_package_set = set()
        base_dependencies_processed = set()
        processed_extras = {}
        relation_name_map = {}
        pending = []

        for package_name in reversed(traversal_roots):
            pending.append((package_name, set()))

        while pending:
            package_name, requested_extras = pending.pop()

            if package_name not in package_map:
                continue

            requested_extras = {
                self._normalize_package_name(extra_name)
                for extra_name in requested_extras
                if extra_name
            }

            old_extras = processed_extras.setdefault(
                package_name,
                set(),
            )
            new_extras = requested_extras - old_extras

            process_base_dependencies = (
                package_name not in base_dependencies_processed
            )

            if not process_base_dependencies and not new_extras:
                continue

            if package_name not in selected_package_set:
                selected_package_set.add(package_name)
                selected_packages.append(package_name)

            package_info = package_map[package_name]

            dependencies_to_process = []

            if process_base_dependencies:
                base_dependencies_processed.add(package_name)
                dependencies_to_process.extend(
                    package_info.get('dependencies', [])
                )

            optional_dependency_map = package_info.get(
                'optional_dependencies',
                {},
            )

            for extra_name in new_extras:
                dependencies_to_process.extend(
                    optional_dependency_map.get(extra_name, [])
                )

            old_extras.update(new_extras)

            parent_dependencies = relation_name_map.setdefault(
                package_name,
                set(),
            )

            for dependency_info in dependencies_to_process:
                dependency_name = dependency_info.get('name', '')
                dependency_extras = set(dependency_info.get('extras', []) or [])

                if dependency_name not in package_map:
                    continue

                parent_dependencies.add(dependency_name)

                pending.append((dependency_name, dependency_extras,))

        if not selected_packages:
            selected_packages = list(package_map.keys())
            selected_package_set = set(selected_packages)

        self.set_manifest_file(['uv.lock'])
        self.total_dep_list = selected_packages
        self.direct_dep = True
        self.direct_dep_list = []
        self.relation_tree = {}

        direct_dependency_candidates = list(direct_root_packages)
        if not direct_dependency_candidates:
            direct_dependency_candidates = list(effective_direct_root_packages)

        for package_name in direct_dependency_candidates:
            package_info = package_map.get(package_name)
            if not package_info:
                continue

            package_version = package_info.get('version', '')
            self.direct_dep_list.append(
                f'{package_name}({package_version})'
            )

        for package_name in selected_packages:
            package_info = package_map.get(package_name, {})
            package_version = package_info.get('version', '')
            package_key = f'{package_name}({package_version})'

            if package_name == self.package_name:
                self.relation_tree[package_key] = []
                continue

            dependency_keys = []

            dependency_names = relation_name_map.get(package_name, set(), )

            for dependency_name in sorted(dependency_names):
                if dependency_name not in selected_package_set:
                    continue

                dependency_info = package_map.get(dependency_name, {}, )
                dependency_version = dependency_info.get('version', '', )
                dependency_keys.append(f'{dependency_name}({dependency_version})')

            self.relation_tree[package_key] = dependency_keys

        return package_map, selected_packages

    def _get_empty_metadata(self):
        """Return the default metadata shape used by the uv.lock flow."""
        return {
            'license_expression': '',
            'classifier': [],
            'license': '',
            'license_file': [],
            'home_page': '',
            'download_url': '',
            'project_url': [],
        }

    def _get_uv_lock_direct_url(self, package_name):
        """Return the direct-url entry for the local project when it matches the package name."""
        if package_name != self.package_name:
            return {}

        local_project_path = os.path.abspath(self.input_dir)
        return {
            'url': f'file://{local_project_path}',
            'dir_info': {
                'editable': False,
            },
        }

    def _build_installed_package_entry(
        self,
        package_name,
        package_version,
        metadata,
        direct_url=None,
        installer='uv',
    ):
        metadata = metadata or {}
        default_mdata = self._get_empty_metadata()

        return {
            'metadata': {
                'name': package_name,
                'version': package_version,
                'license_expression': metadata.get('license_expression', default_mdata.get('license_expression', ''), ),
                'classifier': metadata.get('classifier', default_mdata.get('classifier', []), ),
                'license': metadata.get('license', default_mdata.get('license', ''), ),
                'license_file': metadata.get('license_file', default_mdata.get('license_file', []), ),
                'home_page': metadata.get('home_page', default_mdata.get('home_page', ''), ),
                'download_url': metadata.get('download_url', default_mdata.get('download_url', ''), ),
                'project_url': metadata.get('project_url', default_mdata.get('project_url', []), ),
            },
            'direct_url': direct_url or {},
            'installer': installer,
        }

    def _write_dependency_input_file(self, package_entries):
        if not self.tmp_file_name:
            tmp_file_path = ''
        elif os.path.isabs(self.tmp_file_name):
            tmp_file_path = self.tmp_file_name
        else:
            input_dir = self.input_dir or os.getcwd()
            tmp_file_path = os.path.join(input_dir, self.tmp_file_name)

        parent_dir = os.path.dirname(tmp_file_path)
        if parent_dir and not os.path.isdir(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        if self.tmp_file_name not in self.input_package_list_file:
            self.append_input_package_list_file(self.tmp_file_name)

        with open(tmp_file_path, 'w', encoding='utf-8') as output_file:
            json.dump({'installed': package_entries}, output_file)

        return tmp_file_path

    def _resolve_uv_license_metadata(self, info):
        """Normalize PyPI metadata into a license-focused shape for the uv.lock flow."""
        info = info or {}

        license_expression = info.get('license_expression', '') or ''
        if isinstance(license_expression, str):
            license_expression = license_expression.strip()
        else:
            license_expression = ''

        license_info = info.get('license', '') or ''
        if isinstance(license_info, str):
            license_info = license_info.strip()
        else:
            license_info = ''

        if license_info and ('\n' in license_info or '\r' in license_info):
            detected_license = check_license_name(license_info)
            if detected_license:
                license_info = detected_license
            else:
                license_info = ''

        classifiers = info.get('classifiers', []) or []
        if not isinstance(classifiers, list):
            classifiers = []

        license_classifiers = []
        for classifier in classifiers:
            if not isinstance(classifier, str):
                continue
            if not classifier.startswith('License ::'):
                continue

            parts = classifier.split(' :: ')
            if len(parts) < 2:
                continue

            classifier_license = parts[-1].strip()
            if classifier_license in {'', 'OSI Approved'}:
                continue
            if classifier_license not in license_classifiers:
                license_classifiers.append(classifier_license)

        license_files = info.get('license_files', []) or []
        if isinstance(license_files, str):
            license_files = [license_files]
        elif not isinstance(license_files, list):
            try:
                license_files = list(license_files)
            except TypeError:
                license_files = []

        return {
            'license_expression': license_expression,
            'license': license_info,
            'classifier': classifiers,
            'license_file': license_files,
            'license_classifiers': license_classifiers,
        }

    def _resolve_core_metadata_license_metadata(self, metadata_text):
        """Parse wheel core metadata into the same shape used by PyPI JSON."""
        metadata_text = metadata_text or ''
        if not isinstance(metadata_text, str):
            metadata_text = ''

        license_expression = ''
        license_info = ''
        classifiers = []
        license_classifiers = []
        license_files = []

        for line in metadata_text.splitlines():
            if line.startswith('License-Expression:'):
                value = line.split(':', 1)[1].strip()
                if value:
                    license_expression = value
            elif line.startswith('License:'):
                value = line.split(':', 1)[1].strip()
                if value:
                    license_info = value
            elif line.startswith('Classifier:'):
                value = line.split(':', 1)[1].strip()
                if value and value not in classifiers:
                    classifiers.append(value)
                if value.startswith('License ::'):
                    parts = value.split(' :: ')
                    if len(parts) >= 2:
                        classifier_license = parts[-1].strip()
                        if classifier_license not in {'', 'OSI Approved'} and classifier_license not in license_classifiers:
                            license_classifiers.append(classifier_license)
            elif line.startswith('License-File:'):
                value = line.split(':', 1)[1].strip()
                if value and value not in license_files:
                    license_files.append(value)

        return {
            'license_expression': license_expression,
            'license': license_info,
            'classifier': classifiers,
            'license_file': license_files,
            'license_classifiers': license_classifiers,
        }

    def _merge_uv_license_metadata(self, info, core_metadata=None):
        """Prefer core metadata when present, and fall back to PyPI JSON metadata otherwise."""
        merged_metadata = self._resolve_uv_license_metadata(info)
        if not core_metadata:
            return merged_metadata

        if isinstance(core_metadata, str):
            core_metadata = self._resolve_core_metadata_license_metadata(core_metadata)

        if not isinstance(core_metadata, dict):
            return merged_metadata

        for key in ['license_expression', 'license']:
            value = core_metadata.get(key, '') or ''
            if isinstance(value, str):
                value = value.strip()
            else:
                value = ''
            if value:
                merged_metadata[key] = value

        classifier_values = core_metadata.get('classifier', []) or []
        if isinstance(classifier_values, list):
            normalized_classifiers = [c for c in classifier_values if isinstance(c, str) and c]
            if normalized_classifiers:
                merged_metadata['classifier'] = normalized_classifiers

        license_file_values = core_metadata.get('license_file', []) or []
        if isinstance(license_file_values, list):
            normalized_license_files = [f for f in license_file_values if isinstance(f, str) and f]
            if normalized_license_files:
                merged_metadata['license_file'] = normalized_license_files

        license_classifiers = core_metadata.get('license_classifiers', []) or []
        if isinstance(license_classifiers, list):
            normalized_classifiers = [c for c in license_classifiers if isinstance(c, str) and c]
            if normalized_classifiers:
                merged_metadata['license_classifiers'] = normalized_classifiers

        return merged_metadata

    def _fetch_core_metadata_from_wheel(self, release_urls):
        """Try to read wheel METADATA from the release list and return the parsed license fields."""
        for release in release_urls:
            if not isinstance(release, dict):
                continue

            if release.get('packagetype') != 'bdist_wheel':
                continue

            url_value = release.get('url', '') or ''
            if not isinstance(url_value, str) or not url_value:
                continue

            try:
                req = urllib.request.Request(
                    url_value,
                    headers={
                        'User-Agent': 'fosslight-dependency',
                        'Accept': 'application/octet-stream',
                    },
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    wheel_bytes = response.read()

                with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as wheel_archive:
                    for archive_name in wheel_archive.namelist():
                        if not archive_name.endswith('.dist-info/METADATA'):
                            continue
                        metadata_text = wheel_archive.read(archive_name).decode('utf-8', 'ignore')
                        return self._resolve_core_metadata_license_metadata(metadata_text)
            except Exception as e:
                logger.debug(
                    f'Failed to fetch wheel core metadata from {url_value}: {e}'
                )

        return None

    def _fetch_pypi_metadata(self, package_name, package_version, wheel_urls=None):
        url = (
            f'https://pypi.org/pypi/'
            f'{package_name}/{package_version}/json'
        )

        try:
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'fosslight-dependency',
                    'Accept': 'application/json',
                },
            )

            with urllib.request.urlopen(
                req,
                timeout=10,
            ) as response:
                data = json.load(response)

        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            json.JSONDecodeError,
            TimeoutError,
            Exception,
        ) as e:
            logger.debug(
                f'Failed to fetch PyPI metadata for '
                f'{package_name}({package_version}): {e}'
            )
            data = {}

        info = data.get('info', {}) or {}
        core_metadata = None
        if isinstance(wheel_urls, list) and wheel_urls:
            core_metadata = self._fetch_core_metadata_from_wheel(wheel_urls)

        if not core_metadata:
            release_urls = data.get('urls', []) or []
            if isinstance(release_urls, list):
                core_metadata = self._fetch_core_metadata_from_wheel(release_urls)

        license_metadata = self._merge_uv_license_metadata(info, core_metadata)

        project_urls = info.get('project_urls', {}) or {}
        if not isinstance(project_urls, dict):
            project_urls = {}

        home_page = info.get('home_page', '') or ''
        download_url = info.get('download_url', '') or ''

        project_url_list = []

        for label, url_value in project_urls.items():
            if not url_value:
                continue

            project_url_list.append(
                f'{label}, {url_value}'
            )

        return {
            'license': license_metadata.get('license', ''),
            'license_expression': license_metadata.get('license_expression', ''),
            'classifier': license_metadata.get('classifier', []),
            'license_file': license_metadata.get('license_file', []),
            'home_page': home_page,
            'download_url': download_url,
            'project_url': project_url_list,
        }

    def _prepare_uv_lock_direct(self):
        uv_lock_path = os.path.join(self.input_dir, 'uv.lock')

        try:
            with open(uv_lock_path, 'rb') as fh:
                uv_lock_data = tomllib.load(fh)
        except Exception as e:
            logger.warning(f'Failed to parse uv.lock: {e}')
            return False

        package_map, selected_packages = self._build_uv_lock_metadata(
            uv_lock_data
        )

        # Fetch PyPI metadata for each selected package and write the input file.
        self.input_package_list_file = []
        installed_packages = []

        for package_name in selected_packages:
            package_info = package_map.get(package_name, {})
            package_version = package_info.get('version', '')
            wheel_urls = package_info.get('wheels', []) or []

            metadata = self._fetch_pypi_metadata(
                package_name,
                package_version,
                wheel_urls=wheel_urls,
            )

            if metadata is None:
                metadata = self._get_empty_metadata()

            direct_url = self._get_uv_lock_direct_url(package_name)

            installed_packages.append(
                self._build_installed_package_entry(
                    package_name,
                    package_version,
                    metadata,
                    direct_url,
                )
            )

        self._write_dependency_input_file(installed_packages)

        return True

    def _get_pyproject_project_name(self):
        pyproject_path = os.path.join(self.input_dir, 'pyproject.toml')
        if not os.path.isfile(pyproject_path):
            return ''

        try:
            with open(pyproject_path, 'rb') as fh:
                pyproject_data = tomllib.load(fh)
        except Exception:
            return ''

        project_data = pyproject_data.get('project', {})
        project_name = project_data.get('name', '')
        if isinstance(project_name, str) and project_name.strip():
            return project_name
        return ''

    def run_plugin(self):
        ret = True

        uv_lock_path = os.path.join(self.input_dir, 'uv.lock')
        if os.path.exists(uv_lock_path):
            ret = self._prepare_uv_lock_direct()
            if not ret:
                logger.warning("Failed to prepare uv.lock metadata; falling back to virtualenv inspection.")
                if self.manifest_file_name and 'uv.lock' in self.manifest_file_name:
                    self.manifest_file_name = [m for m in self.manifest_file_name if m != 'uv.lock']
                    self.set_manifest_file(self.manifest_file_name)
                ret = True
            else:
                return ret

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
            ret = self.start_pip_inspect()

        return ret

    def create_virtualenv(self):
        ret = True

        manifest_files = self.manifest_file_name
        if not manifest_files:
            manifest_files = copy.deepcopy(const.SUPPORT_PACKAGE[self.package_manager_name])
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
            create_venv_cmd = f"virtualenv -p python3 {self.venv_tmp_dir}"
            activate_cmd = ". " + os.path.join(venv_path, "bin", "activate")
            cmd_separator = ";"

        if install_cmd_list:
            install_cmd = cmd_separator.join(install_cmd_list)
        else:
            logger.error(const.SUPPORT_PACKAGE[self.package_manager_name])
            logger.error('Cannot create virtualenv because it cannot find: '
                         + ', '.join(const.SUPPORT_PACKAGE[self.package_manager_name]))
            logger.error("Please run with '-a' and '-d' option.")
            return False

        deactivate_cmd = "deactivate"
        pip_upgrade_cmd = "pip install --upgrade pip"

        self.set_pip_activate_cmd(activate_cmd)
        self.set_pip_deactivate_cmd(deactivate_cmd)

        cmd_list = [create_venv_cmd, activate_cmd, install_cmd, pip_upgrade_cmd, deactivate_cmd]
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
                    create_venv_cmd = f"python3 -m venv {self.venv_tmp_dir}"

                    cmd_list = [create_venv_cmd, activate_cmd, install_cmd, pip_upgrade_cmd, deactivate_cmd]
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

    def start_pip_inspect(self):
        ret = True
        pipdeptree = 'pipdeptree'
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

        exists_pipdeptree = False
        try:
            cmd_ret = subprocess.call(command, shell=True)
            if cmd_ret != 0:
                ret = False
                err_msg = f"cmd ret code({cmd_ret})"
            else:
                if os.path.isfile(tmp_pip_list):
                    with open(tmp_pip_list, 'r', encoding='utf-8') as pip_list_file:
                        for pip_list in pip_list_file.readlines():
                            pip_list_name = pip_list.split('==')[0]
                            if pip_list_name == pipdeptree:
                                exists_pipdeptree = True
                                break
                    os.remove(tmp_pip_list)
        except Exception as e:
            ret = False
            err_msg = str(e)

        if not ret:
            logger.error(f"Failed to freeze dependencies ({command}): {err_msg})")
            return False

        command_list = []
        command_list.append(activate_command)

        pip_inspect_command = f"{python_cmd} pip inspect > {self.tmp_file_name}"
        command_list.append(pip_inspect_command)

        if not exists_pipdeptree:
            install_deptree_command = f"{python_cmd} pip install {pipdeptree}"
            command_list.append(install_deptree_command)
            uninstall_deptree_command = f"{python_cmd} pip uninstall -y {pipdeptree}"
        pipdeptree_command = f"{pipdeptree} --json-tree -e 'pipdeptree,pip,wheel,setuptools' > {self.tmp_deptree_file}"
        command_list.append(pipdeptree_command)

        if not exists_pipdeptree:
            command_list.append(uninstall_deptree_command)

        command_list.append(deactivate_command)
        command = command_separator.join(command_list)

        try:
            cmd_ret = subprocess.call(command, shell=True)
            if cmd_ret == 0:
                if os.path.exists(self.tmp_file_name):
                    self.append_input_package_list_file(self.tmp_file_name)

                    with open(self.tmp_file_name, 'r', encoding='utf-8') as json_f:
                        inspect_data = json.load(json_f)
                        for package in inspect_data.get('installed', []):
                            metadata = package.get('metadata', {})
                            package_name = metadata.get('name', '')
                            if package_name:
                                if package_name in ['pip', 'setuptools', 'wheel']:
                                    continue
                                self.total_dep_list.append(re.sub(r"[-_.]+", "-", package_name).lower())
                else:
                    logger.error(f"pip inspect output file not found: {self.tmp_file_name}")
                    ret = False
            else:
                logger.error(f"Failed to run command: {command}")
                ret = False
        except Exception as e:
            ret = False
            logger.error(f"Failed to get package information using pip inspect: {e}")

        return ret

    def parse_oss_information(self, f_name):
        purl_dict = {}
        try:
            oss_init_name = ''
            with open(f_name, 'r', encoding='utf-8') as json_file:
                inspect_data = json.load(json_file)

            for package in inspect_data.get('installed', []):
                dep_item = DependencyItem()
                oss_item = OssItem()
                metadata = package.get('metadata', {})
                if not metadata:
                    continue

                oss_init_name = metadata.get('name', '')
                oss_init_name = re.sub(r"[-_.]+", "-", oss_init_name).lower()
                if oss_init_name not in self.total_dep_list:
                    continue
                oss_item.name = f"{self.package_manager_name}:{oss_init_name}"
                oss_item.version = metadata.get('version', '')

                # license_expression > classifier > license > license_file
                license_info = check_UNKNOWN(metadata.get('license_expression', ''))
                if not license_info:
                    classifiers = metadata.get('classifier', [])
                    license_classifiers = [c for c in classifiers if c.startswith('License ::')]
                    if license_classifiers:
                        license_info_l = []
                        for license_classifier in license_classifiers:
                            parts = license_classifier.split(' :: ')
                            if len(parts) >= 2:
                                license_name = parts[-1].strip()
                                if license_name and license_name != 'OSI Approved':
                                    license_info_l.append(license_name)
                                    break
                        license_info = ','.join(license_info_l)
                if not license_info:
                    license_info = metadata.get('license', '')
                    if '\n' in license_info:
                        license_info = check_UNKNOWN(check_license_name(license_info))
                if not license_info:
                    license_files_meta = metadata.get('license_file')
                    license_info_list = self.get_license_from_file(
                        oss_init_name,
                        oss_item.version,
                        license_files_meta
                    )
                    if license_info_list:
                        license_info = ','.join(license_info_list)
                license_name = check_UNKNOWN(license_info)
                if license_name:
                    license_name = license_name.replace(';', ',')
                oss_item.license = license_name

                oss_item.download_location = f"{self.dn_url}{oss_init_name}/{oss_item.version}"

                # project_url 'source' > download_url > project_url 'homepage' > homepage
                homepage_url = check_UNKNOWN(metadata.get('home_page', ''))
                download_url = check_UNKNOWN(metadata.get('download_url', ''))
                project_urls = check_UNKNOWN(metadata.get('project_url', []))
                if project_urls:
                    priority_order = ['source', 'repository', 'github', 'code', 'source code', 'homepage']
                    for priority in priority_order:
                        for url_entry in project_urls:
                            url_entry_lower = url_entry.lower()
                            if url_entry_lower.startswith(priority):
                                download_url = url_entry.split(', ')[-1]
                                break
                        if download_url:
                            break
                oss_item.homepage = download_url or homepage_url or f"{self.dn_url}{oss_init_name}"

                dep_item.purl = get_url_to_purl(oss_item.download_location, self.package_manager_name)
                purl_dict[f'{oss_init_name}({oss_item.version})'] = dep_item.purl

                direct_url = package.get('direct_url', {})
                is_local = False
                local_path_comment = ''
                if direct_url:
                    direct_url_str = direct_url.get('url', '')
                    if direct_url_str.startswith('file://'):
                        is_local = True
                        local_path = direct_url_str[len('file://'):]
                        local_path = re.sub(r'^/([A-Za-z]:)', r'\1', local_path)
                        local_path = os.path.normpath(local_path)
                        oss_item.download_location = ''
                        oss_item.homepage = ''
                        local_path_comment = f'local: {local_path}'
                    else:
                        oss_item.download_location = direct_url_str
                        oss_item.homepage = oss_item.download_location
                if not is_local and not package.get('installer', ''):
                    oss_item.download_location = oss_item.homepage

                comment = ''
                if oss_init_name == self.package_name:
                    comment = 'root package'
                elif self.direct_dep and len(self.direct_dep_list) > 0:
                    if f'{oss_init_name}({oss_item.version})' in self.direct_dep_list:
                        comment = 'direct'
                    else:
                        comment = 'transitive'
                dep_key = f'{oss_init_name}({oss_item.version})'
                if dep_key in self.relation_tree:
                    dep_item.depends_on_raw = self.relation_tree[dep_key]

                if comment:
                    if comment == 'root package' and local_path_comment:
                        oss_item.comment = f'{comment} / {local_path_comment}'
                    else:
                        oss_item.comment = comment
                elif local_path_comment:
                    oss_item.comment = local_path_comment

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
        if 'uv.lock' in self.manifest_file_name:
            self.direct_dep = True
            return

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
