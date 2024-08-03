#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0
from typing import Optional, Tuple
import igraph as ig
import matplotlib.pyplot as plt


class GraphConvertor:
    def __init__(self, package_list: Optional[list] = None):
        self._verticies = {}
        self._edges = []
        if package_list:
            self.init_list(package_list)

    def init_list(self, package_list: list):
        """
        Initialize package_list to self._verticies and self._edges

        Args:
            package_list (list): List containing package information
        """
        depend_on_package_dict = {}
        for idx, package_info in enumerate(package_list):
            package_name = package_info[0]
            depend_on_packages_str = package_info[-1]
            depend_on_packages = list(map((lambda x: x.strip()), depend_on_packages_str.split(",")))
            self._verticies[package_name] = idx
            depend_on_package_dict[package_name] = depend_on_packages
        else:
            for package_name, depend_on_packages in depend_on_package_dict.items():
                if not package_name:
                    pass
                else:
                    package_idx = self._verticies[package_name]
                    for depend_on_package in depend_on_packages:
                        if not depend_on_package:
                            pass
                        else:
                            depend_on_package_idx = self._verticies[depend_on_package]
                            self._edges.append((package_idx, depend_on_package_idx))

    def save(self, path: str, size: Tuple[(int, int)]):
        g = ig.Graph((len(self._verticies)), (self._edges), directed=True)

        g["title"] = "Dependency Graph"
        g.vs["name"] = list(self._verticies.keys())

        fig, ax = plt.subplots(figsize=(tuple(map((lambda x: x / 100), size))))
        fig.tight_layout()

        ig.plot(
            g,
            target=ax,
            layout="kk",
            vertex_size=15,
            vertex_color=["#FFD2D2"],
            vertex_label=(g.vs["name"]),
            vertex_label_dist=1.5,
            vertex_label_size=7.0,
            edge_width=0.5,
            edge_color=["#FFD2D2"],
            edge_arrow_size=5,
            edge_arrow_width=5,
        )

        fig.savefig(path)
