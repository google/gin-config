# coding=utf-8
# Copyright 2018 The Gin-Config Authors.
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

"""Supplies a default set of configurables from tensorflow.compat.v1."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import functools

from gin import config

import numpy as np
import tensorflow as tf
import gin.tf.compat.shared.external_configurables


def _register_callables(package, module, blacklist):
  for k in dir(package):
    if k not in blacklist:
      v = getattr(package, k)
      if callable(v):
        config.external_configurable(v, name=k, module=module)


blacklist = set(('serialize', 'deserialize', 'get'))
for package, module in (
    (tf.losses, 'tf.losses'),
    (tf.metrics, 'tf.metrics'),
    (tf.optimizers, 'tf.optimizers'),
    (tf.keras.callbacks, 'tf.keras.callbacks'),
    (tf.keras.constraints, 'tf.keras.constraints'),
    (tf.keras.layers, 'tf.keras.layers'),
    ):
  _register_callables(package, module, blacklist)

# clean up namespace
del package, module, blacklist
