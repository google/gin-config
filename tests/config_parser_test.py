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

import ast
import pprint
import random
import typing
from typing import Any, Dict, Sequence, Tuple

from absl.testing import absltest

from gin import config_parser


def _generate_nested_value(max_depth=4, max_container_size=5):
  def generate_int():
    return random.randint(-10000, 10000)

  def generate_float():
    return random.random() * 10000 - 5000

  def generate_bool():
    return random.random() > 0.5

  def generate_none():
    return None

  def generate_string():
    length = random.randint(0, 10)
    quote = random.choice(['"', "'"])
    alphabet = 'abcdefghijklmnopqrstuvwxyz\\\'\" '
    contents = [random.choice(alphabet) for _ in range(length)]
    return quote + ''.join(contents) + quote

  def generate_list():
    length = random.randint(0, max_container_size + 1)
    return [_generate_nested_value(max_depth - 1) for _ in range(length)]

  def generate_tuple():
    return tuple(generate_list())

  def generate_dict():
    length = random.randint(0, max_container_size + 1)
    key_generators = [generate_int, generate_float, generate_string]
    return {
        random.choice(key_generators)(): _generate_nested_value(max_depth - 1)
        for _ in range(length)
    }

  generators = [
      generate_int, generate_float, generate_bool, generate_none,
      generate_string
  ]
  if max_depth > 0:
    generators.extend([generate_list, generate_tuple, generate_dict])

  return random.choice(generators)()


class _TestConfigurableReference(typing.NamedTuple):
  name: str
  evaluate: bool


class _TestMacro(typing.NamedTuple):
  name: str


class _TestParserDelegate(config_parser.ParserDelegate):

  def __init__(self, raise_error=False):
    self._raise_error = raise_error

  def configurable_reference(self, scoped_name, evaluate):
    if self._raise_error:
      raise ValueError('Unknown configurable.')
    return _TestConfigurableReference(scoped_name, evaluate)

  def macro(self, scoped_name):
    if self._raise_error:
      raise ValueError('Bad macro.')
    return _TestMacro(scoped_name)


class _ParsedConfig(typing.NamedTuple):
  config: Dict[Tuple[str, str], Dict[str, Any]]
  imports: Sequence[config_parser.ImportStatement]
  includes: Sequence[str]
  blocks: Sequence[config_parser.BlockDeclaration]


class ConfigParserTest(absltest.TestCase):

  def _parse_value(self, literal):
    parser = config_parser.ConfigParser(literal, _TestParserDelegate())
    return parser.parse_value()

  def _validate_against_literal_eval(self, literal):
    parsed_value = self._parse_value(literal)
    self.assertEqual(parsed_value, ast.literal_eval(literal))

  def _assert_raises_syntax_error(self, literal):
    with self.assertRaises(SyntaxError):
      self._parse_value(literal)

  def _parse_config(self,
                    config_str,
                    generate_unknown_reference_errors=False):
    parser = config_parser.ConfigParser(
        config_str, _TestParserDelegate(generate_unknown_reference_errors))

    config = {}
    imports = []
    includes = []
    blocks = []

    for statement in parser:
      if isinstance(statement, config_parser.BindingStatement):
        scope, selector, arg_name, value, _ = statement
        config.setdefault((scope, selector), {})[arg_name] = value
      elif isinstance(statement, config_parser.BlockDeclaration):
        blocks.append(statement)
      elif isinstance(statement, config_parser.ImportStatement):
        imports.append(statement)
      elif isinstance(statement, config_parser.IncludeStatement):
        includes.append(statement.filename)

    return _ParsedConfig(
        config=config, imports=imports, includes=includes, blocks=blocks)

  def testParseRandomLiterals(self):
    # Try a bunch of random nested Python structures and make sure we can parse
    # them back to the correct value.
    random.seed(42)
    for _ in range(1000):
      value = _generate_nested_value()
      literal = pprint.pformat(value)
      parsed_value = self._parse_value(literal)
      self.assertEqual(value, parsed_value)

  def testInvalidBasicType(self):
    with self.assertRaises(SyntaxError) as assert_raises:
      self._parse_config("""
        scope/some_fn.arg1 = None
        scope/some_fn.arg2 = Garbage  # <-- Not a valid Python value.
      """)
    self.assertEqual(assert_raises.exception.lineno, 3)
    self.assertEqual(assert_raises.exception.offset, 29)
    self.assertEqual(
        assert_raises.exception.text.strip(),
        'scope/some_fn.arg2 = Garbage  # <-- Not a valid Python value.')
    self.assertRegex(
        str(assert_raises.exception),
        r'malformed .*node.* or string.*: <_?ast.Name [^\n]+>\n'
        r"    Failed to parse token 'Garbage' \(line 3\)")

  def testUnknownConfigurableAndMacro(self):
    with self.assertRaisesRegex(ValueError, 'line 2\n.*@raise_an_error'):
      self._parse_config(
          '\n'.join([
              'some_fn.arg1 = None',
              'some_fn.arg2 = @raise_an_error',
          ]),
          generate_unknown_reference_errors=True)

    with self.assertRaisesRegex(ValueError, 'line 2\n.*%raise_an_error'):
      self._parse_config(
          '\n'.join([
              'some_fn.arg1 = None',
              'some_fn.arg2 = %raise_an_error',
          ]),
          generate_unknown_reference_errors=True)

  def testSyntaxCornerCases(self):
    # Trailing commas are ok.
    self._validate_against_literal_eval('[1, 2, 3,]')
    # Two trailing commas are not ok.
    self._assert_raises_syntax_error('[1, 2, 3,,]')

    # Parens without trailing comma is not a tuple.
    self._validate_against_literal_eval('(1)')
    # Parens with trailing comma is a tuple.
    self._validate_against_literal_eval('(1,)')

    # Newlines inside a container are ok.
    self._validate_against_literal_eval("""{
        1: 2, 3: 4
    }""")
    self._validate_against_literal_eval("""(-
        5)""")
    # Newlines outside a container are not ok.
    self._assert_raises_syntax_error("""
        [1, 2, 3]""")

    # Missing quotes are bad.
    self._assert_raises_syntax_error("'missing quote")

    # Adjacent strings concatenate.
    value = self._parse_value("""(
        'one ' 'two '
        'three'
    )""")
    # They also concatenate when doing explicit line continuation.
    self.assertEqual(value, 'one two three')
    value = self._parse_value(r"""'one ' \
        'two ' \
        'three'
    """)
    self.assertEqual(value, 'one two three')

    # Triple-quoted strings work fine.
    self._validate_against_literal_eval('''"""
      I'm a triple quoted string!
    """''')
    self._validate_against_literal_eval("""'''
      I'm a triple quoted string too!
    '''""")

  def testConfigurableReferences(self):
    configurable_reference = self._parse_value('@a/scoped/configurable')
    self.assertEqual(configurable_reference.name, 'a/scoped/configurable')
    self.assertFalse(configurable_reference.evaluate)

    configurable_reference = self._parse_value('@a/scoped/configurable()')
    self.assertEqual(configurable_reference.name, 'a/scoped/configurable')
    self.assertTrue(configurable_reference.evaluate)

    # Space after @ and around parens is ok, if hideous.
    configurable_reference = self._parse_value('@ a/scoped/configurable ( )')
    self.assertEqual(configurable_reference.name, 'a/scoped/configurable')
    self.assertTrue(configurable_reference.evaluate)

    configurable_reference = self._parse_value('@ configurable ( )')
    self.assertEqual(configurable_reference.name, 'configurable')
    self.assertTrue(configurable_reference.evaluate)

    # Spaces inside the configurable name or scope are verboten.
    self._assert_raises_syntax_error('@a / scoped /configurable')

    # Configurable references deep in the bowels of a nested structure work too.
    literal = """{
      'some key': [1, 2, (@a/reference(),)]
    }"""
    value = self._parse_value(literal)
    configurable_reference = value['some key'][2][0]
    self.assertEqual(configurable_reference.name, 'a/reference')
    self.assertTrue(configurable_reference.evaluate)

    # Test a list of configurable references.
    value = self._parse_value('[@ref1, @scoped/ref2, @ref3]')
    self.assertLen(value, 3)
    self.assertEqual(value[0].name, 'ref1')
    self.assertFalse(value[0].evaluate)
    self.assertEqual(value[1].name, 'scoped/ref2')
    self.assertFalse(value[1].evaluate)
    self.assertEqual(value[2].name, 'ref3')
    self.assertFalse(value[2].evaluate)

    # Test mix of configurable references with output references.
    value = self._parse_value('[@ref1(), @scoped/ref2(), @ref3]')
    self.assertLen(value, 3)
    self.assertEqual(value[0].name, 'ref1')
    self.assertTrue(value[0].evaluate)
    self.assertEqual(value[1].name, 'scoped/ref2')
    self.assertTrue(value[1].evaluate)
    self.assertEqual(value[2].name, 'ref3')
    self.assertFalse(value[2].evaluate)

    multiline = r"""[
      @ref1
    ]"""
    value = self._parse_value(multiline)
    self.assertLen(value, 1)
    self.assertEqual(value[0].name, 'ref1')
    self.assertFalse(value[0].evaluate)

  def testMacros(self):
    value = self._parse_value('%pele')
    self.assertIsInstance(value, _TestMacro)
    self.assertEqual(value.name, 'pele')

    value = self._parse_value('%one.two.three')
    self.assertIsInstance(value, _TestMacro)
    self.assertEqual(value.name, 'one.two.three')

    # Commit all kinds of atrocities with whitespace here.
    value_str = """[%ronaldinho,
      ( %robert/galbraith, {
        'Samuel Clemens':       %mark/twain,
        'Charles Dodgson':
%lewis/carroll     ,
'Eric Blair':            %george_orwell})
    ]"""
    expected_result = [
        _TestMacro('ronaldinho'), (_TestMacro('robert/galbraith'), {
            'Samuel Clemens': _TestMacro('mark/twain'),
            'Charles Dodgson': _TestMacro('lewis/carroll'),
            'Eric Blair': _TestMacro('george_orwell')
        })
    ]
    value = self._parse_value(value_str)
    self.assertEqual(value, expected_result)

    # But it doesn't do anything foul to newlines.
    still_an_error = """function.arg =
%macro"""
    with self.assertRaises(SyntaxError):
      self._parse_config(still_an_error)

  def testScopeAndSelectorFormat(self):
    config = self._parse_config("""
      a = 0
      a1.B2.c = 1
      scope/name = %macro
      scope/fn.param = %a.b  # Periods in macros are OK (e.g. for constants).
      a/scope/fn.param = 4
    """).config
    self.assertEqual(config['', 'a'], {'': 0})
    self.assertEqual(config['', 'a1.B2'], {'c': 1})
    self.assertEqual(config['scope', 'name'], {'': _TestMacro('macro')})
    self.assertEqual(config['scope', 'fn'], {'param': _TestMacro('a.b')})
    self.assertEqual(config['a/scope', 'fn'], {'param': 4})

    with self.assertRaises(SyntaxError):
      self._parse_config('1a = 3')
    with self.assertRaises(SyntaxError):
      self._parse_config('dotted.scope/name.value = 3')
    with self.assertRaises(SyntaxError):
      self._parse_config('a..b = 3')
    with self.assertRaises(SyntaxError):
      self._parse_config('a/.b = 3')
    with self.assertRaises(SyntaxError):
      self._parse_config('a/b. = 3')
    with self.assertRaises(SyntaxError):
      self._parse_config('a//b = 3')
    with self.assertRaises(SyntaxError):
      self._parse_config('//b = 3')

  def testParseImports(self):
    config_str = """
      import some.module.name  # Comment afterwards ok.
      import another.module.name
      import some.module.name as alias  # Comment afterwards ok.
      from another.module import name
      from some.module import name as alias  # Comment.
    """
    imports = self._parse_config(config_str).imports

    i = 0
    self.assertEqual(imports[i].module, 'some.module.name')
    self.assertFalse(imports[i].is_from)
    self.assertIsNone(imports[i].alias)
    self.assertEqual(imports[i].format(), 'import some.module.name')
    self.assertEqual(imports[i].bound_name(), 'some')
    self.assertEqual(imports[i].partial_path(), 'some')

    i += 1
    self.assertEqual(imports[i].module, 'another.module.name')
    self.assertFalse(imports[i].is_from)
    self.assertIsNone(imports[i].alias)
    self.assertEqual(imports[i].format(), 'import another.module.name')
    self.assertEqual(imports[i].bound_name(), 'another')
    self.assertEqual(imports[i].partial_path(), 'another')

    i += 1
    self.assertEqual(imports[i].module, 'some.module.name')
    self.assertFalse(imports[i].is_from)
    self.assertEqual(imports[i].alias, 'alias')
    self.assertEqual(imports[i].format(), 'import some.module.name as alias')
    self.assertEqual(imports[i].bound_name(), 'alias')
    self.assertEqual(imports[i].partial_path(), 'some.module.alias')

    i += 1
    self.assertEqual(imports[i].module, 'another.module.name')
    self.assertTrue(imports[i].is_from)
    self.assertIsNone(imports[i].alias)
    self.assertEqual(imports[i].format(), 'from another.module import name')
    self.assertEqual(imports[i].bound_name(), 'name')
    self.assertEqual(imports[i].partial_path(), 'another.module.name')

    i += 1
    self.assertEqual(imports[i].module, 'some.module.name')
    self.assertTrue(imports[i].is_from)
    self.assertEqual(imports[i].alias, 'alias')
    self.assertEqual(imports[i].format(),
                     'from some.module import name as alias')
    self.assertEqual(imports[i].bound_name(), 'alias')
    self.assertEqual(imports[i].partial_path(), 'some.module.alias')

    with self.assertRaises(SyntaxError):
      self._parse_config('import a.0b')
    with self.assertRaises(SyntaxError):
      self._parse_config('import a.b.')

  def testParseIncludes(self):
    config_str = """
      include 'a/file/path.gin'
      include "another/" "path.gin"
    """
    includes = self._parse_config(config_str).includes
    self.assertEqual(includes, ['a/file/path.gin', 'another/path.gin'])

    with self.assertRaises(SyntaxError):
      self._parse_config('include path/to/file.gin')
    with self.assertRaises(SyntaxError):
      self._parse_config('include None')
    with self.assertRaises(SyntaxError):
      self._parse_config('include 123')

  def testParseBindingBlock(self):
    config_str = """
      some/scope/module.Class:
        # arg1 does this.
        arg1 = None
        # arg2 does that.
        arg2 = {
          'nested': True,
          'containers': [1, 2, 3],
        }

      unscoped.function:
        arg = 3
    """
    parsed_config = self._parse_config(config_str)
    self.assertLen(parsed_config.blocks, 2)
    self.assertEqual(parsed_config.blocks[0].scope, 'some/scope')
    self.assertEqual(parsed_config.blocks[0].selector, 'module.Class')
    self.assertEqual(parsed_config.blocks[1].scope, '')
    self.assertEqual(parsed_config.blocks[1].selector, 'unscoped.function')
    self.assertEqual(
        parsed_config.config, {
            ('some/scope', 'module.Class'): {
                'arg1': None,
                'arg2': {
                    'nested': True,
                    'containers': [1, 2, 3]
                }
            },
            ('', 'unscoped.function'): {
                'arg': 3
            }
        })

  def testParseConfig(self):
    config_str = r"""
      # Leading comments are cool.

      import some.module.with.configurables
      import another.module.providing.configs

      include 'another/gin/file.gin'

      a/b/c/d.param_name = {
          'super sweet': 'multi line',
          'dictionary': '!',  # And trailing comments too.
      }

      include 'path/to/config/file.gin'

      # A binding block...
      some/scoped/module.Configurable:
        param_a = 'value_a'
      # Weirdly indented comment!
        param_b = {
          'key': 'value_b'
        }  # Comment at the end...
      # Unindented comment.

      # They work fine in the middle.
      import module

      # Line continuations are fine!
      moar.goodness = \
        ['a', 'moose']

      # And at the end!
    """
    parsed_config = self._parse_config(config_str)

    expected_config = {
        ('a/b/c', 'd'): {
            'param_name': {
                'super sweet': 'multi line',
                'dictionary': '!'
            }
        },
        ('some/scoped', 'module.Configurable'): {
            'param_a': 'value_a',
            'param_b': {
                'key': 'value_b'
            }
        },
        ('', 'moar'): {
            'goodness': ['a', 'moose']
        }
    }
    self.assertEqual(parsed_config.config, expected_config)

    imports = [imp.module for imp in parsed_config.imports]
    expected_imports = [
        'some.module.with.configurables', 'another.module.providing.configs',
        'module'
    ]
    self.assertEqual(imports, expected_imports)

    expected_includes = ['another/gin/file.gin', 'path/to/config/file.gin']
    self.assertEqual(parsed_config.includes, expected_includes)


if __name__ == '__main__':
  absltest.main()
