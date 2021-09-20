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

"""Supplies a default set of configurables from core TensorFlow."""

import functools

from gin import config

import numpy as np
import tensorflow as tf

# Learning rate decays.

config.external_configurable(
    tf.compat.v1.train.exponential_decay, module='tf.train')
config.external_configurable(
    tf.compat.v1.train.inverse_time_decay, module='tf.train')
config.external_configurable(
    tf.compat.v1.train.natural_exp_decay, module='tf.train')
config.external_configurable(
    tf.compat.v1.train.polynomial_decay, module='tf.train')


@config.configurable(module='tf.train')
@functools.wraps(tf.compat.v1.train.piecewise_constant)
def piecewise_constant(global_step, *args, **kwargs):
  if 'boundaries' in kwargs:
    kwargs['boundaries'] = list(np.int64(kwargs['boundaries']))
  return tf.compat.v1.train.piecewise_constant(global_step, *args, **kwargs)


# Losses.

config.external_configurable(
    tf.compat.v1.losses.absolute_difference, module='tf.losses')
config.external_configurable(
    tf.compat.v1.losses.cosine_distance, module='tf.losses')
config.external_configurable(tf.compat.v1.losses.hinge_loss, module='tf.losses')
config.external_configurable(tf.compat.v1.losses.huber_loss, module='tf.losses')
config.external_configurable(tf.compat.v1.losses.log_loss, module='tf.losses')
config.external_configurable(
    tf.compat.v1.losses.mean_pairwise_squared_error, module='tf.losses')
config.external_configurable(
    tf.compat.v1.losses.mean_squared_error, module='tf.losses')
config.external_configurable(
    tf.compat.v1.losses.sigmoid_cross_entropy, module='tf.losses')
config.external_configurable(
    tf.compat.v1.losses.softmax_cross_entropy, module='tf.losses')
config.external_configurable(
    tf.compat.v1.losses.sparse_softmax_cross_entropy, module='tf.losses')

# Maths.

config.external_configurable(
    tf.math.squared_difference, module='tf.math')

# Optimizers.

config.external_configurable(
    tf.compat.v1.train.GradientDescentOptimizer, module='tf.train')
config.external_configurable(
    tf.compat.v1.train.AdadeltaOptimizer, module='tf.train')
config.external_configurable(
    tf.compat.v1.train.AdagradOptimizer, module='tf.train')
config.external_configurable(
    tf.compat.v1.train.AdagradDAOptimizer, module='tf.train')
config.external_configurable(
    tf.compat.v1.train.MomentumOptimizer, module='tf.train')
config.external_configurable(
    tf.compat.v1.train.AdamOptimizer, module='tf.train')
config.external_configurable(
    tf.compat.v1.train.FtrlOptimizer, module='tf.train')
config.external_configurable(
    tf.compat.v1.train.ProximalGradientDescentOptimizer, module='tf.train')
config.external_configurable(
    tf.compat.v1.train.ProximalAdagradOptimizer, module='tf.train')
config.external_configurable(
    tf.compat.v1.train.RMSPropOptimizer, module='tf.train')

# Keras optimizers.

config.external_configurable(
    tf.keras.optimizers.Adadelta, module='tf.keras.optimizers')
config.external_configurable(
    tf.keras.optimizers.Adagrad, module='tf.keras.optimizers')
config.external_configurable(
    tf.keras.optimizers.Adam, module='tf.keras.optimizers')
config.external_configurable(
    tf.keras.optimizers.Adamax, module='tf.keras.optimizers')
config.external_configurable(
    tf.keras.optimizers.Ftrl, module='tf.keras.optimizers')
config.external_configurable(
    tf.keras.optimizers.Nadam, module='tf.keras.optimizers')
config.external_configurable(
    tf.keras.optimizers.RMSprop, module='tf.keras.optimizers')
config.external_configurable(
    tf.keras.optimizers.SGD, module='tf.keras.optimizers')


# LR schedules
def _register_schedule(module):
  config.external_configurable(module, module='tf.keras.optimizers.schedules')
_register_schedule(tf.keras.optimizers.schedules.ExponentialDecay)
_register_schedule(tf.keras.optimizers.schedules.PiecewiseConstantDecay)
_register_schedule(tf.keras.optimizers.schedules.PolynomialDecay)
_register_schedule(tf.keras.optimizers.schedules.InverseTimeDecay)
_register_schedule(tf.keras.optimizers.schedules.CosineDecay)
_register_schedule(tf.keras.optimizers.schedules.CosineDecayRestarts)

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
config.external_configurable(tf.identity, 'tf.identity')

# Random distributions.

config.external_configurable(tf.random.gamma, 'tf.random.gamma')
config.external_configurable(tf.compat.v1.random.multinomial,
                             'tf.random.multinomial')
config.external_configurable(tf.random.normal, 'tf.random.normal')
config.external_configurable(tf.random.poisson, 'tf.random.poisson')
config.external_configurable(tf.random.truncated_normal,
                             'tf.random.truncated_normal')
config.external_configurable(tf.random.uniform, 'tf.random.uniform')
config.external_configurable(tf.random.stateless_categorical,
                             'tf.random.stateless_categorical')
config.external_configurable(tf.random.stateless_normal,
                             'tf.random.stateless_normal')
config.external_configurable(tf.random.stateless_truncated_normal,
                             'tf.random.stateless_truncated_normal')
config.external_configurable(tf.random.stateless_uniform,
                             'tf.random.stateless_uniform')

# Distribution strategies.
config.external_configurable(tf.compat.v2.distribute.MirroredStrategy,
                             module='tf.compat.v2.distribute')

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
