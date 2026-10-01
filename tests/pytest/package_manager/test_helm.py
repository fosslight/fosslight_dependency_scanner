#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0
import os
import pytest
import subprocess
from tests.pytest.assert_report import assert_dep_sheet_has_min_rows
from fosslight_dependency.package_manager.Helm import Helm


@pytest.mark.parametrize("input_path, output_path, extra_args", [
    ("tests/test_helm", "tests/result/helm", "-m helm")
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
@pytest.mark.windows
def test_parse_dependency_charts_with_absolute_manifest_path(tmp_path, monkeypatch):
    # The analyzer passes the manifest as an absolute path. Each dependency chart must
    # still be read from tmp_charts/<dep>/Chart.yaml, not replaced by the root chart.
    (tmp_path / "Chart.yaml").write_text(
        "name: root\nversion: 0.1.0\ndependencies:\n- name: dep-a\n- name: dep-b\n", encoding="utf8")
    for name, version in (("dep-a", "1.0.0"), ("dep-b", "2.0.0")):
        chart_dir = tmp_path / "tmp_charts" / name
        chart_dir.mkdir(parents=True)
        (chart_dir / "Chart.yaml").write_text(f"name: {name}\nversion: {version}\n", encoding="utf8")
    monkeypatch.chdir(tmp_path)

    helm = Helm(str(tmp_path), str(tmp_path))
    helm.parse_oss_information(str(tmp_path / "Chart.yaml"))

    found = sorted(f"{item.oss_items[0].name} {item.oss_items[0].version}" for item in helm.dep_items)
    assert found == ["helm:dep-a 1.0.0", "helm:dep-b 2.0.0"]
