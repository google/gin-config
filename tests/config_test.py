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

import abc
import collections
import enum
import functools
import inspect
import io
import logging
import os
import pickle
import threading

from absl.testing import absltest

from gin import config


_TEST_CONFIG_STR = """
import gin.testdata.import_test_configurables as alias
# Make sure we only get one copy of the import in the output.
from gin.testdata import import_test_configurables as alias

configurable1.kwarg1 = \\
  'a super duper extra double very wordy string that is just plain long'
configurable1.kwarg3 = @configurable2

configurable2.non_kwarg = 'ferret == domesticated polecat'

ConfigurableClass:
  kwarg1 = 'statler'
  kwarg2 = 'waldorf'

ConfigurableSubclass:
  kwarg1 = 'waldorf'
  kwarg3 = 'ferret'

test/scopes/ConfigurableClass:
  kwarg2 = 'beaker'

var_arg_fn:
  non_kwarg2 = {
    'long': [
      'nested', 'structure', ('that', 'will', 'span'),
      'more', ('than', 1), 'line',
    ]
  }
  any_name_is_ok = [%THE_ANSWER, %super/sweet, %pen_names]
  float_value = 2.718
  dict_value = {'success': True}

RegisteredClassWithRegisteredMethods:
  param_a = 'a'
  param_b = 'b'

RegisteredClassWithRegisteredMethods.registered_method1.arg = 3.1415

pass_through.value = @RegisteredClassWithRegisteredMethods()

super/sweet = 'lugduname'
pen_names = ['Pablo Neruda', 'Voltaire', 'Snoop Lion']
a.woolly.sheep.dolly.kwarg = 0
"""

_EXPECTED_OPERATIVE_CONFIG_STR = """
from gin.testdata import import_test_configurables as alias

# Macros:
# ==============================================================================
pen_names = ['Pablo Neruda', 'Voltaire', 'Snoop Lion']
super/sweet = 'lugduname'

# Parameters for configurable1:
# ==============================================================================
configurable1.kwarg1 = \\
    'a super duper extra double very wordy string that is just plain long'
configurable1.kwarg2 = None
configurable1.kwarg3 = @configurable2

# Parameters for configurable2:
# ==============================================================================
configurable2.non_kwarg = 'ferret == domesticated polecat'

# Parameters for ConfigurableClass:
# ==============================================================================
ConfigurableClass.kwarg1 = 'statler'
ConfigurableClass.kwarg2 = 'waldorf'

# Parameters for test/scopes/ConfigurableClass:
# ==============================================================================
test/scopes/ConfigurableClass.kwarg1 = 'statler'
test/scopes/ConfigurableClass.kwarg2 = 'beaker'

# Parameters for ConfigurableSubclass:
# ==============================================================================
ConfigurableSubclass.kwarg1 = 'waldorf'
ConfigurableSubclass.kwarg2 = None
ConfigurableSubclass.kwarg3 = 'ferret'

# Parameters for woolly.sheep.dolly:
# ==============================================================================
woolly.sheep.dolly.kwarg = 0

# Parameters for no_arg_fn:
# ==============================================================================
# None.

# Parameters for pass_through:
# ==============================================================================
pass_through.value = @RegisteredClassWithRegisteredMethods()

# Parameters for RegisteredClassWithRegisteredMethods:
# ==============================================================================
RegisteredClassWithRegisteredMethods.param_a = 'a'
RegisteredClassWithRegisteredMethods.param_b = 'b'

# Parameters for RegisteredClassWithRegisteredMethods.registered_method1:
# ==============================================================================
RegisteredClassWithRegisteredMethods.registered_method1.arg = 3.1415

# Parameters for var_arg_fn:
# ==============================================================================
var_arg_fn.any_name_is_ok = [%THE_ANSWER, %super/sweet, %pen_names]
var_arg_fn.dict_value = {'success': True}
var_arg_fn.float_value = 2.718
var_arg_fn.non_kwarg2 = \\
    {'long': ['nested',
              'structure',
              ('that', 'will', 'span'),
              'more',
              ('than', 1),
              'line']}
"""

_EXPECTED_CONFIG_STR = """
from gin.testdata import import_test_configurables as alias

# Macros:
# ==============================================================================
pen_names = ['Pablo Neruda', 'Voltaire', 'Snoop Lion']
super/sweet = 'lugduname'

# Parameters for configurable1:
# ==============================================================================
configurable1.kwarg1 = \\
    'a super duper extra double very wordy string that is just plain long'
configurable1.kwarg3 = @configurable2

# Parameters for configurable2:
# ==============================================================================
configurable2.non_kwarg = 'ferret == domesticated polecat'

# Parameters for ConfigurableClass:
# ==============================================================================
ConfigurableClass.kwarg1 = 'statler'
ConfigurableClass.kwarg2 = 'waldorf'

# Parameters for test/scopes/ConfigurableClass:
# ==============================================================================
test/scopes/ConfigurableClass.kwarg2 = 'beaker'

# Parameters for ConfigurableSubclass:
# ==============================================================================
ConfigurableSubclass.kwarg1 = 'waldorf'
ConfigurableSubclass.kwarg3 = 'ferret'

# Parameters for woolly.sheep.dolly:
# ==============================================================================
woolly.sheep.dolly.kwarg = 0

# Parameters for pass_through:
# ==============================================================================
pass_through.value = @RegisteredClassWithRegisteredMethods()

# Parameters for RegisteredClassWithRegisteredMethods:
# ==============================================================================
RegisteredClassWithRegisteredMethods.param_a = 'a'
RegisteredClassWithRegisteredMethods.param_b = 'b'

# Parameters for RegisteredClassWithRegisteredMethods.registered_method1:
# ==============================================================================
RegisteredClassWithRegisteredMethods.registered_method1.arg = 3.1415

# Parameters for var_arg_fn:
# ==============================================================================
var_arg_fn.any_name_is_ok = [%THE_ANSWER, %super/sweet, %pen_names]
var_arg_fn.dict_value = {'success': True}
var_arg_fn.float_value = 2.718
var_arg_fn.non_kwarg2 = \\
    {'long': ['nested',
              'structure',
              ('that', 'will', 'span'),
              'more',
              ('than', 1),
              'line']}
"""

_EXPECTED_CONFIG_STR_WITH_PROVENANCE = """
from gin.testdata import import_test_configurables as alias

# Macros:
# ==============================================================================
# Set in test_config.ioreader:43:
pen_names = ['Pablo Neruda', 'Voltaire', 'Snoop Lion']
# Set in test_config.ioreader:42:
super/sweet = 'lugduname'

# Parameters for configurable1:
# ==============================================================================
# Set in test_config.ioreader:6:
configurable1.kwarg1 = \\
    'a super duper extra double very wordy string that is just plain long'
# Set in test_config.ioreader:8:
configurable1.kwarg3 = @configurable2

# Parameters for configurable2:
# ==============================================================================
# Set in test_config.ioreader:10:
configurable2.non_kwarg = 'ferret == domesticated polecat'

# Parameters for ConfigurableClass:
# ==============================================================================
# Set in test_config.ioreader:13:
ConfigurableClass.kwarg1 = 'statler'
# Set in test_config.ioreader:14:
ConfigurableClass.kwarg2 = 'waldorf'

# Parameters for test/scopes/ConfigurableClass:
# ==============================================================================
# Set in test_config.ioreader:21:
test/scopes/ConfigurableClass.kwarg2 = 'beaker'

# Parameters for ConfigurableSubclass:
# ==============================================================================
# Set in test_config.ioreader:17:
ConfigurableSubclass.kwarg1 = 'waldorf'
# Set in test_config.ioreader:18:
ConfigurableSubclass.kwarg3 = 'ferret'

# Parameters for woolly.sheep.dolly:
# ==============================================================================
# Set in test_config.ioreader:44:
woolly.sheep.dolly.kwarg = 0

# Parameters for pass_through:
# ==============================================================================
# Set in test_config.ioreader:40:
pass_through.value = @RegisteredClassWithRegisteredMethods()

# Parameters for RegisteredClassWithRegisteredMethods:
# ==============================================================================
# Set in test_config.ioreader:35:
RegisteredClassWithRegisteredMethods.param_a = 'a'
# Set in test_config.ioreader:36:
RegisteredClassWithRegisteredMethods.param_b = 'b'

# Parameters for RegisteredClassWithRegisteredMethods.registered_method1:
# ==============================================================================
# Set in test_config.ioreader:38:
RegisteredClassWithRegisteredMethods.registered_method1.arg = 3.1415

# Parameters for var_arg_fn:
# ==============================================================================
# Set in test_config.ioreader:30:
var_arg_fn.any_name_is_ok = [%THE_ANSWER, %super/sweet, %pen_names]
# Set in test_config.ioreader:32:
var_arg_fn.dict_value = {'success': True}
# Set in test_config.ioreader:31:
var_arg_fn.float_value = 2.718
# Set in test_config.ioreader:24:
var_arg_fn.non_kwarg2 = \\
    {'long': ['nested',
              'structure',
              ('that', 'will', 'span'),
              'more',
              ('than', 1),
              'line']}
"""

_TEST_DYNAMIC_REGISTRATION_CONFIG_STR = """
from __gin__ import dynamic_registration

include '{}/gin/testdata/dynamic_registration_config_str_test.gin'

import gin.testdata.import_test_configurables as alias

alias.identity.param = 'param'

alias.my_other_func:
  a = 1
  b = 2
  c = @scope/alias.identity
"""

_EXPECTED_DYNAMIC_REGISTRATION_CONFIG_STR = """
from __gin__ import dynamic_registration
from gin.testdata import dynamic_registration_config_str_test as alias
import gin.testdata.import_test_configurables as alias2

# Parameters for alias.Class:
# ==============================================================================
alias.Class.a = 1
alias.Class.b = 2

# Parameters for alias.Class.method:
# ==============================================================================
alias.Class.method.arg = 'method_arg'

# Parameters for alias.function:
# ==============================================================================
alias.function.arg = 'arg'

# Parameters for alias2.identity:
# ==============================================================================
alias2.identity.param = 'param'

# Parameters for alias2.my_other_func:
# ==============================================================================
alias2.my_other_func.a = 1
alias2.my_other_func.b = 2
alias2.my_other_func.c = @scope/alias2.identity
"""


def call_operative_config_str_configurables():
  fn1('mustelid')
  configurable2(config.REQUIRED, kwarg1='I am supplied explicitly.')
  ConfigurableClass()
  ConfigurableSubclass()
  with config.config_scope('test'):
    with config.config_scope('scopes'):
      ConfigurableClass()
  var_arg_fn('non_kwarg1_value', config.REQUIRED)
  instance = pass_through(config.REQUIRED)
  instance.registered_method1()
  no_arg_fn()
  clone2()


@config.configurable('configurable1')
def fn1(non_kwarg, kwarg1=None, kwarg2=None, kwarg3=None):
  return non_kwarg, kwarg1, kwarg2, kwarg3


@config.configurable
def configurable2(non_kwarg, kwarg1=None):
  return non_kwarg, kwarg1


@config.configurable(allowlist=['allowlisted'])
def allowlisted_configurable(allowlisted=None, other=None):
  return allowlisted, other


@config.configurable(denylist=['denylisted'])
def denylisted_configurable(denylisted=None, other=None):
  return denylisted, other


@config.configurable
def required_args(arg1, arg2, arg3, kwarg1=4, kwarg2=5, kwarg3=6):
  return arg1, arg2, arg3, kwarg1, kwarg2, kwarg3


@config.configurable
def required_with_vargs(arg1, arg2, arg3, *args, **kwargs):
  return arg1, arg2, arg3, args, kwargs


@config.configurable
def required_with_vkwargs(arg1,
                          arg2,
                          arg3,
                          kwarg1=4,
                          kwarg2=5,
                          kwarg3=6,
                          **kwargs):
  return arg1, arg2, arg3, kwarg1, kwarg2, kwarg3, kwargs


@config.configurable
def fn_with_kw_only_args(arg1, *, kwarg1=None):
  return arg1, kwarg1


@config.configurable
def fn_with_kw_only_required_arg(arg1, *, kwarg1=config.REQUIRED):
  return arg1, kwarg1


@config.configurable
def no_arg_fn():
  pass


@config.configurable
def var_arg_fn(non_kwarg1, non_kwarg2, *args, **kwargs):
  all_non_kwargs = [non_kwarg1, non_kwarg2] + list(args)
  return all_non_kwargs + [kwargs[key] for key in sorted(kwargs)]


@config.configurable('dolly', module='__main__')
def clone0(kwarg=None):
  return kwarg


@config.configurable('dolly', module='a.furry.sheep')
def clone1(kwarg=None):
  return kwarg


@config.configurable('dolly', module='a.woolly.sheep')
def clone2(kwarg=None):
  return kwarg


@config.configurable('a.fuzzy.sheep.dolly')
def clone3(kwarg=None):
  return kwarg


@config.configurable('sheep.dolly', module='a.hairy')
def clone4(kwarg=None):
  return kwarg


@config.configurable
def new_object():
  return object()


@config.configurable
def required_as_kwarg_default(positional_arg, required_kwarg=config.REQUIRED):
  return positional_arg, required_kwarg


@config.configurable
class ConfigurableClass:
  """A configurable class."""

  def __init__(self, kwarg1=None, kwarg2=None):
    self.kwarg1 = kwarg1
    self.kwarg2 = kwarg2


@config.configurable
class ConfigurableClassWithNew(object):
  """A configurable class with __new__."""

  def __new__(cls, kwarg1=None, kwarg2=None, return_none=False):
    del kwarg2
    if return_none:  # This will test __new__ and __init__ separation.
      return None
    instance = super(ConfigurableClassWithNew, cls).__new__(cls)
    instance.kwarg1 = kwarg1
    return instance

  def __init__(self, kwarg1=None, kwarg2=None, return_none=False):
    del return_none
    self.kwarg1 = kwarg1
    self.kwarg2 = kwarg2


class MetaWithPostNewHook(type):

  def __call__(cls, *args, post_new_hook=None, **kwargs):
    instance = cls.__new__(cls, *args, **kwargs)
    if post_new_hook is not None:  # This will allow to inspect post-new state.
      post_new_hook(instance)
    instance.__init__(*args, **kwargs)
    return instance


@config.configurable
class ConfigurableClassWithMetaAndNew(object, metaclass=MetaWithPostNewHook):
  """A configurable class with metaclass and __new__."""

  def __new__(cls, kwarg1=None, kwarg2=None, return_none=False):
    del kwarg2
    if return_none:  # This will test __new__ and __init__ separation.
      return None
    instance = super(ConfigurableClassWithMetaAndNew, cls).__new__(cls)
    instance.kwarg1 = kwarg1
    return instance

  def __init__(self, kwarg1=None, kwarg2=None, return_none=False):
    del return_none
    self.kwarg1 = kwarg1
    self.kwarg2 = kwarg2


@config.configurable
class ConfigurableClassWithMeta(metaclass=MetaWithPostNewHook):
  """A configurable class with metaclass."""

  def __init__(self, kwarg1=None, kwarg2=None):
    self.kwarg1 = kwarg1
    self.kwarg2 = kwarg2


@config.configurable
class FaultyConfigurableClassWithMeta(metaclass=MetaWithPostNewHook):
  """A configurable class with metaclass."""

  class FaultyError(AssertionError):
    pass

  def __init__(self, kwarg1=None, kwarg2=None):
    raise FaultyConfigurableClassWithMeta.FaultyError('Intentional error.')


@config.configurable
class ConfigurableSubclass(ConfigurableClass):
  """A subclass of a configurable class."""

  def __init__(self, kwarg1=None, kwarg2=None, kwarg3=None):
    super(ConfigurableSubclass, self).__init__(kwarg1, kwarg2)
    self.kwarg3 = kwarg3


NamedTuple = collections.namedtuple('ConfigurableNamedTuple',
                                    ['field1', 'field2'])


@config.configurable
class ConfigurableNamedTuple(NamedTuple):
  pass


@config.register
class RegisteredExternalNamedTuple(NamedTuple):
  pass


@config.configurable
def create_named_tuple(named_tuple, *args):
  return named_tuple(*args)


configurable_external_named_tuple = config.external_configurable(
    NamedTuple, 'ExternalConfigurableNamedTuple')


@config.register
class ObjectSubclassWithoutInit:
  """A class that subclasses object but doesn't define its own __init__.

  While there's nothing to configure in this class, it may still be desirable to
  instantiate such a class from within Gin and bind it to something else.
  """

  @config.register
  def method(self, arg1='default'):
    return arg1


class ExternalClass:
  """A class we'll pretend was defined somewhere else."""

  def __init__(self, kwarg1=None, kwarg2=None):
    self.kwarg1 = kwarg1
    self.kwarg2 = kwarg2

configurable_external_class = config.external_configurable(
    ExternalClass, 'ExternalConfigurable')
config.external_configurable(ExternalClass, 'module.ExternalConfigurable2')


@config.configurable
class ConfigurableExternalSubclass(configurable_external_class):
  """Subclassing an external configurable object.

  This is a configurable subclass (of the configurable subclass implicitly
  created by external_configurable) of the ExternalClass class.
  """

  def __init__(self, kwarg1=None, kwarg2=None, kwarg3=None):
    super(ConfigurableExternalSubclass, self).__init__(
        kwarg1=kwarg1, kwarg2=kwarg2)
    self.kwarg3 = kwarg3


class AbstractConfigurable(metaclass=abc.ABCMeta):

  def __init__(self, kwarg1=None):
    self.kwarg1 = kwarg1

  @abc.abstractmethod
  def implement_me(self):
    pass


@config.configurable
class AbstractConfigurableSubclass(AbstractConfigurable):

  def __init__(self, kwarg1=None, kwarg2=None):
    super(AbstractConfigurableSubclass, self).__init__(kwarg1=kwarg1)
    self.kwarg2 = kwarg2

  @config.configurable
  def implement_me(self, method_arg='arglebargle'):
    return method_arg


class ExternalAbstractConfigurableSubclass(AbstractConfigurable):

  def implement_me(self):
    pass

config.external_configurable(ExternalAbstractConfigurableSubclass)


class ExternalConfigurableClassWithMetaAndNew(metaclass=MetaWithPostNewHook):
  """A configurable class with metaclass and __new__."""

  def __new__(cls, kwarg1=None, kwarg2=None, return_none=False):
    del kwarg2
    if return_none:  # This will test __new__ and __init__ separation.
      return None
    instance = super(ExternalConfigurableClassWithMetaAndNew, cls).__new__(cls)
    instance.kwarg1 = kwarg1
    return instance

  def __init__(self, kwarg1=None, kwarg2=None, return_none=False):
    del return_none
    self.kwarg1 = kwarg1
    self.kwarg2 = kwarg2


external_configurable_class_with_meta_and_new = config.external_configurable(
    ExternalConfigurableClassWithMetaAndNew)


@config.configurable
def pass_through(value):
  return value


@config.register(module='custom')
def not_a_method():
  pass


def unregistered_function(arg):
  return arg


@config.register
class RegisteredClassWithRegisteredMethods:

  def __init__(self, param_a, param_b):
    self.param_a = param_a
    self.param_b = param_b

  not_a_method = not_a_method

  def unregistered_method(self, arg):
    return arg

  @config.register
  def registered_method1(self, arg):
    return arg

  @config.register
  def registered_method2(self, arg):
    return arg


class BaseClassWithMethods:

  def base_method(self, arg):
    return arg


class DynamicallyRegisteredClassWithMethods(BaseClassWithMethods):

  def __init__(self, param):
    self.param = param

  def method1(self, arg):
    return arg

  def method2(self, arg):
    return arg


@config.register(module='custom.module')
class RegisteredClassWithCustomModule:

  @config.register
  def registered_method(self, arg):
    return arg


class ConfigTest(absltest.TestCase):

  def tearDown(self):
    config.clear_config(clear_constants=True)
    super(ConfigTest, self).tearDown()

  def testConfigurable(self):
    config.bind_parameter('configurable1.kwarg1', 'value1')
    config.bind_parameter('configurable1.kwarg2', 'value2')

    self.assertEqual(fn1('value0'), ('value0', 'value1', 'value2', None))

  def testInvalidNameOrModule(self):
    with self.assertRaisesRegex(ValueError, 'invalid.$'):
      config.configurable('0ops')(lambda _: None)

    with self.assertRaisesRegex(ValueError, 'invalid.$'):
      config.configurable('')(lambda _: None)

    with self.assertRaisesRegex(ValueError, 'Module .* invalid'):
      config.configurable('ok', module='not.0k')(lambda _: None)

    with self.assertRaisesRegex(ValueError, 'Module .* invalid'):
      config.configurable('fine', module='')(lambda _: None)

  def testParseConfigFromFilelike(self):
    config_str = u"""
       configurable1.kwarg1 = 'stringval'
       configurable1.kwarg2 = 0
       configurable1.kwarg3 = [0, 1, 'hello']
    """
    string_io = io.StringIO(config_str)
    config.parse_config(string_io)
    self.assertEqual(fn1('value0'), ('value0', 'stringval', 0, [0, 1, 'hello']))

  def testParseConfigFromSingleString(self):
    config_str = """
       configurable1.kwarg1 = 'stringval'
       configurable1.kwarg2 = 0
       configurable1.kwarg3 = [0, 1, 'hello']
    """
    config.parse_config(config_str)
    self.assertEqual(fn1('value0'), ('value0', 'stringval', 0, [0, 1, 'hello']))

  def testParseConfigFromList(self):
    config_str = [
        'configurable1.kwarg1 = "stringval"', 'configurable1.kwarg2 = 0',
        'configurable1.kwarg3 = [0, 1, "hello"]'
    ]
    config.parse_config(config_str)
    self.assertEqual(fn1('value0'), ('value0', 'stringval', 0, [0, 1, 'hello']))

  def testParseConfigImportsAndIncludes(self):
    config_str = """
      import gin.testdata.import_test_configurables
      include '{}'

      identity.param = 'success'
      ConfigurableClass.kwarg1 = @identity()
      ConfigurableClass.kwarg2 = @my_other_func()
    """
    include_path = os.path.join(
        absltest.get_default_test_srcdir(),
        'gin/testdata/my_other_func.gin')
    config.parse_config(config_str.format(include_path))
    self.assertEqual(ConfigurableClass().kwarg1, 'success')
    self.assertEqual(ConfigurableClass().kwarg2, (-2.9, 9.3, 'Oh, Dear.'))

    with self.assertRaisesRegex(ImportError, 'No module'):
      config.parse_config('import nonexistent.module')

    with self.assertRaises(IOError):
      config.parse_config("include 'nonexistent/file'")

  def testInvalidIncludeError(self):
    config_file = os.path.join(
        absltest.get_default_test_srcdir(),
        'gin/testdata/invalid_include.gin')
    err_msg_regex = ('Unable to open file: not/a/valid/file.gin. '
                     'Searched config paths:')
    with self.assertRaisesRegex(IOError, err_msg_regex):
      config.parse_config_file(config_file)

  def testDynamicRegistrationImportAs(self):
    config_str = """
      from __gin__ import dynamic_registration

      import gin.testdata.dynamic_registration as dr

      dr.Class.a = 1
      dr.function.arg = 2
      dr.Class.b = @dr.function()
    """
    config.parse_config(config_str)
    bindings = config.get_bindings('gin.testdata.dynamic_registration.Class')
    self.assertEqual(bindings, {'a': 1, 'b': 2})

  def testDynamicRegistrationFromImport(self):
    config_str = """
      from __gin__ import dynamic_registration

      from gin.testdata import dynamic_registration

      dynamic_registration.Class.a = 1
      dynamic_registration.function.arg = 2
      dynamic_registration.Class.b = @dynamic_registration.function()
    """
    config.parse_config(config_str)
    bindings = config.get_bindings('gin.testdata.dynamic_registration.Class')
    self.assertEqual(bindings, {'a': 1, 'b': 2})

  def testDynamicRegistrationFromImportAs(self):
    config_str = """
      from __gin__ import dynamic_registration

      from gin.testdata import dynamic_registration as dr

      dr.Class.a = 1
      dr.function.arg = 2
      dr.Class.b = @dr.function()
    """
    config.parse_config(config_str)
    bindings = config.get_bindings('gin.testdata.dynamic_registration.Class')
    self.assertEqual(bindings, {'a': 1, 'b': 2})

  def testDynamicRegistrationMacro(self):
    config_str = """
      from __gin__ import dynamic_registration

      from gin.testdata import dynamic_registration

      MACRO_VALUE = 1

      dynamic_registration.Class.a = %MACRO_VALUE
      dynamic_registration.function.arg = 2
      dynamic_registration.Class.b = @dynamic_registration.function()
    """
    config.parse_config(config_str)
    bindings = config.get_bindings('gin.testdata.dynamic_registration.Class')
    self.assertEqual(bindings, {'a': 1, 'b': 2})

  def testDynamicRegistrationImportMain(self):
    config_str = """
      from __gin__ import dynamic_registration

      import __main__  # __main__ is this file (config_test.py).

      from gin.testdata import dynamic_registration

      dynamic_registration.function.arg = 10
      __main__.pass_through.value = @dynamic_registration.function()
    """
    config.parse_config(config_str)
    self.assertEqual(pass_through(config.REQUIRED), 10)

  def testDynamicRegistrationImportMainAndRegister(self):
    config_str = """
      from __gin__ import dynamic_registration

      import __main__ as config_test  # __main__ is this file (config_test.py).

      config_test.unregistered_function.arg = 'test'
    """
    config.parse_config(config_str)
    configurable_fn = config.get_configurable(unregistered_function)
    self.assertEqual(configurable_fn(config.REQUIRED), 'test')

  def testDynamicRegistrationLateEnablingError(self):
    config_str = """
      import __main__  # __main__ is this file (config_test.py).

      from gin.testdata import dynamic_registration

      from __gin__ import dynamic_registration
    """
    expected_msg = (
        'Dynamic registration should be enabled before any other modules are '
        "imported.\n\nAlready imported: \\['import __main__', 'from "
        "gin\\.testdata import dynamic_registration'\\].")
    with self.assertRaisesRegex(SyntaxError, expected_msg):
      config.parse_config(config_str)

  def testExplicitParametersOverrideGin(self):
    config_str = """
      configurable1.non_kwarg = 'non_kwarg'
      configurable1.kwarg1 = 'kwarg1'
      configurable1.kwarg3 = 'kwarg3'
    """
    config.parse_config(config_str)
    # pylint: disable=no-value-for-parameter
    non_kwarg, kwarg1, kwarg2, kwarg3 = fn1(kwarg1='ahoy', kwarg3='matey!')
    # pylint: enable=no-value-for-parameter
    self.assertEqual(non_kwarg, 'non_kwarg')
    self.assertEqual(kwarg1, 'ahoy')
    self.assertIsNone(kwarg2)
    self.assertEqual(kwarg3, 'matey!')

  def testBindingBlockUnknownConfigurableError(self):
    config_str = """
      scope/WhatAmI:
        arg1 = 3
        arg2 = 5
    """
    expected_msg = (r"No configurable matching 'WhatAmI'\.\n"
                    r'  In bindings string line 2\n'
                    r'          scope/WhatAmI:')
    with self.assertRaisesRegex(ValueError, expected_msg):
      config.parse_config(config_str)

  def testUnknownReference(self):
    config_str = """
      ConfigurableClass.kwarg1 = 'okie dokie'
      unknown.kwarg1 = 'kwarg1'
    """
    expected_err_msg = ("No configurable matching 'unknown'.\n"
                        "  In bindings string line 3")
    with self.assertRaisesRegex(ValueError, expected_err_msg):
      config.parse_config(config_str)

  def testSkipUnknown(self):
    config_str = """
      ConfigurableClass.kwarg1 = 'okie dokie'
      unknown.kwarg1 = 'kwarg1'
    """
    with self.assertRaises(ValueError):
      config.parse_config(config_str)
    expected_err_msg = "No configurable matching 'unknown'"
    with self.assertRaisesRegex(ValueError, expected_err_msg):
      config.parse_config(config_str, skip_unknown=['moose'])
    config.parse_config(config_str, skip_unknown=['unknown'])
    config.parse_config(config_str, skip_unknown=True)
    self.assertEqual(ConfigurableClass().kwarg1, 'okie dokie')

  def testSkipUnknownImports(self):
    config_str = """
      import not.a.real.module
    """
    with self.assertRaises(ImportError):
      config.parse_config(config_str)
    with absltest.mock.patch.object(logging, 'info') as mock_log:
      config.parse_config(config_str, skip_unknown=True)
      found_log = False
      for log in mock_log.call_args_list:
        log = log[0][0] % tuple(log[0][1:])
        if 'not.a.real.module' in log:
          if 'Traceback' in log:
            self.fail('Traceback included for non-nested unknown import log.')
          else:
            found_log = True
            break
      self.assertTrue(
          found_log, msg='Did not log import error.')

  def testSkipUnknownNestedImport(self):
    config_str = """
      import gin.testdata.invalid_import
    """
    with self.assertRaises(ImportError):
      config.parse_config(config_str)
    with absltest.mock.patch.object(logging, 'info') as mock_log:
      config.parse_config(config_str, skip_unknown=True)
      found_log = False
      for args, _ in mock_log.call_args_list:
        log = args[0] % tuple(args[1:])
        if 'gin.testdata.invalid_import' in log and 'Traceback' in log:
          found_log = True
          break
      self.assertTrue(
          found_log, msg='Did not log traceback of nested import error.')

  def testSkipUnknownReference(self):
    config_str = """
      ConfigurableClass.kwarg1 = [1, @UnknownReference()]
      ConfigurableClass.kwarg2 = 12345
      configurable2.kwarg1 = 'bog snorkelling'
      unknown.kwarg1 = @UnknownReference
    """
    expected_err_msg = (
        r"No configurable matching reference '@UnknownReference\(\)'")
    with self.assertRaisesRegex(ValueError, expected_err_msg):
      config.parse_config(config_str)
    with self.assertRaisesRegex(ValueError, expected_err_msg):
      config.parse_config(config_str, skip_unknown=['moose'])

    config.parse_config(
        config_str, skip_unknown=['UnknownReference', 'unknown'])
    _, kwarg1_val = configurable2(None)
    self.assertEqual(kwarg1_val, 'bog snorkelling')

    config.parse_config(config_str, skip_unknown=True)
    _, kwarg1_val = configurable2(None)
    self.assertEqual(kwarg1_val, 'bog snorkelling')

    with self.assertRaisesRegex(ValueError, expected_err_msg):
      ConfigurableClass()
    addl_msg = ".* In binding for 'ConfigurableClass.kwarg1'"
    with self.assertRaisesRegex(ValueError, expected_err_msg + addl_msg):
      config.finalize()

    config.bind_parameter('ConfigurableClass.kwarg1', 'valid')
    instance = ConfigurableClass()
    config.finalize()
    self.assertEqual(instance.kwarg1, 'valid')
    self.assertEqual(instance.kwarg2, 12345)

  def testParameterValidation(self):
    config.parse_config('var_arg_fn.anything_is_fine = 0')

    err_regexp = ".* doesn't have a parameter.*\n  In bindings string line 1"
    with self.assertRaisesRegex(ValueError, err_regexp):
      config.parse_config('configurable2.not_a_parameter = 0')
    with self.assertRaisesRegex(ValueError, err_regexp):
      config.parse_config('ConfigurableClass.not_a_parameter = 0')

    config.external_configurable(lambda arg: arg, 'lamdba1', denylist=['arg'])
    config.external_configurable(lambda arg: arg, 'lambda2', allowlist=['arg'])

    err_regexp = '.* not a parameter of'
    with self.assertRaisesRegex(ValueError, err_regexp):
      config.external_configurable(
          lambda arg: arg, 'lambda3', denylist=['nonexistent'])
    with self.assertRaisesRegex(ValueError, err_regexp):
      config.external_configurable(
          lambda arg: arg, 'lambda4', allowlist=['nonexistent'])

  def testMissingPositionalParameter(self):
    config.parse_config("""
       required_args.arg2 = None
       required_args.kwarg2 = None
    """)
    err_regexp = (r".*\n  No values supplied .*: \['arg3'\]\n"
                  r"  Gin had values bound for: \['arg2', 'kwarg2'\]\n"
                  r"  Caller supplied values for: \['arg1', 'kwarg1'\]")
    with self.assertRaisesRegex(TypeError, err_regexp):
      required_args(None, kwarg1=None)  # pylint: disable=no-value-for-parameter

  def testMissingPositionalParameterVarargs(self):
    config.parse_config("""
       required_with_vargs.arg2 = None
       required_with_vargs.kwarg2 = None
    """)
    err_regexp = (r".*\n  No values supplied .*: \['arg3'\]\n"
                  r"  Gin had values bound for: \['arg2', 'kwarg2'\]\n"
                  r"  Caller supplied values for: \['arg1', 'kwarg1'\]")
    with self.assertRaisesRegex(TypeError, err_regexp):
      # pylint: disable=no-value-for-parameter
      required_with_vargs(None, kwarg1=None)

  def testSubclassParametersOverrideSuperclass(self):
    config_str = """
      ConfigurableClass.kwarg1 = 'base_kwarg1'
      ConfigurableClass.kwarg2 = 'base_kwarg2'

      ConfigurableSubclass.kwarg1 = 'sub_kwarg1'
      ConfigurableSubclass.kwarg2 = 'sub_kwarg2'
      ConfigurableSubclass.kwarg3 = 'sub_kwarg3'
    """
    config.parse_config(config_str)

    base = ConfigurableClass()
    self.assertEqual(base.kwarg1, 'base_kwarg1')
    self.assertEqual(base.kwarg2, 'base_kwarg2')

    sub = ConfigurableSubclass()
    self.assertEqual(sub.kwarg1, 'sub_kwarg1')
    self.assertEqual(sub.kwarg2, 'sub_kwarg2')
    self.assertEqual(sub.kwarg3, 'sub_kwarg3')

  def testPositionalArgumentsOverrideConfig(self):
    config_str = """
      configurable2.non_kwarg = 'non_kwarg'
    """
    config.parse_config(config_str)

    # Our Gin config works.
    non_kwarg, _ = configurable2()  # pylint: disable=no-value-for-parameter
    self.assertEqual(non_kwarg, 'non_kwarg')

    # Gin gets overridden by an explicitly supplied positional argument.
    non_kwarg, _ = configurable2('overridden')
    self.assertEqual(non_kwarg, 'overridden')

    # But we haven't broken a legitimate error.
    with self.assertRaises(TypeError):
      # pylint: disable=redundant-keyword-arg
      configurable2('positional', non_kwarg='duplicate')
      # pylint: enable=redundant-keyword-arg

  def testParseConfigurableReferences(self):
    config_str = """
      configurable1:
        kwarg1 = 'stringval'
        kwarg2 = @scoped/configurable2()
        kwarg3 = @configurable2
      scoped/configurable2.non_kwarg = 'wombat'
      configurable2.kwarg1 = {'success': True}
    """
    config.parse_config(config_str)
    value0, value1, value2, value3 = fn1('value0')
    self.assertEqual((value0, value1), ('value0', 'stringval'))
    self.assertEqual(value2, ('wombat', {'success': True}))
    self.assertTrue(callable(value3))
    self.assertEqual(value3('muppeteer'), ('muppeteer', {'success': True}))

  def testConfigurableClass(self):
    config_str = """
      ConfigurableClass.kwarg1 = 'statler'
      ConfigurableClass.kwarg2 = 'waldorf'
    """
    config.parse_config(config_str)
    instance = ConfigurableClass()
    self.assertEqual(instance.kwarg1, 'statler')
    self.assertEqual(instance.kwarg2, 'waldorf')
    self.assertEqual(instance.__dict__,
                     pickle.loads(pickle.dumps(instance)).__dict__)

  def testConfigurableClassWithNew(self):
    config_str = """
      ConfigurableClassWithNew.kwarg1 = 'statler'
      ConfigurableClassWithNew.kwarg2 = 'waldorf'
    """
    config.parse_config(config_str)
    instance = ConfigurableClassWithNew()
    self.assertEqual(instance.kwarg1, 'statler')
    self.assertEqual(instance.kwarg2, 'waldorf')
    self.assertEqual(instance.__dict__,
                     pickle.loads(pickle.dumps(instance)).__dict__)

  def testConfigurableClassWithNewCanReturnOtherType(self):
    config_str = """
      ConfigurableClassWithNew.kwarg1 = 'statler'
      ConfigurableClassWithNew.kwarg2 = 'waldorf'
      ConfigurableClassWithNew.return_none = True
    """
    config.parse_config(config_str)
    instance = ConfigurableClassWithNew()
    self.assertIsNotNone(instance)

    config_str = """
      ConfigurableClassWithNew.kwarg1 = 'statler'
      ConfigurableClassWithNew.kwarg2 = 'waldorf'
    """
    config.parse_config(config_str)
    instance = ConfigurableClassWithNew(return_none=True)
    self.assertIsNone(instance)

  def testConfigurableClassWithMetaAndNew(self):
    config_str = """
      ConfigurableClassWithMetaAndNew.kwarg1 = 'statler'
      ConfigurableClassWithMetaAndNew.kwarg2 = 'waldorf'
    """
    config.parse_config(config_str)
    instance = ConfigurableClassWithMetaAndNew()
    self.assertEqual(instance.kwarg1, 'statler')
    self.assertEqual(instance.kwarg2, 'waldorf')
    self.assertEqual(instance.__dict__,
                     pickle.loads(pickle.dumps(instance)).__dict__)

  def testConfigurableClassWithMetaAndNewPostNewHook(self):
    config_str = """
      ConfigurableClassWithMetaAndNew.kwarg1 = 'statler'
      ConfigurableClassWithMetaAndNew.kwarg2 = 'waldorf'
    """
    config.parse_config(config_str)

    class ValidateHookError(AssertionError):
      pass

    def fail(_):
      raise ValidateHookError('Expected exception.')

    with self.assertRaises(ValidateHookError):
      ConfigurableClassWithMetaAndNew(post_new_hook=fail)  # pylint: disable=unexpected-keyword-arg

  def testConfigurableClassWithMetaAndNewSeparatesNewAndInit(self):
    config_str = """
      ConfigurableClassWithMetaAndNew.kwarg1 = 'statler'
      ConfigurableClassWithMetaAndNew.kwarg2 = 'waldorf'
    """
    config.parse_config(config_str)

    def calls_new_with_no_injection_when_init_present(instance):
      self.assertIsNone(instance.kwarg1)
      self.assertFalse(hasattr(instance, 'kwarg2'))

    instance = ConfigurableClassWithMetaAndNew(  # pylint: disable=unexpected-keyword-arg
        post_new_hook=calls_new_with_no_injection_when_init_present)
    self.assertEqual(instance.kwarg1, 'statler')
    self.assertEqual(instance.kwarg2, 'waldorf')

  def testConfigurableClassWithMeta(self):
    config_str = """
      ConfigurableClassWithMeta.kwarg1 = 'statler'
      ConfigurableClassWithMeta.kwarg2 = 'waldorf'
    """
    config.parse_config(config_str)
    instance = ConfigurableClassWithMeta()
    self.assertEqual(instance.kwarg1, 'statler')
    self.assertEqual(instance.kwarg2, 'waldorf')
    self.assertEqual(instance.__dict__,
                     pickle.loads(pickle.dumps(instance)).__dict__)

  def testConfigurableClassWithMetaPostNewHook(self):
    config_str = """
      ConfigurableClassWithMeta.kwarg1 = 'statler'
      ConfigurableClassWithMeta.kwarg2 = 'waldorf'
    """
    config.parse_config(config_str)

    class ValidateHookError(AssertionError):
      pass

    def fail(_):
      raise ValidateHookError('Expected exception.')

    with self.assertRaises(ValidateHookError):
      ConfigurableClassWithMeta(post_new_hook=fail)  # pylint: disable=unexpected-keyword-arg

  def testConfigurableClassWithMetaSeparatesNewAndInit(self):
    config_str = """
      ConfigurableClassWithMeta.kwarg1 = 'statler'
      ConfigurableClassWithMeta.kwarg2 = 'waldorf'
    """
    config.parse_config(config_str)

    def no_attrs(instance):
      self.assertFalse(hasattr(instance, 'kwarg1'))
      self.assertFalse(hasattr(instance, 'kwarg2'))

    instance = ConfigurableClassWithMeta(post_new_hook=no_attrs)  # pylint: disable=unexpected-keyword-arg
    self.assertEqual(instance.kwarg1, 'statler')
    self.assertEqual(instance.kwarg2, 'waldorf')

  def testFaultyConfigurableClassWithMeta(self):
    config_str = """
      FaultyConfigurableClassWithMeta.kwarg1 = 'statler'
      FaultyConfigurableClassWithMeta.kwarg2 = 'waldorf'
    """
    config.parse_config(config_str)

    with self.assertRaises(FaultyConfigurableClassWithMeta.FaultyError):
      FaultyConfigurableClassWithMeta()

  def testExternalConfigurableClassWithMetaAndNewPostNewHook(self):
    config_str = """
      ExternalConfigurableClassWithMetaAndNew.kwarg1 = 'statler'
      ExternalConfigurableClassWithMetaAndNew.kwarg2 = 'waldorf'
    """
    config.parse_config(config_str)

    class ValidateHookError(AssertionError):
      pass

    def fail(_):
      raise ValidateHookError('Expected exception.')

    with self.assertRaises(ValidateHookError):
      external_configurable_class_with_meta_and_new(post_new_hook=fail)

  def testExternalConfigurableClassWithMetaAndNew(self):
    config_str = """
      ExternalConfigurableClassWithMetaAndNew.kwarg1 = 'statler'
      ExternalConfigurableClassWithMetaAndNew.kwarg2 = 'waldorf'
    """
    config.parse_config(config_str)
    instance = external_configurable_class_with_meta_and_new()
    self.assertEqual(instance.kwarg1, 'statler')
    self.assertEqual(instance.kwarg2, 'waldorf')
    self.assertEqual(instance.__dict__,
                     pickle.loads(pickle.dumps(instance)).__dict__)

  def testExternalConfigurableClassWithMetaAndNewSeparatesNewAndInit(self):
    config_str = """
      ExternalConfigurableClassWithMetaAndNew.kwarg1 = 'statler'
      ExternalConfigurableClassWithMetaAndNew.kwarg2 = 'waldorf'
    """
    config.parse_config(config_str)

    # Due to the strategy of overriding the metaclass's __call__ method for
    # types registered with external_configurable, __new__ will be called with
    # injected values. The __new__ implementation for this test class only sets
    # the value for kwarg1, while kwarg2 is set in __init__.
    def calls_new_with_no_injection_when_init_present(instance):
      self.assertEqual(instance.kwarg1, 'statler')
      self.assertFalse(hasattr(instance, 'kwarg2'))

    instance = external_configurable_class_with_meta_and_new(
        post_new_hook=calls_new_with_no_injection_when_init_present)

    self.assertEqual(instance.kwarg1, 'statler')
    self.assertEqual(instance.kwarg2, 'waldorf')

  def testConfigurableReferenceClassIdentityIsPreserved(self):
    config_str = """
      ConfigurableClass.kwarg1 = 'hi'
      configurable2.non_kwarg = @ConfigurableClass
      configurable2.kwarg1 = @ConfigurableClass()
    """
    config.parse_config(config_str)
    # pylint: disable=no-value-for-parameter
    reference, instance = configurable2()
    # pylint: enable=no-value-for-parameter
    self.assertTrue(inspect.isclass(reference))
    self.assertTrue(issubclass(reference, ConfigurableClass))
    self.assertIsInstance(instance, ConfigurableClass)

  def testConfigurableSubclass(self):
    config_str = """
      configurable2.non_kwarg = @ConfigurableSubclass
      configurable2.kwarg1 = @ConfigurableClass

      ConfigurableClass.kwarg1 = 'one'
      ConfigurableSubclass.kwarg1 = 'some'
      ConfigurableSubclass.kwarg3 = 'thing'
    """
    config.parse_config(config_str)
    # pylint: disable=no-value-for-parameter
    sub_cls_ref, super_cls_ref = configurable2()
    # pylint: enable=no-value-for-parameter
    self.assertTrue(inspect.isclass(super_cls_ref))
    self.assertTrue(inspect.isclass(sub_cls_ref))

    sub_instance = sub_cls_ref()
    super_instance = super_cls_ref()

    self.assertTrue(issubclass(sub_cls_ref, ConfigurableClass))
    self.assertIsInstance(sub_instance, ConfigurableClass)
    self.assertIsInstance(sub_instance, type(super_instance))

    self.assertEqual(super_instance.kwarg1, 'one')
    self.assertIsNone(super_instance.kwarg2)
    self.assertEqual(sub_instance.kwarg1, 'some')
    self.assertIsNone(sub_instance.kwarg2)
    self.assertEqual(sub_instance.kwarg3, 'thing')
    self.assertEqual(sub_instance.__dict__,
                     pickle.loads(pickle.dumps(sub_instance)).__dict__)

  def testConfigurableMethod(self):
    config_str = """
      configurable2.non_kwarg = @scoped/AbstractConfigurableSubclass()
      implement_me.method_arg = 'bananaphone'
    """
    config.parse_config(config_str)
    instance, _ = configurable2()  # pylint: disable=no-value-for-parameter
    self.assertEqual(instance.implement_me(), 'bananaphone')

  def testExternalConfigurableClass(self):
    config_str = """
      ConfigurableClass.kwarg1 = @ExternalConfigurable
      ConfigurableClass.kwarg2 = @module.ExternalConfigurable2
      ExternalConfigurable.kwarg1 = 'statler'
      ExternalConfigurable.kwarg2 = 'waldorf'
    """
    config.parse_config(config_str)
    configurable_class = ConfigurableClass()
    cls = configurable_class.kwarg1
    self.assertTrue(issubclass(cls, ExternalClass))
    self.assertEqual(cls.__module__, ExternalClass.__module__)
    self.assertEqual(cls.__name__, ExternalClass.__name__)
    self.assertEqual(cls.__doc__, ExternalClass.__doc__)
    self.assertTrue(issubclass(configurable_class.kwarg2, ExternalClass))

    instance = cls()
    self.assertIsInstance(instance, ExternalClass)
    self.assertEqual(instance.kwarg1, 'statler')  # pytype: disable=attribute-error  # kwargs-checking
    self.assertEqual(instance.kwarg2, 'waldorf')  # pytype: disable=attribute-error  # kwargs-checking

    config_str = """
      ConfigurableClass.kwarg1 = @ExternalConfigurable
      ExternalConfigurable.kwarg1 = 'statler'
      ExternalConfigurable.kwarg2 = 'waldorf'
    """
    config.parse_config(config_str)
    configurable_class = ConfigurableClass()
    instance = configurable_class.kwarg1()
    self.assertEqual(instance.__dict__,
                     pickle.loads(pickle.dumps(instance)).__dict__)

  def testAbstractExternalConfigurableClass(self):
    config_str = """
      configurable2.non_kwarg = @ExternalAbstractConfigurableSubclass()
      configurable2.kwarg1 = @ConfigurableClass()
      ExternalAbstractConfigurableSubclass.kwarg1 = 'fish'
    """
    config.parse_config(config_str)
    # pylint: disable=no-value-for-parameter
    instance, not_instance = configurable2()
    # pylint: enable=no-value-for-parameter
    self.assertIsInstance(instance, AbstractConfigurable)
    self.assertNotIsInstance(not_instance, AbstractConfigurable)

  def testImplicitlyScopedConfigurableClass(self):
    config_str = """
      configurable2.non_kwarg = @scope1/ConfigurableClass
      configurable2.kwarg1 = @scope2/ConfigurableClass
      scope1/ConfigurableClass:
        kwarg1 = 'scope1arg1'
        kwarg2 = 'scope1arg2'
      scope2/ConfigurableClass:
        kwarg1 = 'scope2arg1'
        kwarg2 = 'scope2arg2'
    """
    config.parse_config(config_str)
    # pylint: disable=no-value-for-parameter
    scope1_cls, scope2_cls = configurable2()
    # pylint: enable=no-value-for-parameter
    self.assertEqual(scope1_cls.__module__, ConfigurableClass.__module__)
    self.assertEqual(scope1_cls.__name__, ConfigurableClass.__name__)
    self.assertEqual(scope1_cls.__doc__, ConfigurableClass.__doc__)
    scope1_instance = scope1_cls()
    scope2_instance = scope2_cls()
    self.assertEqual(scope1_instance.kwarg1, 'scope1arg1')
    self.assertEqual(scope1_instance.kwarg2, 'scope1arg2')
    self.assertEqual(scope2_instance.kwarg1, 'scope2arg1')
    self.assertEqual(scope2_instance.kwarg2, 'scope2arg2')

  def testImplicitlyScopedExternalConfigurableAndSubclass(self):
    config_str = """
      configurable2.non_kwarg = @scope1/ExternalConfigurable
      configurable2.kwarg1 = @scope2/ConfigurableExternalSubclass
      scope1/ExternalConfigurable.kwarg1 = 'one'
      scope2/ConfigurableExternalSubclass.kwarg2 = 'two'
      scope2/ConfigurableExternalSubclass.kwarg3 = 'three'
    """
    config.parse_config(config_str)
    # pylint: disable=no-value-for-parameter
    super_cls, sub_cls = configurable2()
    # pylint: enable=no-value-for-parameter
    self.assertTrue(issubclass(super_cls, ExternalClass))
    self.assertTrue(issubclass(sub_cls, ExternalClass))
    self.assertTrue(issubclass(sub_cls, ConfigurableExternalSubclass))

    super_instance, sub_instance = super_cls(), sub_cls()
    self.assertIsInstance(super_instance, ExternalClass)
    self.assertIsInstance(sub_instance, ConfigurableExternalSubclass)
    self.assertIsInstance(sub_instance, ExternalClass)

    self.assertEqual(super_instance.kwarg1, 'one')  # pytype: disable=attribute-error  # kwargs-checking
    self.assertIsNone(super_instance.kwarg2)  # pytype: disable=attribute-error  # kwargs-checking

    self.assertIsNone(sub_instance.kwarg1)  # pytype: disable=attribute-error  # kwargs-checking
    self.assertEqual(sub_instance.kwarg2, 'two')  # pytype: disable=attribute-error  # kwargs-checking
    self.assertEqual(sub_instance.kwarg3, 'three')  # pytype: disable=attribute-error  # kwargs-checking

  def testAbstractConfigurableSubclass(self):
    config_str = """
      configurable2.non_kwarg = @scoped/AbstractConfigurableSubclass()
      scoped/AbstractConfigurableSubclass.kwarg1 = 'kwarg1'
      scoped/AbstractConfigurableSubclass.kwarg2 = 'kwarg2'
    """
    config.parse_config(config_str)
    with config.config_scope('scoped'):
      instance = AbstractConfigurableSubclass()
    self.assertEqual(instance.kwarg1, 'kwarg1')
    self.assertEqual(instance.kwarg2, 'kwarg2')
    self.assertEqual(instance.implement_me(method_arg='gouda'), 'gouda')

    # Also try when creating from a configurable reference.
    instance, _ = configurable2()  # pylint: disable=no-value-for-parameter
    self.assertEqual(instance.kwarg1, 'kwarg1')
    self.assertEqual(instance.kwarg2, 'kwarg2')
    self.assertEqual(instance.implement_me(method_arg='havarti'), 'havarti')

  def testConfigurableObjectSubclassWithoutInit(self):
    config_str = """
      ConfigurableClass.kwarg1 = @ObjectSubclassWithoutInit()
      ObjectSubclassWithoutInit.method.arg1 = 'valuesaurus'
    """
    config.parse_config(config_str)
    subclass_instance = ConfigurableClass().kwarg1
    self.assertIsInstance(subclass_instance, ObjectSubclassWithoutInit)
    self.assertEqual(subclass_instance.method(), 'valuesaurus')

  def testExternalConfigurableMethodWrapper(self):
    obj_maker = config.external_configurable(object.__call__, 'obj_call')
    self.assertIsInstance(obj_maker(), object)

  def testExternalConfigurableBuiltin(self):
    wrapped_sum = config.external_configurable(sum)
    self.assertEqual(wrapped_sum([1, 2, 3]), 6)

  def testConfigurableNamedTuple(self):
    config_str = """
      ConfigurableNamedTuple.field1 = 'field1'
      ConfigurableNamedTuple.field2 = 'field2'

      ExternalConfigurableNamedTuple.field1 = 'external_field1'
      ExternalConfigurableNamedTuple.field2 = 'external_field2'
    """
    config.parse_config(config_str)

    configurable_named_tuple = ConfigurableNamedTuple()
    self.assertEqual(configurable_named_tuple.field1, 'field1')
    self.assertEqual(configurable_named_tuple.field2, 'field2')

    configurable_named_tuple = configurable_external_named_tuple()
    self.assertEqual(configurable_named_tuple.field1, 'external_field1')
    self.assertEqual(configurable_named_tuple.field2, 'external_field2')

  def testRegisteredExternalNamedTuple(self):
    config_str = """
      RegisteredExternalNamedTuple.field1 = 'external_field1'
      RegisteredExternalNamedTuple.field2 = 'external_field2'
      create_named_tuple.named_tuple = @RegisteredExternalNamedTuple
    """
    config.parse_config(config_str)

    # expected = '__new__() takes exactly 3 arguments (1 given)'
    with self.assertRaises(TypeError):
      RegisteredExternalNamedTuple()

    with self.assertRaises(TypeError):
      create_named_tuple(RegisteredExternalNamedTuple)

    configurable_named_tuple = create_named_tuple(config.REQUIRED)
    self.assertEqual(configurable_named_tuple.field1, 'external_field1')
    self.assertEqual(configurable_named_tuple.field2, 'external_field2')

  def testFailedFunctionCall(self):
    def some_fn(only_one_arg=None):
      del only_one_arg

    @config.configurable('broken_function')
    def borked_fn(arg):  # pylint: disable=unused-variable
      # pytype: disable=wrong-keyword-args
      some_fn(nonexistent_arg=arg)  # pylint: disable=unexpected-keyword-arg
      # pytype: enable=wrong-keyword-args

    config.parse_config([
        'configurable2.non_kwarg = @broken_function()',
        'ConfigurableClass.kwarg1 = @scoped/broken_function()',
        'broken_function.arg = "mulberries"'
    ])

    expected_msg_regexp = r"'broken_function' \(<function .*borked_fn.*\)$"
    with self.assertRaisesRegex(TypeError, expected_msg_regexp):
      configurable2()  # pylint: disable=no-value-for-parameter

    expected_msg_regexp = r"'broken_function' \(<.*\) in scope 'scoped'$"
    with self.assertRaisesRegex(TypeError, expected_msg_regexp):
      ConfigurableClass()  # pylint: disable=no-value-for-parameter

  def testOperativeConfigStr(self):
    config_str = _TEST_CONFIG_STR
    config.constant('THE_ANSWER', 42)
    config.parse_config(config_str)
    config.finalize()

    call_operative_config_str_configurables()

    applied_config_lines = config.operative_config_str().splitlines()
    # See the definition of _EXPECTED_OPERATIVE_CONFIG_STR at top of file.
    expected_config_lines = _EXPECTED_OPERATIVE_CONFIG_STR.splitlines()
    self.assertEqual(applied_config_lines, expected_config_lines[1:])

  def testConfigStr(self):
    config_str = _TEST_CONFIG_STR
    config.constant('THE_ANSWER', 42)
    config.parse_config(config_str)
    config.finalize()

    config_lines = config.config_str().splitlines()
    # See the definition of _EXPECTED_CONFIG_STR at top of file.
    expected_config_lines = _EXPECTED_CONFIG_STR.splitlines()
    self.assertEqual(config_lines, expected_config_lines[1:])

  def testConfigStrWithProvenance(self):
    config_str = _TEST_CONFIG_STR
    config.constant('THE_ANSWER', 42)
    # We want a specific filename for the provenance here, so fake it:
    string_io = io.StringIO(config_str)
    setattr(string_io, 'name', 'test_config.ioreader')
    config.parse_config(string_io)
    config.finalize()

    config_lines = config.config_str(show_provenance=True).splitlines()
    # See the definition of _EXPECTED_CONFIG_STR_WITH_PROVENANCE.
    expected_config_lines = _EXPECTED_CONFIG_STR_WITH_PROVENANCE.splitlines()
    self.assertEqual(config_lines, expected_config_lines[1:])

  def testConfigStrDynamicRegistration(self):
    config_str = _TEST_DYNAMIC_REGISTRATION_CONFIG_STR.format(
        absltest.get_default_test_srcdir())
    config.parse_config(config_str)
    config.finalize()

    config_lines = config.config_str().splitlines()
    # See the definition of _EXPECTED_DYNAMIC_REGISTRATION_CONFIG_STR above.
    expected_lines = _EXPECTED_DYNAMIC_REGISTRATION_CONFIG_STR.splitlines()
    self.assertEqual(config_lines, expected_lines[1:])

  def testConfigStrDynamicRegistrationIsIdempotent(self):
    input_config_str = _TEST_DYNAMIC_REGISTRATION_CONFIG_STR.format(
        absltest.get_default_test_srcdir())
    config.parse_config(input_config_str)
    config_str = config.config_str()
    config.clear_config()
    config.parse_config(config_str)
    self.assertEqual(config.config_str(), config_str)

  def testOperativeConfigStrHandlesOverrides(self):
    config_str = """
      ConfigurableClass.kwarg1 = 'base_kwarg1'
      ConfigurableClass.kwarg2 = 'base_kwarg2'
      ConfigurableSubclass.kwarg1 = 'sub_kwarg1'
    """
    config.parse_config(config_str)

    ConfigurableSubclass()
    # Initially, since ConfigurableClass had all of its parameters overwritten,
    # none of them are logged to the operative config.
    selector = config._REGISTRY.get_match('ConfigurableClass').selector
    self.assertEqual(config._OPERATIVE_CONFIG['', selector], {})
    selector = config._REGISTRY.get_match('ConfigurableSubclass').selector
    self.assertEqual(config._OPERATIVE_CONFIG['', selector],
                     {'kwarg1': 'sub_kwarg1',
                      'kwarg2': None,
                      'kwarg3': None})

    ConfigurableClass()
    # Now that it's been called, we can see its parameters.
    selector = config._REGISTRY.get_match('ConfigurableClass').selector
    self.assertEqual(config._OPERATIVE_CONFIG['', selector],
                     {'kwarg1': 'base_kwarg1', 'kwarg2': 'base_kwarg2'})

    ConfigurableSubclass()
    # And they're still around after another call to the subclass.
    self.assertEqual(config._OPERATIVE_CONFIG['', selector],
                     {'kwarg1': 'base_kwarg1', 'kwarg2': 'base_kwarg2'})

  def testParsingOperativeConfigStrIsIdempotent(self):
    config_str = _TEST_CONFIG_STR
    config.constant('THE_ANSWER', 42)
    config.parse_config(config_str)

    call_operative_config_str_configurables()
    operative_config_str = config.operative_config_str()

    config.clear_config(clear_constants=False)
    config.parse_config(operative_config_str)

    call_operative_config_str_configurables()
    self.assertEqual(config.operative_config_str(), operative_config_str)

  def testParsingImportsIsIdempotentUpToSorting(self):
    config_str = """
      from __gin__ import dynamic_registration
      import gin.testdata.import_test_configurables as test_configurables
      import __main__ as main
      from gin import testdata
      from gin.testdata import dynamic_registration as dr
    """
    config.parse_config(config_str)
    expected_config_str = '\n'.join([
        'from __gin__ import dynamic_registration',
        'import __main__ as main',
        'from gin import testdata',
        'from gin.testdata import dynamic_registration as dr',
        'import gin.testdata.import_test_configurables as test_configurables',
    ])
    self.assertEqual(config.config_str().strip(), expected_config_str)

  def testAllowlist(self):
    config.bind_parameter('allowlisted_configurable.allowlisted', 0)
    self.assertEqual(allowlisted_configurable(), (0, None))
    config.bind_parameter('scope/allowlisted_configurable.allowlisted', 1)
    with config.config_scope('scope'):
      self.assertEqual(allowlisted_configurable(), (1, None))
    with self.assertRaises(ValueError):
      config.bind_parameter('allowlisted_configurable.other', 0)
    with self.assertRaises(ValueError):
      config.bind_parameter('a/b/allowlisted_configurable.other', 0)

  def testDenylist(self):
    config.bind_parameter('denylisted_configurable.other', 0)
    self.assertEqual(denylisted_configurable(), (None, 0))
    config.bind_parameter('scope/denylisted_configurable.other', 1)
    with config.config_scope('scope'):
      self.assertEqual(denylisted_configurable(), (None, 1))
    with self.assertRaises(ValueError):
      config.bind_parameter('denylisted_configurable.denylisted', 0)
    with self.assertRaises(ValueError):
      config.bind_parameter('a/b/denylisted_configurable.denylisted', 0)

  def testRegisteredClassWithRegisteredMethods(self):
    config_str = """
      RegisteredClassWithRegisteredMethods.param_a = 'a'
      RegisteredClassWithRegisteredMethods.param_b = 'b'

      RegisteredClassWithRegisteredMethods.registered_method1.arg = 1
      RegisteredClassWithRegisteredMethods.registered_method2.arg = 2

      pass_through.value = @RegisteredClassWithRegisteredMethods()
    """
    config.parse_config(config_str)

    instance = pass_through(value=config.REQUIRED)
    self.assertEqual(instance.param_a, 'a')
    self.assertEqual(instance.param_b, 'b')
    self.assertEqual(instance.registered_method1(), 1)
    self.assertEqual(instance.registered_method2(), 2)

  def testScopedRegisteredClassWithRegisteredMethods(self):
    config_str = """
      scope/RegisteredClassWithRegisteredMethods.param_a = 'a'
      scope/RegisteredClassWithRegisteredMethods.param_b = 'b'

      scope/RegisteredClassWithRegisteredMethods.registered_method1.arg = 1
      scope/RegisteredClassWithRegisteredMethods.registered_method2.arg = 2

      RegisteredClassWithRegisteredMethods.registered_method1.arg = None
      RegisteredClassWithRegisteredMethods.registered_method2.arg = None

      pass_through.value = @scope/RegisteredClassWithRegisteredMethods()
    """
    config.parse_config(config_str)

    instance = pass_through(value=config.REQUIRED)
    self.assertEqual(instance.param_a, 'a')
    self.assertEqual(instance.param_b, 'b')
    self.assertEqual(instance.registered_method1(), 1)
    self.assertEqual(instance.registered_method2(), 2)

  def testMustSpecifyClassNameForRegisteredMethods(self):
    expected_message = (
        r"Method 'registered_method2' referenced without class name "
        r"'RegisteredClassWithRegisteredMethods'\.")
    with self.assertRaisesRegex(ValueError, expected_message):
      config.parse_config('registered_method2.arg = 2')

  def testRegisteredClassWithCustomModuleAndRegisteredMethods(self):
    config_str = """
      custom.module.RegisteredClassWithCustomModule.registered_method.arg = 2
      pass_through.value = @RegisteredClassWithCustomModule()
    """
    config.parse_config(config_str)
    instance = pass_through(config.REQUIRED)
    self.assertEqual(instance.registered_method(), 2)

  def testDynamicallyRegisteredClassWithMethods(self):
    config_str = """
      from __gin__ import dynamic_registration

      import __main__ as test

      # The configurable reference is created before methods are registered.
      # Creating this reference also dynamically registers the class.
      test.pass_through.value = @test.DynamicallyRegisteredClassWithMethods()
      test.DynamicallyRegisteredClassWithMethods.param = 5
      # Configuring the methods should register them, and also re-register the
      # class in a way that picks up the new method registrations.
      test.DynamicallyRegisteredClassWithMethods.method1.arg = 'arg1'
      test.DynamicallyRegisteredClassWithMethods.method2:  # Test this syntax...
        arg = 'arg2'
      # Configuring methods provided by a base class should also work.
      test.DynamicallyRegisteredClassWithMethods.base_method.arg = 'base_arg'
    """
    config.parse_config(config_str)

    instance = pass_through(config.REQUIRED)
    self.assertEqual(instance.param, 5)
    self.assertEqual(instance.method1(), 'arg1')
    self.assertEqual(instance.method2(), 'arg2')
    self.assertEqual(instance.base_method(), 'base_arg')

  def testRequiredArgs(self):
    with self.assertRaisesRegex(RuntimeError, 'arg1.*arg2'):
      required_args(config.REQUIRED, config.REQUIRED, 3)

    config.bind_parameter('scope/required_args.arg1', 1)
    config.bind_parameter('scope/required_args.arg2', 2)
    with config.config_scope('scope'):
      self.assertEqual(
          required_args(config.REQUIRED, config.REQUIRED, 3),
          (1, 2, 3, 4, 5, 6))

  def testRequiredArgsWithVargs(self):
    with self.assertRaisesRegex(RuntimeError, 'arg1.*arg2'):
      required_with_vargs(config.REQUIRED, config.REQUIRED, 3, 4, 5, kwarg1=6)

    config.bind_parameter('scope/required_with_vargs.arg1', 1)
    config.bind_parameter('scope/required_with_vargs.arg2', 2)
    with config.config_scope('scope'):
      expected = (1, 2, 3, (4, 5), {'kwarg1': 6})
      actual = required_with_vargs(
          config.REQUIRED, config.REQUIRED, 3, 4, 5, kwarg1=6)
      self.assertEqual(expected, actual)

  def testRequiredDisallowedInVargs(self):
    with self.assertRaisesRegex(ValueError, 'not allowed'):
      required_with_vargs(1, 2, 3, config.REQUIRED)

  def testRequiredKwargs(self):
    with self.assertRaisesRegex(RuntimeError, 'kwarg1.*kwarg2|kwarg2.*kwarg1'):
      required_args(1, 2, 3, kwarg1=config.REQUIRED, kwarg2=config.REQUIRED)

    config.bind_parameter('scope/required_args.kwarg1', 4)
    config.bind_parameter('scope/required_args.kwarg2', 5)
    with config.config_scope('scope'):
      self.assertEqual(
          required_args(
              1, 2, 3, kwarg1=config.REQUIRED, kwarg2=config.REQUIRED),
          (1, 2, 3, 4, 5, 6))

  def testRequiredArgsAndKwargs(self):
    with self.assertRaisesRegex(RuntimeError,
                                'arg2.*kwarg1.*kwarg2|arg2.*kwarg2.*kwarg1'):
      required_args(
          1, config.REQUIRED, 3, kwarg1=config.REQUIRED, kwarg2=config.REQUIRED)

    config.bind_parameter('scope/required_args.arg3', 3)
    config.bind_parameter('scope/required_args.kwarg2', 5)
    with config.config_scope('scope'):
      self.assertEqual(
          required_args(1, 2, config.REQUIRED, kwarg2=config.REQUIRED),
          (1, 2, 3, 4, 5, 6))

  def testRequiredArgsVkwargs(self):
    with self.assertRaisesRegex(RuntimeError,
                                'arg2.*kwarg1.*kwarg6|arg2.*kwarg6.*kwarg1'):
      required_with_vkwargs(
          1, config.REQUIRED, 3, kwarg1=config.REQUIRED, kwarg6=config.REQUIRED)

    config.bind_parameter('scope/required_with_vkwargs.arg2', 2)
    config.bind_parameter('scope/required_with_vkwargs.kwarg1', 4)
    config.bind_parameter('scope/required_with_vkwargs.kwarg6', 7)
    with config.config_scope('scope'):
      expected = (1, 2, 3, 4, 5, 6, {'kwarg6': 7})
      actual = required_with_vkwargs(
          1, config.REQUIRED, 3, kwarg1=config.REQUIRED, kwarg6=config.REQUIRED)
      self.assertEqual(expected, actual)

  def testRequiredInSignature(self):
    expected_err_regexp = (
        r'Required bindings for `required_as_kwarg_default` not provided in '
        r"config: \['required_kwarg'\]")
    with self.assertRaisesRegex(RuntimeError, expected_err_regexp):
      required_as_kwarg_default('positional')
    # No issues if REQUIRED is also passed as by caller.
    with self.assertRaisesRegex(RuntimeError, expected_err_regexp):
      required_as_kwarg_default('positional', required_kwarg=config.REQUIRED)
    # No issues if REQUIRED is also passed to different arg.
    expected_err_regexp = r"config: \['positional_arg', 'required_kwarg'\]"
    with self.assertRaisesRegex(RuntimeError, expected_err_regexp):
      required_as_kwarg_default(config.REQUIRED, required_kwarg=config.REQUIRED)
    # Everything works if all values are passed.
    positional, kwarg = required_as_kwarg_default(
        'positional', required_kwarg='a value')
    # Even if not passed as a kwarg.
    positional, kwarg = required_as_kwarg_default('positional', 'a value')
    self.assertEqual(positional, 'positional')
    self.assertEqual(kwarg, 'a value')

  def testRequiredInSignatureDenylistAllowlist(self):
    expected_err_regexp = (
        r"Argument 'arg' of 'test_required_denylist' \('<function .+>'\) "
        r'marked REQUIRED but denylisted.')
    with self.assertRaisesRegex(ValueError, expected_err_regexp):
      config.external_configurable(
          lambda arg=config.REQUIRED: arg,
          'test_required_denylist',
          denylist=['arg'])
    expected_err_regexp = (
        r"Argument 'arg' of 'test_required_allowlist' \('<function .+>'\) "
        r'marked REQUIRED but not allowlisted.')
    with self.assertRaisesRegex(ValueError, expected_err_regexp):
      config.external_configurable(
          lambda arg=config.REQUIRED, arg2=4: arg,
          'test_required_allowlist',
          allowlist=['arg2'])

  def testRequiredInConfigHookNoOverride(self):
    config.parse_config("""
       required_args.arg2 = %gin.REQUIRED
       required_args.kwarg2 = None
    """)
    expected_msg = (
        r'required_args\.arg2 set to `%gin\.REQUIRED` but not subsequently '
        r'overridden.')
    with self.assertRaisesRegex(ValueError, expected_msg):
      config.finalize()

  def testRequiredInConfigHookWithOverride(self):
    config.parse_config("""
       required_args.arg2 = %gin.REQUIRED
       required_args.kwarg2 = None
       required_args.arg2 = 'valid override'
    """)
    config.finalize()

  def testKwOnlyArgs(self):
    config_str = """
      fn_with_kw_only_args.arg1 = 'arg1'
      fn_with_kw_only_args.kwarg1 = 'kwarg1'
    """

    arg, kwarg = fn_with_kw_only_args(None)
    self.assertIsNone(arg)
    self.assertIsNone(kwarg)
    self.assertIn('fn_with_kw_only_args.kwarg1 = None',
                  config.operative_config_str())

    config.parse_config(config_str)

    arg, kwarg = fn_with_kw_only_args('arg1')
    self.assertEqual(arg, 'arg1')
    self.assertEqual(kwarg, 'kwarg1')
    self.assertIn("fn_with_kw_only_args.kwarg1 = 'kwarg1'",
                  config.operative_config_str())

  def testKwOnlyRequiredArgs(self):
    expected_err_regexp = (
        r'Required bindings for `fn_with_kw_only_args` not provided in config: '
        r"\['kwarg1'\]")
    with self.assertRaisesRegex(RuntimeError, expected_err_regexp):
      fn_with_kw_only_args('positional', kwarg1=config.REQUIRED)

  def testKwOnlyRequiredArgsInSignature(self):
    expected_err_regexp = (
        r'Required bindings for `fn_with_kw_only_required_arg` not provided in '
        r"config: \['kwarg1'\]")
    with self.assertRaisesRegex(RuntimeError, expected_err_regexp):
      fn_with_kw_only_required_arg('positional')
    arg, kwarg = fn_with_kw_only_required_arg('positional', kwarg1='a value')
    self.assertEqual(arg, 'positional')
    self.assertEqual(kwarg, 'a value')

  def testConfigScope(self):
    config_str = """
      configurable2.non_kwarg = 'no_scope_arg_0'
      configurable2.kwarg1 = 'no_scope_arg_1'

      scope_1/configurable2.non_kwarg = 'scope_1_arg_0'
      scope_1/configurable2.kwarg1 = 'scope_1_arg_1'

      scope_1/scope_2/configurable2.non_kwarg = 'scope_2_arg_0'
    """
    config.parse_config(config_str)

    # pylint: disable=no-value-for-parameter
    self.assertEqual(configurable2(), ('no_scope_arg_0', 'no_scope_arg_1'))
    with config.config_scope('scope_1'):
      self.assertEqual(configurable2(), ('scope_1_arg_0', 'scope_1_arg_1'))
      with config.config_scope('scope_2'):
        self.assertEqual(configurable2(), ('scope_2_arg_0', 'scope_1_arg_1'))
        with config.config_scope(None):
          expected = ('no_scope_arg_0', 'no_scope_arg_1')
          self.assertEqual(configurable2(), expected)
        self.assertEqual(configurable2(), ('scope_2_arg_0', 'scope_1_arg_1'))
      self.assertEqual(configurable2(), ('scope_1_arg_0', 'scope_1_arg_1'))
    self.assertEqual(configurable2(), ('no_scope_arg_0', 'no_scope_arg_1'))

    # Test shorthand for nested scopes.
    with config.config_scope('scope_1/scope_2'):
      self.assertEqual(configurable2(), ('scope_2_arg_0', 'scope_1_arg_1'))

    with self.assertRaisesRegex(ValueError, 'Invalid value'):
      with config.config_scope(4):
        pass

    with self.assertRaisesRegex(ValueError, 'Invalid value'):
      with config.config_scope('inv@lid/scope/name!'):
        pass

    with self.assertRaisesRegex(ValueError, 'Invalid value'):
      with config.config_scope(0):
        pass

  def testImplicitScopes(self):
    config_str = """
      configurable2.non_kwarg = 'no_scope_non_kwarg'
      configurable2.kwarg1 = 'no_scope_kwarg1'

      implicit_scope_1/configurable2.non_kwarg = '#1_non_kwarg'
      implicit_scope_1/configurable2.kwarg1 = '#1_kwarg1'

      implicit_scope_2/configurable2.kwarg1 = '#2_kwarg1'

      ConfigurableClass.kwarg1 = @implicit_scope_1/configurable2
      ConfigurableClass.kwarg2 = @implicit_scope_2/configurable2()
    """
    config.parse_config(config_str)

    value = ConfigurableClass()
    self.assertEqual(value.kwarg1(), ('#1_non_kwarg', '#1_kwarg1'))
    self.assertEqual(value.kwarg2, ('no_scope_non_kwarg', '#2_kwarg1'))

  def testExplicitVsImplicitScopes(self):
    config_str = """
      configurable2.non_kwarg = 'no_scope_non_kwarg'
      configurable2.kwarg1 = 'no_scope_kwarg1'

      explicit_scope/configurable2.non_kwarg = 'explicit_non_kwarg'
      explicit_scope/configurable2.kwarg1 = 'explicit_scope'

      implicit_scope/configurable2.kwarg1 = 'implicit_scope'

      ConfigurableClass.kwarg1 = @implicit_scope/configurable2
      ConfigurableClass.kwarg2 = @configurable2()
    """
    config.parse_config(config_str)

    value = ConfigurableClass()
    self.assertEqual(value.kwarg1(), ('no_scope_non_kwarg', 'implicit_scope'))
    self.assertEqual(value.kwarg2, ('no_scope_non_kwarg', 'no_scope_kwarg1'))

    with config.config_scope('explicit_scope'):
      value = ConfigurableClass()
    self.assertEqual(value.kwarg1(), ('no_scope_non_kwarg', 'implicit_scope'))
    self.assertEqual(value.kwarg2, ('explicit_non_kwarg', 'explicit_scope'))

  def testScopingThreadSafety(self):

    # pylint: disable=unused-variable
    @config.configurable(denylist=['expected_value'])
    def sanity_check(expected_value, config_value=None):
      return expected_value == config_value

    # pylint: enable=unused-variable

    def validate_test_fn(output_list, index, test_fn):
      for _ in range(10000):
        output_list[index] = output_list[index] and test_fn(index)

    @config.configurable
    def run_threaded_test_fns(test_fns):
      outputs = [True] * len(test_fns)
      threads = []
      for i, test_fn in enumerate(test_fns):
        args = (outputs, i, test_fn)
        thread = threading.Thread(target=validate_test_fn, args=args)
        threads.append(thread)
        thread.start()

      for thread in threads:
        thread.join()

      return outputs

    config_str = """
      scope0/sanity_check.config_value = 0
      scope1/sanity_check.config_value = 1
      scope2/sanity_check.config_value = 2
      scope3/sanity_check.config_value = 3

      run_threaded_test_fns.test_fns = [
          @scope0/sanity_check,
          @scope1/sanity_check,
          @scope2/sanity_check,
          @scope3/sanity_check,
      ]
    """
    config.parse_config(config_str)
    outputs = run_threaded_test_fns(config.REQUIRED)
    self.assertTrue(all(outputs))

  def testIterateReferences(self):
    config_str = """
      configurable2.non_kwarg = [
          {'so': @much/macro()},
          (@nesting/macro(),)
      ]
      configurable2.kwarg1 = {
          'another': {'deeply': ['nested', (@structure/macro(),)]}
      }
    """
    config.parse_config(config_str)
    macros_iterator = config.iterate_references(
        config._CONFIG, to=config.get_configurable(config.macro))
    self.assertLen(list(macros_iterator), 3)

  def testInteractiveMode(self):
    @config.configurable('duplicate_fn')
    def duplicate_fn1():  # pylint: disable=unused-variable
      return 'duplicate_fn1'

    expected_msg = (
        r"A different configurable matching '__main__\.duplicate_fn' already "
        r'exists.')

    with self.assertRaisesRegex(ValueError, expected_msg):

      @config.configurable('duplicate_fn')
      def duplicate_fn2():  # pylint: disable=unused-variable
        pass

    config_str = """
      ConfigurableClass.kwarg1 = @duplicate_fn()
    """
    config.parse_config(config_str)
    self.assertEqual(ConfigurableClass().kwarg1, 'duplicate_fn1')

    with config.interactive_mode():
      @config.configurable('duplicate_fn')
      def duplicate_fn3():  # pylint: disable=unused-variable
        return 'duplicate_fn3'

    with self.assertRaisesRegex(ValueError, expected_msg):

      @config.configurable('duplicate_fn')
      def duplicate_fn4():  # pylint: disable=unused-variable
        pass

    config_str = """
      ConfigurableClass.kwarg1 = @duplicate_fn()
    """
    config.parse_config(config_str)
    self.assertEqual(ConfigurableClass().kwarg1, 'duplicate_fn3')

  def testFinalizeLocksConfig(self):
    config.finalize()
    with self.assertRaises(RuntimeError):
      config.parse_config('configurable2.non_kwarg = 3')
    with self.assertRaises(RuntimeError):
      config.bind_parameter('configurable2.non_kwarg', 3)
    with self.assertRaises(RuntimeError):
      @config.configurable
      def bah():  # pylint: disable=unused-variable
        pass
    with self.assertRaises(RuntimeError):
      config.external_configurable(RuntimeError)

  def testUnlockConfig(self):
    with config.unlock_config():
      pass
    self.assertFalse(config.config_is_locked())
    config.finalize()
    with config.unlock_config():
      config.parse_config('configurable2.kwarg1 = 3')
    self.assertTrue(config.config_is_locked())
    self.assertEqual(configurable2(1), (1, 3))

  def testFinalizeHooks(self):
    self.skipTest('b/137302565')
    old_finalize_hooks = config._FINALIZE_HOOKS[:]

    @config.register_finalize_hook
    def provide_binding(_):  # pylint: disable=unused-variable
      return {'configurable2.kwarg1': 5}

    _, kwarg = configurable2(None)
    self.assertIsNone(kwarg)
    config.finalize()
    _, kwarg = configurable2(None)
    self.assertEqual(kwarg, 5)

    @config.register_finalize_hook
    def provide_conflicting_binding(_):  # pylint: disable=unused-variable
      # Provide a slightly different selector.
      return {'config_test.configurable2.kwarg1': 7}

    with self.assertRaises(ValueError), config.unlock_config():
      config.finalize()

    config._FINALIZE_HOOKS = old_finalize_hooks

  def testBasicMacro(self):
    config_str = """
      batch_size/macro.value = 512
      discriminator/num_layers/macro.value = 5
      configurable2.non_kwarg = @batch_size/macro()
      configurable2.kwarg1 = @discriminator/num_layers/macro()
    """
    config.parse_config(config_str)
    # pylint:disable=no-value-for-parameter
    batch_size, num_layers = configurable2()
    # pylint:enable=no-value-for-parameter
    self.assertEqual(batch_size, 512)
    self.assertEqual(num_layers, 5)

  def testOverwriteBasicMacro(self):
    config_str = """
      batch_size/macro.value = 512
      discriminator/num_layers/macro.value = 5
      configurable2:
        non_kwarg = @batch_size/macro()
        kwarg1 = @discriminator/num_layers/macro()
    """
    config.parse_config(config_str)
    config.bind_parameter('batch_size/macro.value', 256)
    config.bind_parameter('discriminator/num_layers/macro.value', 10)
    # pylint:disable=no-value-for-parameter
    batch_size, num_layers = configurable2()
    # pylint:enable=no-value-for-parameter
    self.assertEqual(batch_size, 256)
    self.assertEqual(num_layers, 10)

  def testSpecialMacroSyntax(self):
    config_str = """
      batch_size = 512
      discriminator/num_layers = 5
      configurable2.non_kwarg = %batch_size
      configurable2.kwarg1 = %discriminator/num_layers
    """
    config.parse_config(config_str)
    # pylint:disable=no-value-for-parameter
    batch_size, num_layers = configurable2()
    # pylint:enable=no-value-for-parameter
    self.assertEqual(batch_size, 512)
    self.assertEqual(num_layers, 5)

  def testOverwriteSpecialMacroSyntax(self):
    config_str = """
      batch_size = 512
      discriminator/num_layers = 5
      configurable2.non_kwarg = %batch_size
      configurable2.kwarg1 = %discriminator/num_layers
    """
    config.parse_config(config_str)
    config.bind_parameter('%batch_size', 256)
    config.bind_parameter('%discriminator/num_layers', 10)
    # pylint:disable=no-value-for-parameter
    batch_size, num_layers = configurable2()
    # pylint:enable=no-value-for-parameter
    self.assertEqual(batch_size, 256)
    self.assertEqual(num_layers, 10)

  def testUncalledMacroAtFinalize(self):
    config_str = """
      batch_size/macro.value = 512
      configurable2.non_kwarg = ([{'batch_size': @batch_size/macro}],)
    """
    config.parse_config(config_str)
    with self.assertRaises(ValueError):
      config.finalize()

  def testModuleDisambiguation(self):
    with self.assertRaises(KeyError):
      config.bind_parameter('dolly.kwarg', 5)
    with self.assertRaises(KeyError):
      config.bind_parameter('sheep.dolly.kwarg', 5)
    with self.assertRaises(ValueError):
      # Make sure the default module isn't prepended if the module is supplied
      # as part of the configurable name.
      config.bind_parameter('__main__.a.fuzzy.sheep.dolly.kwarg', 5)

    config_str = """
      __main__.dolly.kwarg = ''
      furry.sheep.dolly.kwarg = 'bah'
      a.woolly.sheep.dolly.kwarg = 'baaah'
      fuzzy.sheep.dolly.kwarg = 'baaaaah'
      hairy.sheep.dolly.kwarg = 'baaaaaaah'
      cow/woolly.sheep.dolly.kwarg = 'mooo'
      reference/furry.sheep.dolly.kwarg = @cow/a.woolly.sheep.dolly()
    """
    config.parse_config(config_str)
    self.assertEqual(clone0(), '')
    self.assertEqual(clone1(), 'bah')
    self.assertEqual(clone2(), 'baaah')
    self.assertEqual(clone3(), 'baaaaah')
    self.assertEqual(clone4(), 'baaaaaaah')
    with config.config_scope('cow'):
      self.assertEqual(clone2(), 'mooo')
    with config.config_scope('reference'):
      self.assertEqual(clone1(), 'mooo')

  def testConstant(self):
    value = 'istanbul'
    config.constant('CONSTANTINOPLE', value)
    config_str = """
      configurable2.non_kwarg = %CONSTANTINOPLE
    """
    config.parse_config(config_str)
    non_kwarg, _ = configurable2()  # pylint: disable=no-value-for-parameter
    self.assertIs(non_kwarg, value)  # We should be getting the same object.

    with self.assertRaisesRegex(ValueError, 'Invalid constant selector'):
      config.constant('CONST@NTINOPLE', 0)

  def testConstantModuleDisambiguation(self):
    config.constant('foo.PI', 3.14)
    config.constant('bar.PI', 22/7)
    config.constant('bar.E', 2.718)

    with self.assertRaises(ValueError):
      config.parse_config('configurable2.non_kwarg = %PI')

    config_str = """
      configurable2.non_kwarg = %foo.PI
      configurable2.kwarg1 = %bar.PI
      ConfigurableClass.kwarg1 = %E
      ConfigurableClass.kwarg2 = %bar.E
    """
    config.parse_config(config_str)

    non_kwarg, kwarg1 = configurable2()  # pylint: disable=no-value-for-parameter
    self.assertEqual(non_kwarg, 3.14)
    self.assertEqual(kwarg1, 22/7)

    configurable_class = ConfigurableClass()
    self.assertEqual(configurable_class.kwarg1, 2.718)
    self.assertEqual(configurable_class.kwarg2, 2.718)

  def testSingletons(self):
    config_str = """
      ConfigurableClass:
        kwarg1 = @obj1/singleton()
        kwarg2 = @obj2/singleton()
      error/ConfigurableClass.kwarg1 = @not_callable/singleton()

      obj1/singleton.constructor = @new_object
      obj2/singleton.constructor = @new_object
      not_callable/singleton.constructor = @new_object()
    """
    config.parse_config(config_str)

    class1 = ConfigurableClass()
    class2 = ConfigurableClass()
    self.assertIs(class1.kwarg1, class2.kwarg1)
    self.assertIs(class1.kwarg2, class2.kwarg2)
    self.assertIsNot(class1.kwarg1, class1.kwarg2)
    self.assertIsNot(class2.kwarg1, class2.kwarg2)
    with config.config_scope('error'):
      expected = "The constructor for singleton 'not_callable' is not callable."
      with self.assertRaisesRegex(ValueError, expected):
        ConfigurableClass()

  def testSingletonsWithDynamicRegistration(self):
    config_str = """
      from __gin__ import dynamic_registration

      import gin.testdata.dynamic_registration as dynamic_registration

      CLASS = @class/gin.singleton()
      class/gin.singleton.constructor = @dynamic_registration.Class

      dynamic_registration.Class.a = 3
      dynamic_registration.Class.b = 7

      scope_1/dynamic_registration.function.arg = %CLASS
      scope_2/dynamic_registration.function.arg = %CLASS
    """
    config.parse_config(config_str)

    f = config.get_configurable('dynamic_registration.function')
    with config.config_scope('scope_1'):
      c1 = f()

    with config.config_scope('scope_2'):
      c2 = f()
    self.assertIs(c1, c2)

  def testQueryParameter(self):
    config.bind_parameter('allowlisted_configurable.allowlisted', 0)
    value = config.query_parameter('allowlisted_configurable.allowlisted')
    self.assertEqual(0, value)
    with self.assertRaises(ValueError):
      config.query_parameter('allowlisted_configurable.wrong_param')
    with self.assertRaises(ValueError):
      config.query_parameter('denylisted_configurable.denylisted')
    with self.assertRaises(ValueError):
      # Parameter not set.
      config.query_parameter('allowlisted_configurable.other')
    with self.assertRaisesRegex(TypeError, 'expected string*'):
      config.query_parameter(4)

  def testQueryConstant(self):
    config.constant('Euler', 0.5772156649)
    self.assertEqual(0.5772156649, config.query_parameter('Euler'))
    config.constant('OLD.ANSWER', 0)
    config.constant('NEW.ANSWER', 10)
    with self.assertRaisesRegex(ValueError, 'Ambiguous constant selector*'):
      config.query_parameter('ANSWER')
    self.assertEqual(0, config.query_parameter('OLD.ANSWER'))
    self.assertEqual(10, config.query_parameter('NEW.ANSWER'))

  def testConstantsFromEnum(self):

    @config.constants_from_enum(module='enum_module')
    class SomeEnum(enum.Enum):
      A = 0,
      B = 1

    @config.configurable
    def f(a, b):
      return a, b

    config.parse_config("""
      f.a = %enum_module.SomeEnum.A
      f.b = %SomeEnum.B
    """)
    # pylint: disable=no-value-for-parameter
    a, b = f()
    # pylint: enable=no-value-for-parameter
    self.assertEqual(SomeEnum.A, a)
    self.assertEqual(SomeEnum.B, b)

  def testConstantsFromEnumWithModule(self):

    class SomeOtherEnum(enum.Enum):
      A = 0,
      B = 1

    @config.configurable
    def g(a, b):
      return a, b

    config.constants_from_enum(SomeOtherEnum, module='TestModule')
    config.parse_config("""
      g.a = %TestModule.SomeOtherEnum.A
      g.b = %SomeOtherEnum.B
    """)
    # pylint: disable=no-value-for-parameter
    a, b = g()
    # pylint: enable=no-value-for-parameter
    self.assertEqual(SomeOtherEnum.A, a)
    self.assertEqual(SomeOtherEnum.B, b)

  def testConstantsFromEnumNotEnum(self):
    expected_msg = "Class 'FakeEnum' is not subclass of enum."
    with self.assertRaisesRegex(TypeError, expected_msg):

      # pylint: disable=unused-variable
      @config.constants_from_enum
      class FakeEnum:
        A = 0,
        B = 1

  def testAddConfigPath(self):
    gin_file = 'test_gin_file_location_prefix.gin'
    with self.assertRaises(IOError):
      config.parse_config_files_and_bindings([gin_file], None)
    test_srcdir = absltest.get_default_test_srcdir()
    relative_testdata_path = 'gin/testdata'
    absolute_testdata_path = os.path.join(test_srcdir, relative_testdata_path)
    config.add_config_file_search_path(absolute_testdata_path)
    config.parse_config_files_and_bindings([gin_file], None)

  def testPrintAndReturnNestedIncludesAndImports(self):
    gin_file = 'root_with_nested_includes_and_imports.gin'
    test_srcdir = absltest.get_default_test_srcdir()
    relative_testdata_path = 'gin/testdata'
    absolute_testdata_path = os.path.join(test_srcdir, relative_testdata_path)
    config.add_config_file_search_path(absolute_testdata_path)
    result = config.parse_config_files_and_bindings(
        [gin_file], None, print_includes_and_imports=True)[0]
    self.assertEqual(result.filename, gin_file)
    self.assertListEqual(result.imports,
                         ['gin.testdata.import_test_configurables'])
    self.assertEqual(result.includes[0].filename, 'valid.gin')
    self.assertListEqual(result.includes[0].imports, [])
    self.assertListEqual(result.includes[0].includes, [])
    self.assertEqual(result.includes[1].filename, 'nested.gin')
    self.assertListEqual(result.includes[1].imports, ['io', 'time'])
    self.assertListEqual(result.includes[1].includes, [])

  def testEmptyNestedIncludesAndImports(self):
    test_srcdir = absltest.get_default_test_srcdir()
    relative_testdata_path = 'gin/testdata'
    absolute_testdata_path = os.path.join(test_srcdir, relative_testdata_path)
    config.add_config_file_search_path(absolute_testdata_path)
    result = config.parse_config_files_and_bindings(
        [], ['TEST=1'], print_includes_and_imports=True)
    self.assertListEqual(result, [])

  def testGetBindings(self):
    # Bindings can be accessed through name or object
    # Default are empty
    self.assertDictEqual(config.get_bindings('configurable1'), {})
    self.assertDictEqual(config.get_bindings(fn1), {})

    self.assertDictEqual(config.get_bindings('ConfigurableClass'), {})
    self.assertDictEqual(config.get_bindings(ConfigurableClass), {})

    config_str = """
      configurable1.non_kwarg = 'kwarg1'
      configurable1.kwarg2 = 123
      ConfigurableClass.kwarg1 = @pass_through()

      pass_through.value = 'okie dokie'
    """
    config.parse_config(config_str)

    self.assertDictEqual(config.get_bindings('configurable1'), {
        'non_kwarg': 'kwarg1',
        'kwarg2': 123,
    })
    self.assertDictEqual(config.get_bindings(fn1), {
        'non_kwarg': 'kwarg1',
        'kwarg2': 123,
    })

    self.assertDictEqual(config.get_bindings('ConfigurableClass'), {
        'kwarg1': 'okie dokie',
    })
    self.assertDictEqual(config.get_bindings(ConfigurableClass), {
        'kwarg1': 'okie dokie',
    })

  def testGetBindingsScope(self):
    config_str = """
      configurable1.non_kwarg = 'kwarg1'
      configurable1.kwarg2 = 123
      scope/configurable1.kwarg2 = 456
    """
    config.parse_config(config_str)

    self.assertDictEqual(config.get_bindings('configurable1'), {
        'non_kwarg': 'kwarg1',
        'kwarg2': 123,
    })
    self.assertDictEqual(config.get_bindings(fn1), {
        'non_kwarg': 'kwarg1',
        'kwarg2': 123,
    })

    with config.config_scope('scope'):
      self.assertDictEqual(config.get_bindings('configurable1'), {
          'non_kwarg': 'kwarg1',
          'kwarg2': 456,
      })
      self.assertDictEqual(config.get_bindings(fn1), {
          'non_kwarg': 'kwarg1',
          'kwarg2': 456,
      })

  def testGetBindingsScopeStrict(self):
    config_str = """
      configurable1.kwarg1 = 9
      scope/scope2/configurable1.kwarg1 = 7
    """
    config.parse_config(config_str)

    get_binding_strict = functools.partial(
        config.get_bindings, inherit_scopes=False)

    self.assertDictEqual(
        get_binding_strict('configurable1'), {'kwarg1': 9})
    self.assertDictEqual(
        get_binding_strict('scope/configurable1'), {})
    self.assertDictEqual(
        get_binding_strict('scope/scope2/configurable1'), {'kwarg1': 7})
    self.assertDictEqual(
        get_binding_strict('scope2/configurable1'), {})

  def testGetBindingsReferences(self):
    # `resolve_references=True`
    config_str = """
      configurable1.non_kwarg = @configurable2
    """
    config.parse_config(config_str)
    self.assertDictEqual(config.get_bindings('configurable1'), {
        'non_kwarg': configurable2,
    })

    # `resolve_references=False`
    config.parse_config(config_str)
    non_kwarg = config.get_bindings(
        'configurable1', resolve_references=False)['non_kwarg']
    self.assertIsInstance(non_kwarg, config.ConfigurableReference)

  def testGetBindingsUnknown(self):
    expected_msg = 'Could not find .* in the Gin registry'
    with self.assertRaisesRegex(ValueError, expected_msg):
      config.get_bindings('UnknownParam')

    with self.assertRaisesRegex(ValueError, expected_msg):
      config.get_bindings(lambda x: None)

  def testGetConfigurable(self):
    self.assertIs(config.get_configurable(pass_through), pass_through)
    self.assertIs(
        config.get_configurable(pass_through.__wrapped__), pass_through)
    self.assertIs(config.get_configurable('pass_through'), pass_through)

    expected_msg = 'Could not find .* in the Gin registry'
    with self.assertRaisesRegex(ValueError, expected_msg):
      config.get_configurable('unknown.selector')

  def testGetConfigurableScoped(self):
    config_str = """
      other_scope/pass_through.value = 5
      test_scope/pass_through.value = @other_scope/pass_through()
    """
    config.parse_config(config_str)
    unscoped = config.get_configurable('pass_through')
    with self.assertRaises(TypeError):  # Missing parameter.
      unscoped()

    scoped = config.get_configurable('test_scope/pass_through')
    self.assertEqual(scoped(), 5)

    with config.config_scope('test_scope'):
      scoped = config.get_configurable(pass_through)
    self.assertEqual(scoped(), 5)

    with config.config_scope('other_scope'):
      # An explicit scope as part of the passed selector takes precedence.
      scoped = config.get_configurable('test_scope/pass_through')
    self.assertEqual(scoped(), 5)


if __name__ == '__main__':
  absltest.main()
