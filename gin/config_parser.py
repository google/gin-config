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

"""Provides a parser for Gin configuration files."""

import abc
import ast
import collections
import contextlib
import io
import re
import tokenize
import typing
from typing import Any, Optional, Sequence, Tuple

from gin import selector_map
from gin import utils

# A regular expression matching a valid module identifier. A valid module
# identifier consists of one or more valid identifiers (see below), separated by
# periods (as in a Python module).
MODULE_RE = selector_map.SELECTOR_RE
# A regular expression matching valid identifiers. A valid identifier consists
# of a string beginning with an alphabet character or underscore, followed by
# any number of alphanumeric (or underscore) characters, as in Python.
IDENTIFIER_RE = re.compile(r'^[a-zA-Z_]\w*$')


class ParserDelegate(metaclass=abc.ABCMeta):
  """A delegate object used to handle certain operations while parsing."""

  @abc.abstractmethod
  def configurable_reference(self, scoped_configurable_name, evaluate):
    """Called to construct an object representing a configurable reference.

    Args:
      scoped_configurable_name: The name of the configurable reference,
        including all scopes.
      evaluate: Whether the configurable reference should be evaluated.

    Returns:
      Should return an object representing the configurable reference.
    """
    pass

  @abc.abstractmethod
  def macro(self, macro_name):
    """Called to construct an object representing an macro.

    Args:
      macro_name: The name of the macro, including all scopes.

    Returns:
      Should return an object representing the macro.
    """
    pass


class Location(typing.NamedTuple):
  filename: Optional[str]
  line_num: int
  char_num: Optional[int]
  line_content: str


class BindingStatement(typing.NamedTuple):
  scope: str
  selector: str
  arg_name: str
  value: Any
  location: Location


class ImportStatement(typing.NamedTuple):
  """Represents an import statement."""
  module: str
  is_from: bool
  alias: Optional[str]
  location: Location

  def format(self):
    if self.is_from:
      from_module, import_name = self.module.rsplit('.', maxsplit=1)
      output = f'from {from_module} import {import_name}'
    else:
      output = f'import {self.module}'
    if self.alias:
      output += f' as {self.alias}'
    return output

  def bound_name(self):
    if self.alias:
      return self.alias
    parts = self.module.split('.')
    return parts[-1] if self.is_from else parts[0]

  def partial_path(self):
    if self.alias:
      parts = self.module.split('.')
      parts[-1] = self.alias
      return '.'.join(parts)
    elif self.is_from:
      return self.module
    else:  # not self.is_from and not self.alias
      return self.module.split('.')[0]


class IncludeStatement(typing.NamedTuple):
  filename: str
  location: Location


class BlockDeclaration(typing.NamedTuple):
  scope: str
  selector: str
  location: Location


class ConfigParser(object):
  """A parser for configuration files/strings.

  This class implements a recursive descent parser for (sequences of) parameter
  binding strings. Each parameter binding string has the form:

      maybe/some/scope/configurable_name.parameter_name = value

  The `value` above may be any legal Python literal (list, tuple, dict, string,
  number, boolean, or None). Additionally, a "configurable reference" literal is
  supported, with the syntax

      @maybe/some/scope/configurable_name

  or

      @maybe/some/scope/configurable_name()

  The first form represents a reference to the configurable function itself,
  whereas the second form represents the result of calling the configurable
  function.

  This class doesn't assume a specific type for configurable function
  references, and instead allows the type to be specified at construction time.

  The primary method that should be called is `parse_binding`, which parses one
  parameter binding string. Additionally, a `parse_value` function is provided
  which just parses a literal value.

  This class implements the iterator interface, which makes it easy to iterate
  over multiple parameter bindings (newline separated) in a given file/string.

  Example:

      class DummyConfigurableReferenceType(object):
        def __init__(self, scoped_configurable_name, evaluate):
          pass

      f = open('/path/to/file.config')
      parser = config_parser.ConfigParser(f, DummyConfigurableReferenceType)
      config = {}
      for scoped_configurable_name, parameter_name, value in parser:
        config.setdefault(scoped_configurable_name, {})[parameter_name] = value
      f.close()
  """

  def __init__(self, string_or_filelike, parser_delegate):
    """Construct the parser.

    Args:
      string_or_filelike: Either the string to parse, or a file-like object
        supporting the readline method.
      parser_delegate: An instance of the ParserDelegate class, that will be
        responsible for constructing appropriate objects for configurable
        references and macros.
    """
    if hasattr(string_or_filelike, 'readline'):
      line_reader = string_or_filelike.readline
    else:  # Assume it's string-like.
      string_io = io.StringIO(string_or_filelike)
      line_reader = string_io.readline

    def _text_line_reader():
      line = line_reader()
      if isinstance(line, bytes):
        line = line.decode('utf8')
      return line

    self._token_generator = tokenize.generate_tokens(_text_line_reader)
    self._filename = getattr(string_or_filelike, 'name', None)
    self._current_token = None
    self._delegate = parser_delegate
    self._within_block = False
    self._statements_queue = collections.deque()
    self._advance_one_token()

  def __iter__(self):
    return self

  def __next__(self):
    statement = self.parse_statement()
    if statement:
      return statement
    raise StopIteration

  @property
  def current_token(self):
    return self._current_token

  def parse_statement(self):
    """Parse a single statement.

    Returns:
      Either a `BindingStatement`, `ImportStatement`, `IncludeStatement`, or
      `None` if no more statements can be parsed (EOF reached).
    """
    if self._statements_queue:
      return self._statements_queue.popleft()

    self._skip_whitespace_and_comments()
    if self._current_token.type == tokenize.ENDMARKER:
      return None

    # Save off location, but ignore char_num for any statement-level errors.
    stmt_loc = self._current_location(ignore_char_num=True)
    binding_key_or_keyword = self._parse_selector()
    statement = None
    if self._current_token.string == '=':
      self._advance_one_token()
      value = self.parse_value()
      scope, selector, arg_name = parse_binding_key(binding_key_or_keyword)
      statement = BindingStatement(scope, selector, arg_name, value, stmt_loc)
    elif self._current_token.string == ':':
      statement, bindings = self._parse_binding_block(
          binding_key_or_keyword, block_location=stmt_loc)
      self._statements_queue.extend(bindings)
    elif binding_key_or_keyword in ('import', 'from'):
      statement = self._parse_import(binding_key_or_keyword, stmt_loc)
    elif binding_key_or_keyword == 'include':
      str_loc = self._current_location()
      success, filename = self._maybe_parse_basic_type()
      if not success or not isinstance(filename, str):
        self._raise_syntax_error('Expected file path as string.', str_loc)
      statement = IncludeStatement(filename, stmt_loc)
    else:
      self._raise_syntax_error("Couldn't parse statement, expected ':' or '='.")

    assert statement, 'Internal parsing error.'

    end_types = (tokenize.NEWLINE, tokenize.DEDENT, tokenize.ENDMARKER)
    if self._current_token.type not in end_types:
      self._raise_syntax_error('Expected newline.')

    if self._current_token.type != tokenize.ENDMARKER:
      self._advance_one_token()

    return statement

  def parse_value(self):
    """Parse a single literal value.

    Returns:
      The parsed value.
    """
    parsers = [
        self._maybe_parse_container, self._maybe_parse_basic_type,
        self._maybe_parse_configurable_reference, self._maybe_parse_macro
    ]
    for parser in parsers:
      success, value = parser()
      if success:
        return value
    self._raise_syntax_error('Unable to parse value.')

  def _advance_one_token(self):
    self._current_token = next(self._token_generator)
    # Certain symbols (e.g., "$") cause ERRORTOKENs on all preceding space
    # characters. Find the first non-space or non-ERRORTOKEN token.
    while (self._current_token.type == tokenize.ERRORTOKEN and
           self._current_token.string in ' \t'):
      self._current_token = next(self._token_generator)

  def advance_one_line(self):
    """Advances to next line."""

    current_line = self._current_token.start[0]  # Line number.
    while current_line == self._current_token.start[0]:
      self._current_token = next(self._token_generator)

  @contextlib.contextmanager
  def _block_scope(self):
    self._within_block = True
    try:
      yield
    finally:
      self._within_block = False

  def _skip_whitespace_and_comments(self):
    skippable_tokens = [tokenize.COMMENT, tokenize.NL]
    if not self._within_block:
      skippable_tokens.extend([tokenize.INDENT, tokenize.DEDENT])
    self._skip(skippable_tokens)

  def _advance(self):
    self._advance_one_token()
    self._skip_whitespace_and_comments()

  def _current_location(self, ignore_char_num=False):
    line_num, char_num = self._current_token.start
    if ignore_char_num:
      char_num = None
    return Location(
        filename=self._filename,
        line_num=line_num,
        char_num=char_num,
        line_content=self._current_token.line)

  def _raise_syntax_error(self, msg, location=None):
    if not location:
      location = self._current_location()
    raise SyntaxError(msg, location)

  def _expect(self, expected, err_msg):
    """Check that the current token is `expected`, otherwise raise `err_msg`."""
    if isinstance(expected, str):
      actual = self._current_token.string
    elif isinstance(expected, int):
      actual = self._current_token.type
    if actual != expected:
      actual_type_name = tokenize.tok_name[self._current_token.type]
      actual_value = self._current_token.string
      received = f'  Got {actual_type_name} = {actual_value}.'
      self._raise_syntax_error(err_msg + received)
    self._advance_one_token()

  def _skip(self, skippable_token_types):
    while self._current_token.type in skippable_token_types:
      self._advance_one_token()

  def _parse_dict_item(self):
    key = self.parse_value()
    if self._current_token.string != ':':
      self._raise_syntax_error("Expected ':'.")
    self._advance()
    value = self.parse_value()
    return key, value

  def _parse_selector(self, scoped=True, allow_periods_in_scope=False):
    """Parse a (possibly scoped) selector.

    A selector is a sequence of one or more valid Python-style identifiers
    separated by periods (see also `SelectorMap`). A scoped selector is a
    selector that may be preceded by scope names (separated by slashes).

    Args:
      scoped: Whether scopes are allowed.
      allow_periods_in_scope: Whether to allow period characters in the scope
        names preceding the selector.

    Returns:
      The parsed selector (as a string).

    Raises:
      SyntaxError: If the scope or selector is malformatted.
    """
    if self._current_token.type != tokenize.NAME:
      self._raise_syntax_error('Unexpected token.')

    begin_line_num = self._current_token.start[0]
    begin_char_num = self._current_token.start[1]
    end_char_num = self._current_token.end[1]
    line = self._current_token.line

    selector_parts = []
    # This accepts an alternating sequence of NAME and '/' or '.' tokens.
    step_parity = 0
    while (step_parity == 0 and self._current_token.type == tokenize.NAME or
           step_parity == 1 and self._current_token.string in ('/', '.')):
      selector_parts.append(self._current_token.string)
      step_parity = not step_parity
      end_char_num = self._current_token.end[1]
      self._advance_one_token()
    self._skip_whitespace_and_comments()

    # Due to tokenization, most whitespace has been stripped already. To prevent
    # whitespace inside the scoped selector, we verify that it matches an
    # untokenized version of the selector obtained from the first through last
    # character positions of the consumed tokens in the line being parsed.
    scoped_selector = ''.join(selector_parts)
    untokenized_scoped_selector = line[begin_char_num:end_char_num]
    # Also check that it's properly formatted (e.g., no consecutive slashes).
    scope_re = IDENTIFIER_RE
    if allow_periods_in_scope:
      scope_re = MODULE_RE
    selector_re = MODULE_RE

    scope_parts = scoped_selector.split('/')
    valid_format = all(scope_re.match(scope) for scope in scope_parts[:-1])
    valid_format &= bool(selector_re.match(scope_parts[-1]))
    valid_format &= bool(scoped or len(scope_parts) == 1)
    if untokenized_scoped_selector != scoped_selector or not valid_format:
      location = (self._filename, begin_line_num, begin_char_num + 1, line)
      self._raise_syntax_error('Malformatted scope or selector.', location)

    return scoped_selector

  def _parse_identifier(self):
    identifier = self._current_token.string
    if not IDENTIFIER_RE.match(identifier):
      self._raise_syntax_error('Invalid identifier name.')
    self._advance()
    return identifier

  def _parse_import(self, keyword: str, statement_location: Location):
    """Parses a single import statement."""
    alias = None
    if keyword == 'import':
      module = self._parse_selector(scoped=False)
    elif keyword == 'from':
      module = self._parse_selector(scoped=False)
      self._expect('import', "Expected 'import'.")
      submodule = self._parse_identifier()
      module = f'{module}.{submodule}'
    if self._current_token.string == 'as':
      self._advance_one_token()
      alias = self._parse_identifier()

    return ImportStatement(
        module=module,
        is_from=keyword == 'from',
        alias=alias,
        location=statement_location)

  def _parse_binding_block(
      self, scoped_selector, block_location: Location
  ) -> Tuple[BlockDeclaration, Sequence[BindingStatement]]:
    """Parses a single binding block (indented group of binding statements)."""
    self._expect(':', "Expected ':'.")
    self._skip([tokenize.COMMENT])
    self._expect(tokenize.NEWLINE, 'Expected newline.')
    self._skip([tokenize.COMMENT, tokenize.NL])
    self._expect(tokenize.INDENT, 'Expected indentation.')
    self._skip([tokenize.COMMENT, tokenize.NL])

    scope, selector = parse_scoped_selector(scoped_selector)
    block_declaration = BlockDeclaration(
        scope=scope, selector=selector, location=block_location)

    bindings = []
    with self._block_scope():
      while self._current_token.type != tokenize.DEDENT:
        binding_location = self._current_location()
        arg_name = self._parse_identifier()
        self._expect('=', "Expected '='.")
        value = self.parse_value()
        binding = BindingStatement(
            scope=scope,
            selector=selector,
            arg_name=arg_name,
            value=value,
            location=binding_location)
        bindings.append(binding)
        self._expect(tokenize.NEWLINE, 'Expected newline.')
        self._skip_whitespace_and_comments()

    return block_declaration, bindings

  def _maybe_parse_container(self):
    """Try to parse a container type (dict, list, or tuple)."""
    bracket_types = {
        '{': ('}', dict, self._parse_dict_item),
        '(': (')', tuple, self.parse_value),
        '[': (']', list, self.parse_value)
    }
    if self._current_token.string in bracket_types:
      open_bracket = self._current_token.string
      close_bracket, type_fn, parse_item = bracket_types[open_bracket]
      self._advance()

      values = []
      saw_comma = False
      while self._current_token.string != close_bracket:
        values.append(parse_item())
        if self._current_token.string == ',':
          saw_comma = True
          self._advance()
        elif self._current_token.string != close_bracket:
          self._raise_syntax_error("Expected ',' or '%s'." % close_bracket)

      # If it's just a single value enclosed in parentheses without a trailing
      # comma, it's not a tuple, so just grab the value.
      if type_fn is tuple and len(values) == 1 and not saw_comma:
        type_fn = lambda x: x[0]

      self._advance()
      return True, type_fn(values)

    return False, None

  def _maybe_parse_basic_type(self):
    """Try to parse a basic type (str, bool, number)."""
    token_value = ''
    # Allow a leading dash to handle negative numbers.
    if self._current_token.string == '-':
      token_value += self._current_token.string
      self._advance()

    basic_type_tokens = [tokenize.NAME, tokenize.NUMBER, tokenize.STRING]
    continue_parsing = self._current_token.type in basic_type_tokens
    if not continue_parsing:
      return False, None

    while continue_parsing:
      token_value += self._current_token.string

      try:
        value = ast.literal_eval(token_value)
      except Exception as e:  # pylint: disable=broad-except
        err_str = "{}\n    Failed to parse token '{}'"
        self._raise_syntax_error(err_str.format(e, token_value))

      was_string = self._current_token.type == tokenize.STRING
      self._advance()
      is_string = self._current_token.type == tokenize.STRING
      continue_parsing = was_string and is_string

    return True, value

  def _maybe_parse_configurable_reference(self):
    """Try to parse a configurable reference (@[scope/name/]fn_name[()])."""
    if self._current_token.string != '@':
      return False, None

    location = self._current_location()
    self._advance_one_token()
    scoped_name = self._parse_selector(allow_periods_in_scope=True)

    evaluate = False
    if self._current_token.string == '(':
      evaluate = True
      self._advance()
      if self._current_token.string != ')':
        self._raise_syntax_error("Expected ')'.")
      self._advance_one_token()
    self._skip_whitespace_and_comments()

    with utils.try_with_location(location):
      reference = self._delegate.configurable_reference(scoped_name, evaluate)

    return True, reference

  def _maybe_parse_macro(self):
    """Try to parse an macro (%scope/name)."""
    if self._current_token.string != '%':
      return False, None

    location = self._current_location()
    self._advance_one_token()
    scoped_name = self._parse_selector(allow_periods_in_scope=True)

    with utils.try_with_location(location):
      macro = self._delegate.macro(scoped_name)

    return True, macro


def parse_scoped_selector(scoped_selector):
  """Parse scoped selector."""
  # Convert Macro (%scope/name) to (scope/name/macro.value)
  if scoped_selector[0] == '%':
    if scoped_selector.endswith('.value'):
      err_str = '{} is invalid cannot use % and end with .value'
      raise ValueError(err_str.format(scoped_selector))
    scoped_selector = scoped_selector[1:] + '/macro.value'
  scope_selector_list = scoped_selector.rsplit('/', 1)
  scope = ''.join(scope_selector_list[:-1])
  selector = scope_selector_list[-1]
  return scope, selector


def parse_binding_key(binding_key):
  scope, selector = parse_scoped_selector(binding_key)
  selector_arg_name_list = selector.rsplit('.', 1)
  selector = ''.join(selector_arg_name_list[0])
  arg_name = ''.join(selector_arg_name_list[1:])
  return scope, selector, arg_name
