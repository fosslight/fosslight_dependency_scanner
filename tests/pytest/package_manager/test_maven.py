#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0
import os
import pytest
import subprocess
import openpyxl

DIST_PATH = os.path.join(os.environ.get("TOX_PATH", ""), "dist", "cli.exe")


@pytest.mark.parametrize("input_path, output_path", [
    ("tests/test_maven1/lombok.maven", "tests/result/maven1"),
    ("tests/test_maven2", "tests/result/maven2")
])
@pytest.mark.ubuntu
def test_ubuntu(input_path, output_path):
    command = f"fosslight_dependency -p {input_path} -o {output_path}"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    assert result.returncode == 0, f"Command failed: {command}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    assert any(os.scandir(output_path)), f"Output file does not exist: {output_path}"


@pytest.mark.parametrize("input_path, output_path", [
    (os.path.join("tests", "test_maven2"), os.path.join("tests", "result", "maven2"))
])
@pytest.mark.windows
def test_windows(input_path, output_path):
    command = f"{DIST_PATH} -p {input_path} -o {output_path} -m maven"
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, f"Command failed: {command}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    assert any(os.scandir(output_path)), f"Output file does not exist: {output_path}"


@pytest.mark.ubuntu
def test_custom_repository_url():
    """
    Test that custom repository URLs are collected correctly from non-central repositories.
    Uses Spring Milestone repository as test case.
    """
    import shutil
    import tempfile
    from pathlib import Path
    
    test_dir = "tests/test_maven_custom_repo"
    assert os.path.exists(os.path.join(test_dir, "pom.xml")), f"Test project not found: {test_dir}"
    
    # Clean Maven cache for test packages to force download
    m2_repo = Path.home() / ".m2" / "repository"
    test_packages = [
        m2_repo / "org/springframework/data/spring-data-r2dbc/1.5.0-M1"
    ]
    for pkg_path in test_packages:
        if pkg_path.exists():
            shutil.rmtree(pkg_path)
    
    # Run fosslight_dependency
    with tempfile.TemporaryDirectory() as output_dir:
        command = f"fosslight_dependency -p {test_dir} -o {output_dir}"
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        assert result.returncode == 0, f"Command failed: {command}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        
        # Find output Excel file
        output_files = list(Path(output_dir).glob("fosslight_report_dep_*.xlsx"))
        assert len(output_files) > 0, f"No output file found in {output_dir}"
        
        # Read Excel and check URLs
        wb = openpyxl.load_workbook(output_files[0])
        sheet = wb['DEP_FL_Dependency']
        
        headers = [cell.value for cell in sheet[1]]
        name_idx = headers.index('OSS Name')
        download_idx = headers.index('Download Location')
        
        spring_r2dbc_found = False
        spring_r2dbc_url_correct = False
        
        for row in sheet.iter_rows(min_row=2, values_only=True):
            name = row[name_idx] if name_idx < len(row) else ''
            download_url = row[download_idx] if download_idx < len(row) else ''
            
            # Check spring-data-r2dbc has custom repo URL
            if 'spring-data-r2dbc' in str(name):
                spring_r2dbc_found = True
                if 'repo.spring.io' in str(download_url):
                    spring_r2dbc_url_correct = True
                    break
        
        assert spring_r2dbc_found, "spring-data-r2dbc package not found in output"
        assert spring_r2dbc_url_correct, f"spring-data-r2dbc should have repo.spring.io URL, but got: {download_url}"

