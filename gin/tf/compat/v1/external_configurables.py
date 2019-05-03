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

_prefix = 'tf' if tf.__version__.startswith('1') else 'tf.compat.v1'

# Learning rate decays.

config.external_configurable(
    tf.compat.v1.train.exponential_decay, module='%s.train' % _prefix)
config.external_configurable(
    tf.compat.v1.train.inverse_time_decay, module='%s.train' % _prefix)
config.external_configurable(
    tf.compat.v1.train.natural_exp_decay, module='%s.train' % _prefix)
config.external_configurable(
    tf.compat.v1.train.polynomial_decay, module='%s.train' % _prefix)


@config.configurable(module='%s.train' % _prefix)
@functools.wraps(tf.compat.v1.train.piecewise_constant)
def piecewise_constant(global_step, *args, **kwargs):
  if 'boundaries' in kwargs:
    kwargs['boundaries'] = list(np.int64(kwargs['boundaries']))
  return tf.compat.v1.train.piecewise_constant(global_step, *args, **kwargs)


# Losses.

config.external_configurable(
    tf.compat.v1.losses.absolute_difference, module='%s.losses' % _prefix)
config.external_configurable(
    tf.compat.v1.losses.cosine_distance, module='%s.losses' % _prefix)
config.external_configurable(
    tf.compat.v1.losses.hinge_loss, module='%s.losses' % _prefix)
config.external_configurable(
    tf.compat.v1.losses.huber_loss, module='%s.losses' % _prefix)
config.external_configurable(
    tf.compat.v1.losses.log_loss, module='%s.losses' % _prefix)
config.external_configurable(
    tf.compat.v1.losses.mean_pairwise_squared_error, module='%s.losses'
    % _prefix)
config.external_configurable(
    tf.compat.v1.losses.mean_squared_error, module='%s.losses' % _prefix)
config.external_configurable(
    tf.compat.v1.losses.sigmoid_cross_entropy, module='%s.losses' % _prefix)
config.external_configurable(
    tf.compat.v1.losses.softmax_cross_entropy, module='%s.losses' % _prefix)
config.external_configurable(
    tf.compat.v1.losses.sparse_softmax_cross_entropy, module='%s.losses'
    % _prefix)


# Optimizers.

config.external_configurable(
    tf.compat.v1.train.GradientDescentOptimizer, module='%s.train' % _prefix)
config.external_configurable(
    tf.compat.v1.train.AdadeltaOptimizer, module='%s.train' % _prefix)
config.external_configurable(
    tf.compat.v1.train.AdagradOptimizer, module='%s.train' % _prefix)
config.external_configurable(
    tf.compat.v1.train.AdagradDAOptimizer, module='%s.train' % _prefix)
config.external_configurable(
    tf.compat.v1.train.MomentumOptimizer, module='%s.train' % _prefix)
config.external_configurable(
    tf.compat.v1.train.AdamOptimizer, module='%s.train' % _prefix)
config.external_configurable(
    tf.compat.v1.train.FtrlOptimizer, module='%s.train' % _prefix)
config.external_configurable(
    tf.compat.v1.train.ProximalGradientDescentOptimizer, module='%s.train'
    % _prefix)
config.external_configurable(
    tf.compat.v1.train.ProximalAdagradOptimizer, module='%s.train' % _prefix)
config.external_configurable(
    tf.compat.v1.train.RMSPropOptimizer, module='%s.train' % _prefix)


# Misc
config.external_configurable(
    tf.compat.v1.random.multinomial, '%s.random.multinomial' % _prefix)
