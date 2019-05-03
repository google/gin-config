from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import tensorflow as tf
from gin import config

# Register TF file reader for Gin's parse_config_file.
config.register_file_reader(tf.io.gfile.GFile, tf.io.gfile.exists)
