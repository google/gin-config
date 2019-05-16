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

"""Init file for PyTorch-specific Gin-Config package."""

# pylint: disable=g-import-not-at-top


# Ensure PyTorch is importable and its version is sufficiently recent. This
# needs to happen before anything else, since the imports below will try to
# import torch, too.
import sys as _sys


def _ensure_torch_install():  # pylint: disable=g-statement-before-imports
    """Attempt to import toch, and ensure its version is sufficient.

    Raises:
      ImportError: if either torch is not importable or its version is
      inadequate.
    """
    try:
        import torch
    except ImportError:
        # Print more informative error message, then reraise.
        print("\n\nFailed to import PyTorch.\n\n")
        raise

    # Update this whenever we need to depend on a newer PyTorch release.
    required_torch_version = "1.1.0"

    import distutils.version

    if (distutils.version.LooseVersion(torch.__version__) <
            distutils.version.LooseVersion(required_torch_version)):
        raise ImportError(
            "This version of Gin-Config requires PyTorch "
            "version >= {required}; Detected an installation of version {present}. "
            "Please upgrade TensorFlow to proceed.".format(
                required=required_torch_version,
                present=torch.__version__))


_ensure_torch_install()


# Cleanup symbols to avoid polluting namespace.
# pylint: enable=g-import-not-at-top
for symbol in ["_ensure_torch_install", "_sys"]:
    delattr(_sys.modules[__name__], symbol)
