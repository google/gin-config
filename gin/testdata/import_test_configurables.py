# coding=utf-8
# Copyright 2020 The Gin-Config Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Provides a simple configurable for testing Gin imports."""

# Just using the config module, so we don't run Gin's __init__.py (which alters
# the set of a available file readers and makes the test take ~15x longer due to
# a dependency on TensorFlow).
from gin import config


@config.configurable
def identity(param=None):
  return param


@config.configurable
def my_other_func(a, b, c):
  return a, b, c
