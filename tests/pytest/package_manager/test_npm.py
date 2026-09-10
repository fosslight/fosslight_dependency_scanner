#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0
import json
import os
import subprocess
from unittest.mock import patch

import pytest

from fosslight_dependency.package_manager.Npm import Npm
from tests.pytest.assert_report import assert_dep_sheet_has_min_rows


@pytest.mark.parametrize("input_path, output_path, extra_args", [
    ("tests/test_npm1", "tests/result/npm1", ""),
    ("tests/test_npm2", "tests/result/npm2", "-m npm")
])
@pytest.mark.ubuntu
def test_ubuntu(input_path, output_path, extra_args):
    command = f"fosslight_dependency -p {input_path} -o {output_path} {extra_args}"
    result = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert result.returncode == 0, f"Command failed: {command}\nstderr: {result.stderr}"
    assert any(os.scandir(output_path)), f"Output file does not exist: {output_path}"
    assert_dep_sheet_has_min_rows(output_path)


@pytest.mark.ubuntu
def test_parse_oss_information_without_repository_key(tmp_path):
    """license-checker may omit repository for malformed package.json repository objects."""
    license_json = {
        "music-metadata@10.9.1": {
            "licenses": "MIT",
            "name": "music-metadata",
            "version": "10.9.1",
            "path": str(tmp_path),
            "licenseText": "",
            "copyright": "",
            "url": "",
        }
    }
    input_file = tmp_path / "tmp_npm_license_output.json"
    input_file.write_text(json.dumps(license_json), encoding="utf-8")

    with patch.object(Npm, "_check_network_available", return_value=False):
        npm = Npm(str(tmp_path), str(tmp_path))
        npm._network_available = False
        npm.parse_oss_information(str(input_file))

    assert len(npm.dep_items) == 1
    oss = npm.dep_items[0].oss_items[0]
    assert oss.name == "npm:music-metadata"
    assert oss.homepage == "https://www.npmjs.com/package/music-metadata"
    assert oss.download_location == "https://www.npmjs.com/package/music-metadata/v/10.9.1"
