#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2024 LG Electronics Inc.
# SPDX-License-Identifier: Apache-2.0

import logging
from fosslight_util.constant import LOGGER_NAME
from fosslight_util.oss_item import FileItem

_logger = logging.getLogger(LOGGER_NAME)


class DependencyItem(FileItem):
    def __init__(self):
        super().__init__("")

        self._depends_on_raw = []  # name(version) format
        self._depends_on = []  # purl format
        self.purl = ""

    def __del__(self):
        pass

    @property
    def depends_on(self):
        return self._depends_on

    @depends_on.setter
    def depends_on(self, value):
        if not value:
            self._depends_on = []
        else:
            if not isinstance(value, list):
                value = value.split(",")
            self._depends_on.extend(value)
            self._depends_on = [item.strip() for item in self._depends_on]
            self._depends_on = list(set(self._depends_on))

    @property
    def depends_on_raw(self):
        return self._depends_on_raw

    @depends_on_raw.setter
    def depends_on_raw(self, value):
        if not value:
            self._depends_on_raw = []
        else:
            if not isinstance(value, list):
                value = value.split(",")
            self._depends_on_raw.extend(value)
            self._depends_on_raw = [item.strip() for item in self._depends_on_raw]
            self._depends_on_raw = list(set(self._depends_on_raw))

    def get_print_array(self):
        items = []
        for oss in self.oss_items:
            exclude = "Exclude" if self.exclude or oss.exclude else ""
            lic = ",".join(oss.license)
            depends_on = ",".join(self.depends_on) if len(self.depends_on) > 0 else ""

            oss_item = [self.purl, oss.name, oss.version, lic, oss.download_location, oss.homepage,
                        oss.copyright, exclude, oss.comment, depends_on]
            items.append(oss_item)

        return items

    def get_print_json(self):
        items = []
        for oss in self.oss_items:
            json_item = {}
            json_item["name"] = oss.name
            json_item["version"] = oss.version

            if self.purl != "":
                json_item["package url"] = self.purl
            if len(oss.license) > 0:
                json_item["license"] = oss.license
            if oss.download_location != "":
                json_item["download location"] = oss.download_location
            if oss.homepage != "":
                json_item["homepage"] = oss.homepage
            if oss.copyright != "":
                json_item["copyright text"] = oss.copyright
            if self.exclude or oss.exclude:
                json_item["exclude"] = True
            if oss.comment != "":
                json_item["comment"] = oss.comment
            if len(self.depends_on) > 0:
                json_item["depends on"] = self.depends_on

            items.append(json_item)

        return items


def change_dependson_to_purl(purl_dict, dep_items):
    for dep_item in dep_items:
        try:
            dep_item.depends_on = list(filter(None, map(lambda x: purl_dict.get(x, ''), dep_item.depends_on_raw)))

        except Exception as e:
            _logger.warning(f'Fail to change depend_on to purl:{e}')
    return dep_items
