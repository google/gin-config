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

"""Init file for TensorFlow-specific Gin-Config package."""

# pylint: disable=g-import-not-at-top


# Ensure TensorFlow is importable and its version is sufficiently recent. This
# needs to happen before anything else, since the imports below will try to
# import tensorflow, too.
def _ensure_tf_install():  # pylint: disable=g-statement-before-imports
  """Attempt to import tensorflow, and ensure its version is sufficient.

  Raises:
    ImportError: if either tensorflow is not importable or its version is
    inadequate.
  """
  try:
    import tensorflow as tf
  except ImportError:
    # Print more informative error message, then reraise.
    print("\n\nFailed to import TensorFlow. Please note that TensorFlow is not "
          "installed by default when you install Gin-Config. This is so that "
          "users can decide whether to install the GPU-enabled TensorFlow "
          "package. To use Gin-Config, please install the most recent version "
          "of TensorFlow, by following instructions at "
          "https://tensorflow.org/install.\n\n")
    raise

  # Update this whenever we need to depend on a newer TensorFlow release.
  required_tensorflow_version = "1.12.0"

  import distutils.version

  if (distutils.version.LooseVersion(tf.__version__) <
      distutils.version.LooseVersion(required_tensorflow_version)):
    raise ImportError(
        "This version of Gin-Config requires TensorFlow "
        "version >= {required}; Detected an installation of version {present}. "
        "Please upgrade TensorFlow to proceed.".format(
            required=required_tensorflow_version,
            present=tf.__version__))


_ensure_tf_install()


# Cleanup symbols to avoid polluting namespace.
import sys as _sys
for symbol in ["_ensure_tf_install", "_sys"]:
  delattr(_sys.modules[__name__], symbol)


# pylint: disable=unused-import
from gin.tf.utils import GinConfigSaverHook

# pylint: enable=g-import-not-at-top
