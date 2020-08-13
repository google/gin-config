#!/usr/bin/env bash
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

# Test with stable ML packages (default): ./run_tests.sh stable
# Test with nightly ML packages: ./run_tests.sh nightly

# Exit if any process returns non-zero status.
set -e

run_tests() {
  # Get arguments.
  local -r python_version="${1:-python3.7}"
  local -r stability="${2:-stable}"
  echo "Testing under ${python_version} with ${stability} ML packages."

  # Create and activate a virtualenv to specify python version and test in
  # isolated environment. Note that we don't actually have to cd into a
  # virtualenv directory to use it; we just need to source bin/activate into the
  # current shell.
  local -r tmp="$(mktemp -d)"
  local -r venv_path="${tmp}/virtualenv/${python_version}"
  virtualenv -p "${python_version}" "${venv_path}"
  source ${venv_path}/bin/activate

  # TensorFlow isn't a regular dependency because there are many different pip
  # packages a user might have installed.
  if [[ "$stability" == "stable" ]] ; then
    local -r extras=tensorflow,torch
  elif [[ $stability == "nightly" ]] ; then
    local -r extras=tf-nightly,pytorch-nightly
  else
    echo "Error: Unknown stability ${stability}, pass either nightly or stable."
    exit 1
  fi

  # Install Gin and dependencies.
  pip install ".[testing,${extras}]"

  # Find the tests.
  local -r test_files=$(find tests -name '*_test.py')

  # Run the tests.
  for test_file in ${test_files}; do
    echo "Running tests in ${test_file}..."
    nosetests "${test_file}"
  done

  # Uninstall Gin (deps remain) to properly test installing from package.
  pip uninstall -y gin-config

  # Test packaging and then installing the Gin package.
  local -r wheel_path="${tmp}/wheel/${python_version}"
  ./pip_pkg.sh ${wheel_path}/

  pip install ${wheel_path}/gin_config*.whl

# Move away from repo directory so "import gin.tf" refers to the installed wheel
# and not to the local filesystem. This just test some basic imports, relying
# on the leftover installations of tensorflow and torch from above.
  pushd $(mktemp -d)
  python -c 'import gin'
  python -c 'import gin.tf'
  python -c 'import gin.torch'
  popd

  # Deactivate virtualenv
  deactivate
}

# Test on Python3.7
run_tests "python3.7" "$1"
# Test on Python3.5
run_tests "python3.5" "$1"
# Test on Python2.7
run_tests "python2.7" "$1"

echo "$(tput setaf 2)All tests passed."
