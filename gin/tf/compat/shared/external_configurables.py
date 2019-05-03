
"""Supplies a default set of configurables from core TensorFlow."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from gin import config

import numpy as np
import tensorflow as tf
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
config.external_configurable(tf.random.normal, 'tf.random.normal')
config.external_configurable(tf.random.poisson, 'tf.random.poisson')
config.external_configurable(tf.random.truncated_normal,
                             'tf.random.truncated_normal')

# 1.12 doesn't have tf.random.categorical
config.external_configurable(
    tf.random.categorical if hasattr(tf.random, 'categorical')
        else tf.random.multinomial, 'tf.random.categorical')
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
