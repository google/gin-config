#!/bin/bash

# Test nightly release: ./test_release.sh nightly
# Test stable release: ./test_release.sh stable

# Exit if any process returns non-zero status.
set -e
# Display the commands being run in logs, which are replicated to sponge.
set -x

if [[ $# -lt 1 ]] ; then
  echo "Usage:"
  echo "test_release [nightly|stable]"
  exit 1
fi

run_tests() {
  echo "run_tests $1 $2"
  TMP=$(mktemp -d)
  # Create and activate a virtualenv to specify python version and test in
  # isolated environment. Note that we don't actually have to cd'ed into a
  # virtualenv directory to use it; we just need to source bin/activate into the
  # current shell.
  VENV_PATH=${TMP}/virtualenv/$1
  virtualenv -p "$1" "${VENV_PATH}"
  source ${VENV_PATH}/bin/activate

  if [[ $1 == "python2.7" ]] ; then
    mv tests/config_py3_test.py tests/config_py3_test.bak
  fi

  # TensorFlow isn't a regular dependency because there are many different pip
  # packages a user might have installed.
  if [[ $2 == "nightly" ]] ; then
    pip install tf-nightly

    # Run the tests
    python setup.py test

    # Install Gin package.
    WHEEL_PATH=${TMP}/wheel/$1
    ./pip_pkg.sh ${WHEEL_PATH}/
  elif [[ $2 == "stable" ]] ; then
    pip install tensorflow

    # Run the tests
    python setup.py test

    # Install Gin package.
    WHEEL_PATH=${TMP}/wheel/$1
    ./pip_pkg.sh ${WHEEL_PATH}/
  else
    echo "Error unknow option only [nightly|stable]"
    exit
  fi

  if [[ $1 == "python2.7" ]] ; then
    mv tests/config_py3_test.bak tests/config_py3_test.py
  fi

  pip install ${WHEEL_PATH}/gin_config*.whl

  # Move away from repo directory so "import gin.tf" refers to the
  # installed wheel and not to the local fs.
  (cd $(mktemp -d) && python -c 'import gin.tf')

  # Deactivate virtualenv
  deactivate
}

# Test on Python3.5
run_tests "python3.5" $1
# Test on Python3.6
run_tests "python3.6" $1
# Test on Python2.7
run_tests "python2.7" $1
