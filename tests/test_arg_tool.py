import argparse
from configparser import DuplicateOptionError
from textwrap import dedent

import pytest

from caper.arg_tool import read_from_conf, update_parsers_defaults_with_conf

CONF_CONTENTS = dedent(
    """\
    param-wo-default="please_remove_double_quote"
    param-w-type-wo-default='4.0'
    param-w-type-wo-default2="5.0"
    param_w_type_wo_default3=
    param-w-int-default=10
    param-w-int-default3=
    flag-w-default=True
    flag-w-default2='False'
    flag-wo-default='FALSE'
    flag-wo-default2="True"
    to_be-replaced=1
"""
)


CONF_CONTENTS_DUPLICATE_ENTRY = dedent(
    """\
    shared-param=200
    shared-param=400
    uniq-param-a=2000
    uniq-param-c=4
"""
)


CONF_CONTENTS_FOR_SUBPARSER = dedent(
    """\
    shared-param=600
    uniq-param-a=2000
    uniq-param-b=4000
    uniq-param-c=4
"""
)


@pytest.fixture
def parser_wo_subparsers():
    parser = argparse.ArgumentParser()
    parser.add_argument('--param-wo-default')
    parser.add_argument('--param-w-type-wo-default', type=float)
    parser.add_argument('--param-w-type-wo-default2', type=float)
    parser.add_argument('--param-w-type-wo-default3', type=float)
    parser.add_argument('--param-w-int-default', default=2)
    parser.add_argument('--param-w-int-default2', default=4)
    parser.add_argument('--param-w-int-default3', default=6)
    parser.add_argument('--flag-w-default', action='store_true', default=False)
    parser.add_argument('--flag-w-default2', action='store_true', default=False)
    parser.add_argument('--flag-wo-default', action='store_true')
    parser.add_argument('--flag-wo-default2', action='store_true')
    return parser


@pytest.fixture
def parser_with_subparsers():
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers(dest='action')

    p_sub_a = subparser.add_parser('a')
    p_sub_b = subparser.add_parser('b')

    # two subparsers will have shared and original parameters
    p_sub_a.add_argument('--shared-param', default=2)
    p_sub_a.add_argument('--uniq-param-a', default=20)

    p_sub_b.add_argument('--shared-param', default=4.0)
    p_sub_b.add_argument('--uniq-param-b', default=40.0)
    p_sub_b.add_argument('--uniq-param-c', type=int)

    return parser, [p_sub_a, p_sub_b]


def test_read_from_conf(tmp_path):
    c = tmp_path / 'c1.conf'
    c.write_text(CONF_CONTENTS)

    d1 = read_from_conf(
        c, no_strip_quote=False, conf_key_map={'to_be_replaced': 'replaced_key'}
    )
    assert d1['param_wo_default'] == 'please_remove_double_quote'
    assert d1['param_w_type_wo_default'] == '4.0'
    assert d1['param_w_type_wo_default2'] == '5.0'
    assert 'param_w_type_wo_default3' not in d1
    assert d1['param_w_int_default'] == '10'
    assert 'param_w_int_default3' not in d1
    assert d1['flag_w_default'] == 'True'
    assert d1['flag_w_default2'] == 'False'
    assert d1['flag_wo_default'] == 'FALSE'
    assert d1['flag_wo_default2'] == 'True'
    assert d1['replaced_key'] == '1'
    assert 'to_be-replaced' not in d1

    d2 = read_from_conf(c, no_strip_quote=True)
    assert d2['param_wo_default'] == '"please_remove_double_quote"'
    assert d2['param_w_type_wo_default2'] == '"5.0"'
    assert d2['flag_w_default2'] == '\'False\''
    assert d2['flag_wo_default'] == '\'FALSE\''
    assert d2['flag_wo_default2'] == '"True"'

    c2 = tmp_path / 'c2.conf'
    c2.write_text(CONF_CONTENTS_DUPLICATE_ENTRY)

    with pytest.raises(DuplicateOptionError):
        d2 = read_from_conf(c2)


def test_update_parsers_defaults_with_conf(tmp_path, parser_wo_subparsers):
    """Check if this function correctly updates argparse parser's
    default values.
    """
    val_type = {'param_w_type_wo_default2': float}
    val_default = {'param_w_type_wo_default3': 'hello', 'param_w_int_default3': 50}

    p1 = parser_wo_subparsers
    c1 = tmp_path / 'c1.conf'

    # can mix up _ and -
    c1.write_text(CONF_CONTENTS)
    d1 = update_parsers_defaults_with_conf(
        parsers=[p1], conf_file=str(c1), val_type=val_type, val_default=val_default
    )

    assert p1.get_default('param_wo_default') == 'please_remove_double_quote'
    assert p1.get_default('param_w_type_wo_default') == '4.0'
    assert p1.get_default('param_w_type_wo_default2') == 5.0
    assert p1.get_default('param_w_type_wo_default3') == 'hello'
    assert p1.get_default('param_w_int_default') == 10
    assert p1.get_default('param_w_int_default2') == 4
    assert p1.get_default('param_w_int_default3') == 50
    assert p1.get_default('flag_w_default')
    assert not p1.get_default('flag_w_default2')
    assert not p1.get_default('flag_wo_default')
    assert p1.get_default('flag_wo_default2')

    assert d1['param_wo_default'] == 'please_remove_double_quote'
    assert d1['param_w_type_wo_default'] == '4.0'
    assert d1['param_w_type_wo_default2'] == 5.0
    assert d1['param_w_type_wo_default3'] == 'hello'
    assert d1['param_w_int_default'] == 10
    assert 'param_w_int_default2' not in d1
    assert d1['param_w_int_default3'] == 50
    assert d1['flag_w_default']
    assert not d1['flag_w_default2']
    assert not d1['flag_wo_default']
    assert d1['flag_wo_default2']


def test_update_parsers_defaults_with_conf_with_subparsers(
    tmp_path, parser_with_subparsers
):
    """Check if this function correctly updates argparse parser's
    default values.
    """
    p, subparsers = parser_with_subparsers
    c1 = tmp_path / 'c1.conf'

    # can mix up _ and -
    c1.write_text(CONF_CONTENTS_FOR_SUBPARSER)
    d = update_parsers_defaults_with_conf(parsers=subparsers, conf_file=str(c1))
    args_a, _ = p.parse_known_args(['a'])
    args_b, _ = p.parse_known_args(['b'])

    assert args_a.shared_param == 600.0
    assert args_a.uniq_param_a == 2000

    assert args_b.shared_param == 600.0
    assert args_b.uniq_param_b == 4000.0
    # cannot parse "type" from argparse
    assert args_b.uniq_param_c == 4

    assert d['shared_param'] == 600.0
    assert d['uniq_param_a'] == 2000
    assert d['uniq_param_b'] == 4000.0
    assert d['uniq_param_c'] == '4'
