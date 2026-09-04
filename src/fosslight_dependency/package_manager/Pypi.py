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
import shlex
import sys
import tempfile
import urllib.request
import urllib.error
import zipfile

try:
    import tomllib
except ModuleNotFoundError:
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

MAX_WHEEL_SIZE = 100 * 1024 * 1024

MAX_ERR_OUTPUT_CHARS = 2000

# Child process output can carry credentials: a private index is configured with
# --extra-index-url/--index-url (see run_plugin), and pip echoes that URL in its error
# messages. Mask them before the text reaches a log file or CI output.
_SECRET_PATTERNS = (
    # https://user:token@host -> https://user:***@host  (keep the user for diagnosis)
    (re.compile(r'(?<=://)([^/\s:@]+):[^/\s@]+@'), r'\1:***@'),
    # https://token@host -> https://***@host
    (re.compile(r'(?<=://)[^/\s:@]+@'), '***@'),
    # token=..., api_key: ..., password=...
    (re.compile(r'((?:token|api[-_]?key|secret|password|passwd|pwd)["\']?\s*[=:]\s*)\S+',
                re.IGNORECASE), r'\1***'),
    # Authorization: Bearer <value>
    (re.compile(r'(authorization\s*:\s*(?:bearer|basic|token)?\s*)\S+', re.IGNORECASE), r'\1***'),
)


def redact_secrets(text):
    """Mask credentials in text that is about to be logged."""
    if not text:
        return text
    text = str(text)
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def describe_venv_failure(cmd_ret):
    stderr_text = ''
    raw = getattr(cmd_ret, 'stderr', None)
    if raw:
        stderr_text = raw.decode('utf-8', errors='replace') if isinstance(raw, bytes) else str(raw)
        stderr_text = redact_secrets(stderr_text.strip())
        if len(stderr_text) > MAX_ERR_OUTPUT_CHARS:
            stderr_text = '...\n' + stderr_text[-MAX_ERR_OUTPUT_CHARS:]

    if cmd_ret.returncode != 0:
        msg = f"return code({cmd_ret.returncode})"
        return False, f"{msg}\n{stderr_text}" if stderr_text else msg
    if stderr_text.lower().startswith('error:'):
        return False, stderr_text
    return True, ''


def quote_shell_path(path):
    """Quote a path that is interpolated into a shell command chain.

    On POSIX, shlex.quote() single-quotes the value, so neither $(...) command
    substitution nor $VAR expansion can happen. On Windows the command runs through
    cmd.exe, where %VAR% is expanded before parsing and there is no escape that works
    both inside and outside a batch file, so double quotes only cover whitespace there;
    removing shell=True is the real fix on that platform.
    """
    if os.name == 'nt':
        return f'"{path}"'
    return shlex.quote(path)


def venv_interpreter(fallback):
    """The interpreter used to create the temporary virtualenv.

    Resolving a bare 'python'/'python3' through PATH picks whatever comes first, which
    on Windows is often the Microsoft Store stub (it exits without creating anything)
    and elsewhere can be a version that has no wheels for the analyzed dependencies.
    sys.executable is the interpreter already running the scanner, so it is known to
    exist and to be usable. It also keeps get_virtualenv_site_packages() correct: that
    lookup builds the POSIX path from sys.version_info, so a virtualenv created by a
    different minor version would not be found.
    """
    if not sys.executable:
        return fallback
    return quote_shell_path(sys.executable)


def quote_activate_cmd(activate_cmd):
    for prefix in ('source ', '. '):
        if activate_cmd.startswith(prefix):
            path = activate_cmd[len(prefix):]
            return f'{prefix}{quote_shell_path(path)}' if os.path.isabs(path) else activate_cmd
    if activate_cmd.startswith('conda '):
        return activate_cmd
    return quote_shell_path(activate_cmd) if os.path.isabs(activate_cmd) else activate_cmd


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
        # Create the temporary virtualenv outside the analysis target. The analysis
        # chdirs into the target, so a relative name put the venv inside the user's
        # project: for a deeply nested project the venv's internal paths exceed the
        # Windows MAX_PATH limit (260) and the analysis fails, and it also leaves
        # build artifacts in the source tree.
        #
        # mkdtemp() gives an exclusive directory per instance. A shared path would be
        # unsafe here: get_virtualenv_site_packages() looks at this directory before the
        # caller-supplied activation environment, so a directory left over from an
        # earlier run (process ids are reused) could supply license information for
        # unrelated packages, and __del__() would remove a directory another instance is
        # still using.
        self.venv_tmp_dir = tempfile.mkdtemp(prefix='fosslight_venv_')

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
            venv_path = self.venv_tmp_dir
            if os.path.exists(venv_path):
                # A virtualenv puts packages under Lib\site-packages on Windows and
                # lib/pythonX.Y/site-packages on POSIX, so try both. Assigning the POSIX
                # candidate to site_packages up front used to leak a non-existent path
                # out of this function when neither branch matched.
                for candidate in (
                    os.path.join(venv_path, 'Lib', 'site-packages'),
                    os.path.join(venv_path, 'lib',
                                 f"python{sys.version_info.major}.{sys.version_info.minor}",
                                 'site-packages'),
                ):
                    if os.path.exists(candidate):
                        return candidate

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

        parsed = self._resolve_core_metadata_license_metadata(metadata_text)
        license_value = parsed.get('license_expression', '') or parsed.get('license', '')
        if not license_value:
            return ''
        return check_UNKNOWN(check_license_name(license_value)) or ''

    def _normalize_package_name(self, package_name):
        return re.sub(r"[-_.]+", "-", package_name).strip().lower()

    def _normalize_extra_names(self, extra_names):
        """Normalize a collection of extra names, de-duplicating while preserving order."""
        normalized_names = []
        for extra_name in extra_names or []:
            if not isinstance(extra_name, str):
                continue
            normalized_extra = self._normalize_package_name(extra_name)
            if normalized_extra not in normalized_names:
                normalized_names.append(normalized_extra)
        return normalized_names

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

        source_info = package_entry.get('source', {}) or {}
        if not isinstance(source_info, dict):
            source_info = {}

        if not self.package_name and source_info.get('editable') == '.':
            self.package_name = package_name

        return {
            'name': package_name,
            'version': package_entry.get('version', ''),
            'dependencies': [],
            'optional_dependencies': {},
            'wheels': self._get_uv_lock_package_wheels(package_entry),
            'source': source_info,
        }

    def _evaluate_uv_lock_package_marker(self, package_entry):
        """Return whether a uv.lock package entry is applicable in the current environment.

        Package-level fork variants (e.g. platform/python-specific wheel builds) are
        recorded under the plural `resolution-markers` key as a list of full marker
        strings; the variant applies if any of them evaluates to true (they are OR'd
        together, mirroring uv's own fork-selection semantics). A singular `marker`
        key is also honored if present, for forward/backward compatibility.
        """
        marker_values = []

        resolution_markers = package_entry.get('resolution-markers')
        if isinstance(resolution_markers, list):
            marker_values.extend(m for m in resolution_markers if isinstance(m, str) and m.strip())
        elif isinstance(resolution_markers, str) and resolution_markers.strip():
            marker_values.append(resolution_markers)

        single_marker = package_entry.get('marker')
        if isinstance(single_marker, str) and single_marker.strip():
            marker_values.append(single_marker)

        if not marker_values:
            return True

        for marker_value in marker_values:
            marker_value = marker_value.strip()
            try:
                if Marker(marker_value).evaluate():
                    return True
            except Exception as e:
                logger.debug(f"Failed to evaluate uv.lock package marker '{marker_value}': {e}")
                # An unparsable marker is treated as a wildcard so a valid variant
                # is not silently dropped.
                return True

        return False

    def _select_uv_lock_package_entries(self, package_entries):
        """Select one package entry per normalized package name using current-environment markers."""
        grouped_entries = {}
        for package_entry in package_entries or []:
            package_name = self._normalize_package_name(package_entry.get('name', ''))
            if not package_name:
                continue
            grouped_entries.setdefault(package_name, []).append(package_entry)

        selected_entries = []
        for package_name, entries in grouped_entries.items():
            matching_entries = [entry for entry in entries if self._evaluate_uv_lock_package_marker(entry)]
            if not matching_entries:
                matching_entries = entries
            elif len(matching_entries) > 1:
                unmarked_entries = [
                    entry for entry in matching_entries
                    if not entry.get('marker') and not entry.get('resolution-markers')
                ]
                if unmarked_entries:
                    matching_entries = unmarked_entries

            if len(matching_entries) > 1:
                logger.warning(
                    "Multiple uv.lock package entries for '%s' matched the current environment; using the first entry.",
                    package_name,
                )

            selected_entries.append(matching_entries[0])

        return selected_entries

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
                try:
                    requested_extras = list(requested_extras)
                except TypeError:
                    requested_extras = []
        else:
            dependency_name = dependency
            requested_extras = []

        if not dependency_name:
            return None

        normalized_name = self._normalize_package_name(dependency_name)
        if normalized_name not in package_map:
            return None

        return {
            'name': normalized_name,
            'extras': self._normalize_extra_names(requested_extras),
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

    def _collect_uv_lock_dependencies_to_walk(self, package_info, include_base_dependencies, extras_to_activate):
        """Return the dependency entries to walk next for one traversal step.

        Includes the package's base `dependencies` when `include_base_dependencies` is
        True, plus the dependencies declared under each extra in `extras_to_activate`.
        """
        dependencies_to_walk = []

        if include_base_dependencies:
            dependencies_to_walk.extend(package_info.get('dependencies', []))

        optional_dependency_map = package_info.get('optional_dependencies', {})
        for extra_name in extras_to_activate:
            dependencies_to_walk.extend(optional_dependency_map.get(extra_name, []))

        return dependencies_to_walk

    def _traverse_uv_lock_packages(self, traversal_roots, package_map):
        """Walk the uv.lock dependency graph from the traversal roots.

        Returns (selected_packages, selected_package_set, relation_name_map) where
        relation_name_map maps a package name to the set of its direct dependency names
        that were reached during traversal.
        """
        selected_packages = []
        selected_package_set = set()
        base_dependencies_processed = set()
        processed_extras = {}
        relation_name_map = {}
        pending = [(package_name, set()) for package_name in reversed(traversal_roots)]

        while pending:
            package_name, requested_extras = pending.pop()

            if package_name not in package_map:
                continue

            requested_extras = set(self._normalize_extra_names(requested_extras))

            old_extras = processed_extras.setdefault(package_name, set())
            new_extras = requested_extras - old_extras

            process_base_dependencies = package_name not in base_dependencies_processed
            if not process_base_dependencies and not new_extras:
                continue

            if package_name not in selected_package_set:
                selected_package_set.add(package_name)
                selected_packages.append(package_name)

            package_info = package_map[package_name]
            dependencies_to_process = self._collect_uv_lock_dependencies_to_walk(
                package_info,
                process_base_dependencies,
                new_extras,
            )

            base_dependencies_processed.add(package_name)
            old_extras.update(new_extras)

            parent_dependencies = relation_name_map.setdefault(package_name, set())

            for dependency_info in dependencies_to_process:
                dependency_name = dependency_info.get('name', '')
                if dependency_name not in package_map:
                    continue

                parent_dependencies.add(dependency_name)

                dependency_extras = set(dependency_info.get('extras', []) or [])
                pending.append((dependency_name, dependency_extras))

        if not selected_packages:
            selected_packages = list(package_map.keys())
            selected_package_set = set(selected_packages)

        return selected_packages, selected_package_set, relation_name_map

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
            logger.warning('No package entries found in uv.lock.')
            return {}, []

        selected_package_entries = self._select_uv_lock_package_entries(package_entries)
        package_map = self._build_uv_lock_package_map(selected_package_entries)
        package_map = self._populate_uv_lock_package_dependencies(selected_package_entries, package_map)

        # 3. Determine traversal roots.
        traversal_roots, effective_direct_root_packages = self._infer_uv_lock_traversal_roots(
            selected_package_entries,
            package_map,
            direct_root_packages,
        )

        # 4. Traverse base dependencies and activated extras.
        selected_packages, selected_package_set, relation_name_map = self._traverse_uv_lock_packages(
            traversal_roots,
            package_map,
        )

        self.set_manifest_file(['uv.lock'])
        self.total_dep_list = selected_packages
        self.direct_dep = True

        direct_dependency_candidates = list(direct_root_packages) or list(effective_direct_root_packages)
        self.direct_dep_list = self._build_uv_lock_direct_dep_list(
            package_map,
            direct_dependency_candidates,
        )
        self.relation_tree = self._build_uv_lock_relation_tree(
            package_map,
            selected_packages,
            selected_package_set,
            relation_name_map,
        )

        return package_map, selected_packages

    def _build_uv_lock_direct_dep_list(self, package_map, direct_dependency_candidates):
        """Render '<name>(<version>)' entries for the resolved direct dependencies."""
        direct_dep_list = []
        for package_name in direct_dependency_candidates:
            package_info = package_map.get(package_name)
            if not package_info:
                continue

            package_version = package_info.get('version', '')
            direct_dep_list.append(f'{package_name}({package_version})')

        return direct_dep_list

    def _build_uv_lock_relation_tree(self, package_map, selected_packages, selected_package_set, relation_name_map):
        """Render the package relation tree keyed by '<name>(<version>)'."""
        relation_tree = {}
        for package_name in selected_packages:
            package_info = package_map.get(package_name, {})
            package_version = package_info.get('version', '')
            package_key = f'{package_name}({package_version})'

            if package_name == self.package_name:
                relation_tree[package_key] = []
                continue

            dependency_keys = []
            for dependency_name in sorted(relation_name_map.get(package_name, set())):
                if dependency_name not in selected_package_set:
                    continue

                dependency_info = package_map.get(dependency_name, {})
                dependency_version = dependency_info.get('version', '')
                dependency_keys.append(f'{dependency_name}({dependency_version})')

            relation_tree[package_key] = dependency_keys

        return relation_tree

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

    def _is_uv_lock_registry_source(self, source_info):
        """Return whether a uv.lock package source is a package registry (e.g. PyPI).

        Only registry sources are safe to look up by name/version against the public
        PyPI JSON API: a git/url/path source can share a name with an unrelated public
        package, so querying PyPI for it would attach that unrelated package's license
        and links instead of the actual dependency's.
        """
        return isinstance(source_info, dict) and bool(source_info.get('registry'))

    def _get_uv_lock_source_url(self, source_info):
        """Best-effort URL describing a non-registry uv.lock package source."""
        if not isinstance(source_info, dict):
            return ''

        git_url = source_info.get('git')
        if isinstance(git_url, str) and git_url:
            rev = source_info.get('rev') or source_info.get('commit')
            return f'{git_url}@{rev}' if rev else git_url

        url_value = source_info.get('url')
        if isinstance(url_value, str) and url_value:
            return url_value

        local_path = source_info.get('path') or source_info.get('directory')
        if isinstance(local_path, str) and local_path:
            if not os.path.isabs(local_path):
                local_path = os.path.join(self.input_dir, local_path)
            return f'file://{os.path.abspath(local_path)}'

        return ''

    def _get_uv_lock_direct_url(self, package_name, source_info=None):
        """Return the direct-url entry for the local project or a non-registry package source."""
        if package_name == self.package_name:
            local_project_path = os.path.abspath(self.input_dir)
            return {
                'url': f'file://{local_project_path}',
                'dir_info': {
                    'editable': False,
                },
            }

        source_url = self._get_uv_lock_source_url(source_info)
        if source_url:
            return {'url': source_url}

        return {}

    def _fetch_uv_lock_local_source_metadata(self, wheel_urls):
        """Build metadata for a non-registry uv.lock package from its wheel core metadata only.

        There is no registry entry to query, so license fields come solely from the wheel
        (when one is listed); other fields are left empty and filled in by the caller from
        the recorded source URL.
        """
        metadata = self._get_empty_metadata()
        if not wheel_urls:
            return metadata

        core_metadata = self._fetch_core_metadata_from_wheel(wheel_urls)
        if not core_metadata:
            return metadata

        license_metadata = self._merge_uv_license_metadata({}, core_metadata)
        metadata['license'] = license_metadata.get('license', '')
        metadata['license_expression'] = license_metadata.get('license_expression', '')
        metadata['classifier'] = license_metadata.get('classifier', [])
        metadata['license_file'] = license_metadata.get('license_file', [])
        return metadata

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
        max_wheel_bytes = MAX_WHEEL_SIZE

        for release in release_urls:
            if not isinstance(release, dict):
                continue

            if release.get('packagetype') != 'bdist_wheel':
                continue

            url_value = release.get('url', '') or ''
            if not isinstance(url_value, str) or not url_value:
                continue

            try:
                # PEP 658: a `<wheel-url>.metadata` sidecar carries just the core metadata,
                # so prefer it to avoid downloading the whole wheel when it is available.
                metadata_text = self._fetch_wheel_metadata_sidecar(url_value)
                if metadata_text is None:
                    metadata_text = self._download_wheel_metadata_text(url_value, max_wheel_bytes)
                if metadata_text is not None:
                    return self._resolve_core_metadata_license_metadata(metadata_text)
            except Exception as e:
                logger.debug(
                    f'Failed to fetch wheel core metadata from {url_value}: {e}'
                )

        return None

    def _fetch_wheel_metadata_sidecar(self, url_value):
        """Try the PEP 658 standalone metadata file for a wheel; return its text, or None.

        Falls back silently (returns None) on any error so the caller can still try
        downloading the full wheel.
        """
        max_metadata_bytes = 1024 * 1024
        try:
            req = urllib.request.Request(
                f'{url_value}.metadata',
                headers={
                    'User-Agent': 'fosslight-dependency',
                    'Accept': 'text/plain, application/octet-stream',
                },
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                raw = response.read(max_metadata_bytes + 1)
            if len(raw) > max_metadata_bytes:
                return None
            return raw.decode('utf-8', 'ignore')
        except Exception as e:
            logger.debug(f'No PEP 658 metadata sidecar for {url_value}: {e}')
            return None

    def _download_wheel_metadata_text(self, url_value, max_wheel_bytes):
        """Download a wheel file and return its dist-info METADATA text.

        Returns None if the wheel is oversized (by Content-Length) or has no METADATA member.
        """
        req = urllib.request.Request(
            url_value,
            headers={
                'User-Agent': 'fosslight-dependency',
                'Accept': 'application/octet-stream',
            },
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            content_length = response.headers.get('Content-Length')
            if content_length is not None:
                try:
                    if int(content_length) > max_wheel_bytes:
                        logger.debug(f'Skipping oversized wheel {url_value} ({content_length} bytes)')
                        return None
                except ValueError:
                    pass

            wheel_path = None
            try:
                wheel_path = self._save_response_to_tempfile(response, max_wheel_bytes)
                return self._read_dist_info_metadata(wheel_path)
            finally:
                if wheel_path and os.path.exists(wheel_path):
                    os.remove(wheel_path)

    def _save_response_to_tempfile(self, response, max_wheel_bytes):
        """Stream a urllib response body into a temp file, enforcing a maximum size.

        `delete=False` is required so the file survives the `with` block for the caller to
        read, so on any failure (including the size-limit check) the partial file is
        removed explicitly before the exception propagates.
        """
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        wheel_path = temp_file.name
        try:
            with temp_file:
                downloaded_bytes = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    downloaded_bytes += len(chunk)
                    if downloaded_bytes > max_wheel_bytes:
                        raise ValueError('wheel exceeds size limit')
                    temp_file.write(chunk)
        except Exception:
            if os.path.exists(wheel_path):
                os.remove(wheel_path)
            raise
        return wheel_path

    def _read_dist_info_metadata(self, wheel_path):
        """Return the dist-info METADATA text from a wheel archive, or None if absent."""
        with zipfile.ZipFile(wheel_path) as wheel_archive:
            for archive_name in wheel_archive.namelist():
                if not archive_name.endswith('.dist-info/METADATA'):
                    continue
                return wheel_archive.read(archive_name).decode('utf-8', 'ignore')
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
        if not selected_packages:
            logger.warning('uv.lock contains no analyzable packages.')
            return False

        # Fetch metadata for each selected package and write the input file. Only
        # registry-sourced packages are looked up on PyPI; a git/url/path source is
        # resolved from its own recorded source and wheel core metadata instead, so a
        # same-named public package is never mistaken for it.
        self.input_package_list_file = []
        installed_packages = []

        for package_name in selected_packages:
            package_info = package_map.get(package_name, {})
            package_version = package_info.get('version', '')
            wheel_urls = package_info.get('wheels', []) or []
            source_info = package_info.get('source', {}) or {}

            if package_name != self.package_name and self._is_uv_lock_registry_source(source_info):
                metadata = self._fetch_pypi_metadata(
                    package_name,
                    package_version,
                    wheel_urls=wheel_urls,
                )
            else:
                # The root project itself (editable '.') has no registry entry either,
                # so its license must come from local wheel metadata only, never PyPI.
                metadata = self._fetch_uv_lock_local_source_metadata(wheel_urls)

            if metadata is None:
                metadata = self._get_empty_metadata()

            direct_url = self._get_uv_lock_direct_url(package_name, source_info)

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
                    # The cover comment ends up in the generated report, which is meant
                    # to be shared. A private index is usually configured with the
                    # credentials in the URL, so mask them here as well as in the log.
                    # The host is what makes this note useful and it is preserved.
                    self.cover_comment += redact_secrets(rf_line)

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

        venv_path = self.venv_tmp_dir

        if self.platform == const.WINDOWS:
            create_venv_cmd = f'{venv_interpreter("python")} -m venv {quote_shell_path(self.venv_tmp_dir)}'
            activate_cmd = os.path.join(self.venv_tmp_dir, "Scripts", "activate.bat")
            cmd_separator = "&&"
        else:
            create_venv_cmd = (f'virtualenv -p {venv_interpreter("python3")} '
                               f'{quote_shell_path(self.venv_tmp_dir)}')
            activate_cmd = ". " + os.path.join(venv_path, "bin", "activate")
            cmd_separator = "&&"

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

        cmd_list = [create_venv_cmd, quote_activate_cmd(activate_cmd), install_cmd,
                    pip_upgrade_cmd, deactivate_cmd]
        ret, err_msg = self._run_venv_setup_command(cmd_list, cmd_separator)

        if (not ret) and (self.platform != const.WINDOWS):
            create_venv_cmd = (f'{venv_interpreter("python3")} -m venv '
                               f'{quote_shell_path(self.venv_tmp_dir)}')
            cmd_list = [create_venv_cmd, quote_activate_cmd(activate_cmd), install_cmd,
                        pip_upgrade_cmd, deactivate_cmd]
            ret, err_msg = self._run_venv_setup_command(cmd_list, cmd_separator)

        if ret:
            logger.info(f"Created the temporary virtualenv({venv_path}).")
        else:
            # err_msg may also come from an exception carrying the command line,
            # which can embed the private index credentials.
            logger.error(f"Failed to create virtualenv: {redact_secrets(err_msg)}")

        return ret

    def _run_venv_setup_command(self, cmd_list, cmd_separator):
        """Run a virtualenv setup command list and return (success, error_message)."""
        cmd = cmd_separator.join(cmd_list)
        try:
            cmd_ret = subprocess.run(cmd, shell=True, stderr=subprocess.PIPE)
            return describe_venv_failure(cmd_ret)
        except Exception as e:
            return False, e

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

        activate_command = quote_activate_cmd(pip_activate_cmd)
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
                                self.total_dep_list.append(self._normalize_package_name(package_name))
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
                oss_init_name = self._normalize_package_name(oss_init_name)
                if oss_init_name not in self.total_dep_list:
                    continue
                oss_item.name = f"{self.package_manager_name}:{oss_init_name}"
                oss_item.version = metadata.get('version', '')

                oss_item.license = self._resolve_installed_package_license(
                    metadata, oss_init_name, oss_item.version
                )

                oss_item.download_location = f"{self.dn_url}{oss_init_name}/{oss_item.version}"
                oss_item.homepage = self._resolve_installed_package_homepage(metadata, oss_init_name)

                dep_item.purl = get_url_to_purl(oss_item.download_location, self.package_manager_name)
                purl_dict[f'{oss_init_name}({oss_item.version})'] = dep_item.purl

                _is_local, local_path_comment = self._apply_direct_url_override(package, oss_item)

                dep_key = f'{oss_init_name}({oss_item.version})'
                if dep_key in self.relation_tree:
                    dep_item.depends_on_raw = self.relation_tree[dep_key]

                oss_item.comment = self._resolve_installed_package_comment(
                    oss_init_name, oss_item.version, local_path_comment
                )

                dep_item.oss_items.append(oss_item)
                self.dep_items.append(dep_item)

        except Exception as ex:
            logger.warning(f"Fail to parse oss information: {oss_init_name}({ex})")
        if self.direct_dep:
            self.dep_items = change_dependson_to_purl(purl_dict, self.dep_items)
        return

    def _resolve_installed_package_license(self, metadata, oss_init_name, version):
        """Resolve license using priority: license_expression > classifier > license > license_file."""
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
                version,
                license_files_meta
            )
            if license_info_list:
                license_info = ','.join(license_info_list)
        license_name = check_UNKNOWN(license_info)
        if license_name:
            license_name = license_name.replace(';', ',')
        return license_name

    def _resolve_installed_package_homepage(self, metadata, oss_init_name):
        """Resolve homepage using priority: project_url 'source' > download_url > project_url 'homepage' > homepage."""
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
        return download_url or homepage_url or f"{self.dn_url}{oss_init_name}"

    def _apply_direct_url_override(self, package, oss_item):
        """Apply direct_url info (local path or explicit URL) to oss_item.

        Returns (is_local, local_path_comment).
        """
        is_local = False
        local_path_comment = ''
        direct_url = package.get('direct_url', {})
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
        return is_local, local_path_comment

    def _resolve_installed_package_comment(self, oss_init_name, version, local_path_comment):
        """Build the comment field: root package/direct/transitive, merged with any local path note."""
        comment = ''
        if oss_init_name == self.package_name:
            comment = 'root package'
        elif self.direct_dep and len(self.direct_dep_list) > 0:
            if f'{oss_init_name}({version})' in self.direct_dep_list:
                comment = 'direct'
            else:
                comment = 'transitive'

        if comment:
            if comment == 'root package' and local_path_comment:
                return f'{comment} / {local_path_comment}'
            return comment
        return local_path_comment

    def get_dependencies(self, dependencies, package):
        package_name = 'package_name'
        deps = 'dependencies'
        installed_ver = 'installed_version'

        pkg_name = self._normalize_package_name(package[package_name])
        pkg_ver = package[installed_ver]
        dependency_list = package[deps]
        dependencies[f"{pkg_name}({pkg_ver})"] = []
        for dependency in dependency_list:
            dep_name = self._normalize_package_name(dependency[package_name])
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
                        package_name = self._normalize_package_name(package['package_name'])
                        if package_name in self.total_dep_list:
                            direct_without_system_package += 1
                    if direct_without_system_package == 1:
                        self.package_name = self._normalize_package_name(json_f[0]['package_name'])
                        root_package = json_f[0]['dependencies']

                for package in root_package:
                    package_name = self._normalize_package_name(package['package_name'])
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
