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

"""Provides a parser for Gin configuration files."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import abc
import ast
import collections
import io
import re
import tokenize

from gin import selector_map
from gin import utils

import six

# A regular expression matching a valid module identifier. A valid module
# identifier consists of one or more valid identifiers (see below), separated by
# periods (as in a Python module).
MODULE_RE = selector_map.SELECTOR_RE
# A regular expression matching valid identifiers. A valid identifier consists
# of a string beginning with an alphabet character or underscore, followed by
# any number of alphanumeric (or underscore) characters, as in Python.
IDENTIFIER_RE = re.compile(r'^[a-zA-Z_]\w*$')


class ParserDelegate(object):
  """A delegate object used to handle certain operations while parsing."""

  __metaclass__ = abc.ABCMeta

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


class BindingStatement(
    collections.namedtuple(
        'BindingStatement',
        ['scope', 'selector', 'arg_name', 'value', 'location'])):
  pass


class ImportStatement(
    collections.namedtuple('ImportStatement', ['module', 'location'])):
  pass


class IncludeStatement(
    collections.namedtuple('IncludeStatement', ['filename', 'location'])):
  pass


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

  _TOKEN_FIELDS = ['kind', 'value', 'begin', 'end', 'line']

  class Token(collections.namedtuple('Token', _TOKEN_FIELDS)):

    @property
    def line_number(self):
      return self.begin[0]

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
      if six.PY2:
        string_or_filelike = unicode(string_or_filelike)
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
    self._advance_one_token()

  def __iter__(self):
    return self

  def __next__(self):
    return self.next()

  @property
  def current_token(self):
    return self._current_token

  def next(self):
    statement = self.parse_statement()
    if statement:
      return statement
    raise StopIteration

  def parse_statement(self):
    """Parse a single statement.

    Returns:
      Either a `BindingStatement`, `ImportStatement`, `IncludeStatement`, or
      `None` if no more statements can be parsed (EOF reached).
    """
    self._skip_whitespace_and_comments()
    if self._current_token.kind == tokenize.ENDMARKER:
      return None

    # Save off location, but ignore char_num for any statement-level errors.
    stmt_loc = self._current_location(ignore_char_num=True)
    binding_key_or_keyword = self._parse_selector()
    statement = None
    if self._current_token.value != '=':
      if binding_key_or_keyword == 'import':
        module = self._parse_selector(scoped=False)
        statement = ImportStatement(module, stmt_loc)
      elif binding_key_or_keyword == 'include':
        str_loc = self._current_location()
        success, filename = self._maybe_parse_basic_type()
        if not success or not isinstance(filename, str):
          self._raise_syntax_error('Expected file path as string.', str_loc)
        statement = IncludeStatement(filename, stmt_loc)
      else:
        self._raise_syntax_error("Expected '='.")
    else:  # We saw an '='.
      self._advance_one_token()
      value = self.parse_value()
      scope, selector, arg_name = parse_binding_key(binding_key_or_keyword)
      statement = BindingStatement(scope, selector, arg_name, value, stmt_loc)

    assert statement, 'Internal parsing error.'

    if (self._current_token.kind != tokenize.NEWLINE and
        self._current_token.kind != tokenize.ENDMARKER):
      self._raise_syntax_error('Expected newline.')
    elif self._current_token.kind == tokenize.NEWLINE:
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
    self._current_token = ConfigParser.Token(*next(self._token_generator))
    # Certain symbols (e.g., "$") cause ERRORTOKENs on all preceding space
    # characters. Find the first non-space or non-ERRORTOKEN token.
    while (self._current_token.kind == tokenize.ERRORTOKEN and
           self._current_token.value in ' \t'):
      self._current_token = ConfigParser.Token(*next(self._token_generator))

  def advance_one_line(self):
    """Advances to next line."""

    current_line = self._current_token.line_number
    while current_line == self._current_token.line_number:
      self._current_token = ConfigParser.Token(*next(self._token_generator))

  def _skip_whitespace_and_comments(self):
    skippable_token_kinds = [
        tokenize.COMMENT, tokenize.NL, tokenize.INDENT, tokenize.DEDENT
    ]
    while self._current_token.kind in skippable_token_kinds:
      self._advance_one_token()

  def _advance(self):
    self._advance_one_token()
    self._skip_whitespace_and_comments()

  def _current_location(self, ignore_char_num=False):
    line_num, char_num = self._current_token.begin
    if ignore_char_num:
      char_num = None
    return (self._filename, line_num, char_num, self._current_token.line)

  def _raise_syntax_error(self, msg, location=None):
    if not location:
      location = self._current_location()
    raise SyntaxError(msg, location)

  def _parse_dict_item(self):
    key = self.parse_value()
    if self._current_token.value != ':':
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
    if self._current_token.kind != tokenize.NAME:
      self._raise_syntax_error('Unexpected token.')

    begin_line_num = self._current_token.begin[0]
    begin_char_num = self._current_token.begin[1]
    end_char_num = self._current_token.end[1]
    line = self._current_token.line

    selector_parts = []
    # This accepts an alternating sequence of NAME and '/' or '.' tokens.
    step_parity = 0
    while (step_parity == 0 and self._current_token.kind == tokenize.NAME or
           step_parity == 1 and self._current_token.value in ('/', '.')):
      selector_parts.append(self._current_token.value)
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

  def _maybe_parse_container(self):
    """Try to parse a container type (dict, list, or tuple)."""
    bracket_types = {
        '{': ('}', dict, self._parse_dict_item),
        '(': (')', tuple, self.parse_value),
        '[': (']', list, self.parse_value)
    }
    if self._current_token.value in bracket_types:
      open_bracket = self._current_token.value
      close_bracket, type_fn, parse_item = bracket_types[open_bracket]
      self._advance()

      values = []
      saw_comma = False
      while self._current_token.value != close_bracket:
        values.append(parse_item())
        if self._current_token.value == ',':
          saw_comma = True
          self._advance()
        elif self._current_token.value != close_bracket:
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
    if self._current_token.value == '-':
      token_value += self._current_token.value
      self._advance()

    basic_type_tokens = [tokenize.NAME, tokenize.NUMBER, tokenize.STRING]
    continue_parsing = self._current_token.kind in basic_type_tokens
    if not continue_parsing:
      return False, None

    while continue_parsing:
      token_value += self._current_token.value

      try:
        value = ast.literal_eval(token_value)
      except Exception as e:  # pylint: disable=broad-except
        err_str = "{}\n    Failed to parse token '{}'"
        self._raise_syntax_error(err_str.format(e, token_value))

      was_string = self._current_token.kind == tokenize.STRING
      self._advance()
      is_string = self._current_token.kind == tokenize.STRING
      continue_parsing = was_string and is_string

    return True, value

  def _maybe_parse_configurable_reference(self):
    """Try to parse a configurable reference (@[scope/name/]fn_name[()])."""
    if self._current_token.value != '@':
      return False, None

    location = self._current_location()
    self._advance_one_token()
    scoped_name = self._parse_selector(allow_periods_in_scope=True)

    evaluate = False
    if self._current_token.value == '(':
      evaluate = True
      self._advance()
      if self._current_token.value != ')':
        self._raise_syntax_error("Expected ')'.")
      self._advance_one_token()
    self._skip_whitespace_and_comments()

    with utils.try_with_location(location):
      reference = self._delegate.configurable_reference(scoped_name, evaluate)

    return True, reference

  def _maybe_parse_macro(self):
    """Try to parse an macro (%scope/name)."""
    if self._current_token.value != '%':
      return False, None

    location = self._current_location()
    self._advance_one_token()
    scoped_name = self._parse_selector(allow_periods_in_scope=True)

    with utils.try_with_location(location):
      macro = self._delegate.macro(scoped_name)

    return True, macro


def parse_scoped_selector(scoped_selector):
  """Parse scoped selector."""
  # Conver Macro (%scope/name) to (scope/name/macro.value)
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
