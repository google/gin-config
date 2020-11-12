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
import inspect
import io
import logging
import os
import threading

from absl.testing import absltest

from gin import config


_EXPECTED_OPERATIVE_CONFIG_STR = """
import gin.testdata.import_test_configurables

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
import gin.testdata.import_test_configurables

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


@config.configurable('configurable1')
def fn1(non_kwarg, kwarg1=None, kwarg2=None, kwarg3=None):
  return non_kwarg, kwarg1, kwarg2, kwarg3


@config.configurable
def configurable2(non_kwarg, kwarg1=None):
  return non_kwarg, kwarg1


@config.configurable(whitelist=['whitelisted'])
def whitelisted_configurable(whitelisted=None, other=None):
  return whitelisted, other


@config.configurable(blacklist=['blacklisted'])
def blacklisted_configurable(blacklisted=None, other=None):
  return blacklisted, other


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


@config.configurable
class ObjectSubclassWithoutInit:
  """A class that subclasses object but doesn't define its own __init__.

  While there's nothing to configure in this class, it may still be desirable to
  instantiate such a class from within Gin and bind it to something else.
  """

  @config.configurable(module='ObjectSubclassWithoutInit')
  def method(self, arg1='default'):
    return arg1


class ExternalClass:
  """A class we'll pretend was defined somewhere else."""

  __module__ = 'timbuktu'

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

    config.external_configurable(lambda arg: arg, 'lamdba1', blacklist=['arg'])
    config.external_configurable(lambda arg: arg, 'lambda2', whitelist=['arg'])

    err_regexp = '.* not a parameter of'
    with self.assertRaisesRegex(ValueError, err_regexp):
      config.external_configurable(
          lambda arg: arg, 'lambda3', blacklist=['nonexistent'])
    with self.assertRaisesRegex(ValueError, err_regexp):
      config.external_configurable(
          lambda arg: arg, 'lambda4', whitelist=['nonexistent'])

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
      configurable1.kwarg1 = 'stringval'
      configurable1.kwarg2 = @scoped/configurable2()
      configurable1.kwarg3 = @configurable2
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

    # Because references always wrap the original class via subclassing, other
    # subclasses of the original class are not subclasses of the reference.
    self.assertFalse(issubclass(sub_cls_ref, super_cls_ref))
    self.assertNotIsInstance(sub_instance, super_cls_ref)
    self.assertNotIsInstance(sub_instance, type(super_instance))

    self.assertEqual(super_instance.kwarg1, 'one')
    self.assertIsNone(super_instance.kwarg2)
    self.assertEqual(sub_instance.kwarg1, 'some')
    self.assertIsNone(sub_instance.kwarg2)
    self.assertEqual(sub_instance.kwarg3, 'thing')

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
    self.assertEqual(instance.kwarg1, 'statler')
    self.assertEqual(instance.kwarg2, 'waldorf')

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
      scope1/ConfigurableClass.kwarg1 = 'scope1arg1'
      scope1/ConfigurableClass.kwarg2 = 'scope1arg2'
      scope2/ConfigurableClass.kwarg1 = 'scope2arg1'
      scope2/ConfigurableClass.kwarg2 = 'scope2arg2'
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

    self.assertEqual(super_instance.kwarg1, 'one')
    self.assertIsNone(super_instance.kwarg2)

    self.assertIsNone(sub_instance.kwarg1)
    self.assertEqual(sub_instance.kwarg2, 'two')
    self.assertEqual(sub_instance.kwarg3, 'three')

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
    config_str = """
      import gin.testdata.import_test_configurables

      configurable1.kwarg1 = \\
        'a super duper extra double very wordy string that is just plain long'
      configurable1.kwarg3 = @configurable2
      configurable2.non_kwarg = 'ferret == domesticated polecat'
      ConfigurableClass.kwarg1 = 'statler'
      ConfigurableClass.kwarg2 = 'waldorf'
      ConfigurableSubclass.kwarg1 = 'waldorf'
      ConfigurableSubclass.kwarg3 = 'ferret'
      test/scopes/ConfigurableClass.kwarg2 = 'beaker'
      var_arg_fn.non_kwarg2 = {
        'long': [
          'nested', 'structure', ('that', 'will', 'span'),
          'more', ('than', 1), 'line',
        ]
      }
      var_arg_fn.any_name_is_ok = [%THE_ANSWER, %super/sweet, %pen_names]
      var_arg_fn.float_value = 2.718
      var_arg_fn.dict_value = {'success': True}

      super/sweet = 'lugduname'
      pen_names = ['Pablo Neruda', 'Voltaire', 'Snoop Lion']
      a.woolly.sheep.dolly.kwarg = 0
    """
    config.constant('THE_ANSWER', 42)
    config.parse_config(config_str)
    config.finalize()

    fn1('mustelid')
    # pylint: disable=no-value-for-parameter
    configurable2(kwarg1='I am supplied explicitly.')
    # pylint: enable=no-value-for-parameter
    ConfigurableClass()
    ConfigurableSubclass()
    with config.config_scope('test'):
      with config.config_scope('scopes'):
        ConfigurableClass()
    var_arg_fn('non_kwarg1_value')  # pylint: disable=no-value-for-parameter
    no_arg_fn()
    clone2()

    applied_config_lines = config.operative_config_str().splitlines()
    # See the definition of _EXPECTED_OPERATIVE_CONFIG_STR at top of file.
    expected_config_lines = _EXPECTED_OPERATIVE_CONFIG_STR.splitlines()
    self.assertEqual(applied_config_lines, expected_config_lines[1:])

  def testConfigStr(self):
    config_str = """
      import gin.testdata.import_test_configurables

      configurable1.kwarg1 = \\
        'a super duper extra double very wordy string that is just plain long'
      configurable1.kwarg3 = @configurable2
      configurable2.non_kwarg = 'ferret == domesticated polecat'
      ConfigurableClass.kwarg1 = 'statler'
      ConfigurableClass.kwarg2 = 'waldorf'
      ConfigurableSubclass.kwarg1 = 'waldorf'
      ConfigurableSubclass.kwarg3 = 'ferret'
      test/scopes/ConfigurableClass.kwarg2 = 'beaker'
      var_arg_fn.non_kwarg2 = {
        'long': [
          'nested', 'structure', ('that', 'will', 'span'),
          'more', ('than', 1), 'line',
        ]
      }
      var_arg_fn.any_name_is_ok = [%THE_ANSWER, %super/sweet, %pen_names]
      var_arg_fn.float_value = 2.718
      var_arg_fn.dict_value = {'success': True}

      super/sweet = 'lugduname'
      pen_names = ['Pablo Neruda', 'Voltaire', 'Snoop Lion']
      a.woolly.sheep.dolly.kwarg = 0
    """
    config.constant('THE_ANSWER', 42)
    config.parse_config(config_str)
    config.finalize()

    config_lines = config.config_str().splitlines()
    # See the definition of _EXPECTED_CONFIG_STR at top of file.
    expected_config_lines = _EXPECTED_CONFIG_STR.splitlines()
    self.assertEqual(config_lines, expected_config_lines[1:])

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
    config_str = """
      configurable1.kwarg1 = \\
        'a super duper extra double very wordy string that is just plain long'
      configurable1.kwarg3 = @configurable2
      configurable2.non_kwarg = 'ferret == domesticated polecat'
      ConfigurableClass.kwarg1 = 'statler'
      ConfigurableClass.kwarg2 = 'waldorf'
      ConfigurableSubclass.kwarg1 = 'subclass_kwarg1'
      ConfigurableSubclass.kwarg3 = 'subclass_kwarg3'
      test/scopes/ConfigurableClass.kwarg2 = 'beaker'
      var_arg_fn.non_kwarg2 = {
        'long': [
          'nested', 'structure', ('that', 'will', 'span'),
          'more', ('than', 1), 'line',
        ]
      }
      var_arg_fn.any_name_is_ok = [1, 2, 3]
      var_arg_fn.float_value = 2.718
      var_arg_fn.dict_value = {'success': True}
    """
    config.parse_config(config_str)

    def call_configurables():
      fn1('mustelid')
      # pylint: disable=no-value-for-parameter
      configurable2(kwarg1='I am supplied explicitly.')
      # pylint: enable=no-value-for-parameter
      ConfigurableClass()
      ConfigurableSubclass()
      with config.config_scope('test'):
        with config.config_scope('scopes'):
          ConfigurableClass()
      var_arg_fn('non_kwarg1_value')  # pylint: disable=no-value-for-parameter

    call_configurables()
    operative_config_str = config.operative_config_str()

    config.clear_config()
    config.parse_config(operative_config_str)

    call_configurables()
    self.assertEqual(config.operative_config_str(), operative_config_str)

  def testWhitelist(self):
    config.bind_parameter('whitelisted_configurable.whitelisted', 0)
    self.assertEqual(whitelisted_configurable(), (0, None))
    config.bind_parameter('scope/whitelisted_configurable.whitelisted', 1)
    with config.config_scope('scope'):
      self.assertEqual(whitelisted_configurable(), (1, None))
    with self.assertRaises(ValueError):
      config.bind_parameter('whitelisted_configurable.other', 0)
    with self.assertRaises(ValueError):
      config.bind_parameter('a/b/whitelisted_configurable.other', 0)

  def testBlacklist(self):
    config.bind_parameter('blacklisted_configurable.other', 0)
    self.assertEqual(blacklisted_configurable(), (None, 0))
    config.bind_parameter('scope/blacklisted_configurable.other', 1)
    with config.config_scope('scope'):
      self.assertEqual(blacklisted_configurable(), (None, 1))
    with self.assertRaises(ValueError):
      config.bind_parameter('blacklisted_configurable.blacklisted', 0)
    with self.assertRaises(ValueError):
      config.bind_parameter('a/b/blacklisted_configurable.blacklisted', 0)

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

  def testRequiredInSignatureBlacklistWhitelist(self):
    expected_err_regexp = (
        r"Argument 'arg' of 'test_required_blacklist' \('<function .+>'\) "
        r'marked REQUIRED but blacklisted.')
    with self.assertRaisesRegex(ValueError, expected_err_regexp):
      config.external_configurable(
          lambda arg=config.REQUIRED: arg,
          'test_required_blacklist',
          blacklist=['arg'])
    expected_err_regexp = (
        r"Argument 'arg' of 'test_required_whitelist' \('<function .+>'\) "
        r'marked REQUIRED but not whitelisted.')
    with self.assertRaisesRegex(ValueError, expected_err_regexp):
      config.external_configurable(
          lambda arg=config.REQUIRED, arg2=4: arg,
          'test_required_whitelist',
          whitelist=['arg2'])

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
    @config.configurable(blacklist=['expected_value'])
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
    macros = list(config.iterate_references(config._CONFIG, to=config.macro))
    self.assertLen(macros, 3)

  def testInteractiveMode(self):
    @config.configurable('duplicate_fn')
    def duplicate_fn1():  # pylint: disable=unused-variable
      return 'duplicate_fn1'

    with self.assertRaisesRegex(ValueError, 'A configurable matching'):

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

    with self.assertRaisesRegex(ValueError, 'A configurable matching'):

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
      configurable2.non_kwarg = @batch_size/macro()
      configurable2.kwarg1 = @discriminator/num_layers/macro()
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
      ConfigurableClass.kwarg1 = @obj1/singleton()
      ConfigurableClass.kwarg2 = @obj2/singleton()
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

  def testQueryParameter(self):
    config.bind_parameter('whitelisted_configurable.whitelisted', 0)
    value = config.query_parameter('whitelisted_configurable.whitelisted')
    self.assertEqual(0, value)
    with self.assertRaises(ValueError):
      config.query_parameter('whitelisted_configurable.wrong_param')
    with self.assertRaises(ValueError):
      config.query_parameter('blacklisted_configurable.blacklisted')
    with self.assertRaises(ValueError):
      # Parameter not set.
      config.query_parameter('whitelisted_configurable.other')
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


if __name__ == '__main__':
  absltest.main()
