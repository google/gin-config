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

"""Supplies a default set of configurables from core TensorFlow."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import functools

from gin import config

import numpy as np
import tensorflow as tf


# Learning rate decays.

config.external_configurable(tf.train.exponential_decay, module='tf.train')
config.external_configurable(tf.train.inverse_time_decay, module='tf.train')
config.external_configurable(tf.train.natural_exp_decay, module='tf.train')
config.external_configurable(tf.train.polynomial_decay, module='tf.train')


@config.configurable(module='tf.train')
@functools.wraps(tf.train.piecewise_constant)
def piecewise_constant(global_step, *args, **kwargs):
  if 'boundaries' in kwargs:
    kwargs['boundaries'] = list(np.int64(kwargs['boundaries']))
  return tf.train.piecewise_constant(global_step, *args, **kwargs)


# Losses.

config.external_configurable(tf.losses.absolute_difference, module='tf.losses')
config.external_configurable(tf.losses.cosine_distance, module='tf.losses')
config.external_configurable(tf.losses.hinge_loss, module='tf.losses')
config.external_configurable(tf.losses.huber_loss, module='tf.losses')
config.external_configurable(tf.losses.log_loss, module='tf.losses')
config.external_configurable(
    tf.losses.mean_pairwise_squared_error, module='tf.losses')
config.external_configurable(tf.losses.mean_squared_error, module='tf.losses')
config.external_configurable(
    tf.losses.sigmoid_cross_entropy, module='tf.losses')
config.external_configurable(
    tf.losses.softmax_cross_entropy, module='tf.losses')
config.external_configurable(
    tf.losses.sparse_softmax_cross_entropy, module='tf.losses')


# Optimizers.

config.external_configurable(
    tf.train.GradientDescentOptimizer, module='tf.train')
config.external_configurable(tf.train.AdadeltaOptimizer, module='tf.train')
config.external_configurable(tf.train.AdagradOptimizer, module='tf.train')
config.external_configurable(tf.train.AdagradDAOptimizer, module='tf.train')
config.external_configurable(tf.train.MomentumOptimizer, module='tf.train')
config.external_configurable(tf.train.AdamOptimizer, module='tf.train')
config.external_configurable(tf.train.FtrlOptimizer, module='tf.train')
config.external_configurable(
    tf.train.ProximalGradientDescentOptimizer, module='tf.train')
config.external_configurable(
    tf.train.ProximalAdagradOptimizer, module='tf.train')
config.external_configurable(tf.train.RMSPropOptimizer, module='tf.train')


# Activation functions.

config.external_configurable(tf.nn.crelu, 'tf.nn.crelu')
config.external_configurable(tf.nn.dropout, 'tf.nn.dropout')
config.external_configurable(tf.nn.elu, 'tf.nn.elu')
config.external_configurable(tf.nn.leaky_relu, 'tf.nn.leaky_relu')
config.external_configurable(tf.nn.relu, 'tf.nn.relu')
config.external_configurable(tf.nn.relu6, 'tf.nn.relu6')
config.external_configurable(tf.nn.sigmoid, 'tf.nn.sigmoid')
config.external_configurable(tf.nn.softmax, 'tf.nn.softmax')
config.external_configurable(tf.nn.softplus, 'tf.nn.softplus')
config.external_configurable(tf.nn.softsign, 'tf.nn.softsign')
config.external_configurable(tf.nn.tanh, 'tf.nn.tanh')


# Random distributions.

config.external_configurable(tf.random.gamma, 'tf.random.gamma')
config.external_configurable(tf.random.multinomial, 'tf.random.multinomial')
config.external_configurable(tf.random.normal, 'tf.random.normal')
config.external_configurable(tf.random.poisson, 'tf.random.poisson')
config.external_configurable(tf.random.truncated_normal,
                             'tf.random.truncated_normal')
config.external_configurable(tf.random.uniform, 'tf.random.uniform')


# Constants

config.constant('tf.float16', tf.float16)
config.constant('tf.float32', tf.float32)
config.constant('tf.float64', tf.float64)
config.constant('tf.bfloat16', tf.bfloat16)
config.constant('tf.complex64', tf.complex64)
config.constant('tf.complex128', tf.complex128)
config.constant('tf.int8', tf.int8)
config.constant('tf.uint8', tf.uint8)
config.constant('tf.uint16', tf.uint16)
config.constant('tf.int16', tf.int16)
config.constant('tf.int32', tf.int32)
config.constant('tf.int64', tf.int64)
config.constant('tf.bool', tf.bool)
config.constant('tf.string', tf.string)
config.constant('tf.qint8', tf.qint8)
config.constant('tf.quint8', tf.quint8)
config.constant('tf.qint16', tf.qint16)
config.constant('tf.quint16', tf.quint16)
config.constant('tf.qint32', tf.qint32)
config.constant('tf.resource', tf.resource)
config.constant('tf.variant', tf.variant)
