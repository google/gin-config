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

"""Init file for scikit-learn-specific Gin-Config package."""

# pylint: disable=g-import-not-at-top


# Ensure scikit-learn is importable and its version is sufficiently recent.
# This needs to happen before anything else, since the imports below will try
# to import scikit-learn, too.
def _ensure_sklearn_install():  # pylint: disable=g-statement-before-imports
  """Attempt to import scikit-learn, and ensure its version is sufficient.

  Raises:
    ImportError: If either scikit-learn is not importable or its version is
      inadequate.
  """
  try:
    import sklearn
  except ImportError:
    # Print more informative error message, then reraise.
    print("\n\nFailed to import scikit-learn. Please note that scikit-learn "
          "is not installed by default when you install Gin-Config. This is "
          "so that users can decide whether to install TensorFlow, "
          "GPU-enabled Tensorflow, PyTorch, or scikit-learn. To use "
          "Gin-Config with scikit-learn, please install the most recent "
          "version of scikit-learn, by following instructions at "
          "https://scikit-learn.org/stable/install.html.\n\n")
    raise

  # Update this whenever we need to depend on a newer scikit-learn release.
  required_sklearn_version = "0.19.1"

  import distutils.version

  if (distutils.version.LooseVersion(sklearn.__version__) <
      distutils.version.LooseVersion(required_sklearn_version)):
    raise ImportError(
        "This version of Gin-Config requires TensorFlow "
        "version >= {required}; Detected an installation of version {present}. "
        "Please upgrade scikit-learn to proceed.".format(
            required=required_sklearn_version,
            present=sklearn.__version__))


_ensure_sklearn_install()


# Cleanup symbols to avoid polluting namespace.
import sys as _sys
import .external_configurables as _ext
for symbol in ["_ensure_sklearn_install", "_sys", "_ext"]:
  delattr(_sys.modules[__name__], symbol)

# pylint: enable=g-import-not-at-top
