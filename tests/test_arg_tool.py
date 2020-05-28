import argparse
from textwrap import dedent

from caper.arg_tool import update_parser_defaults_with_conf


def get_test_parser():
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


def test_update_parser_defaults_with_conf(tmp_path):
    """Check if this function correctly updates argparse parser's
    default values.
    """
    d = tmp_path / 'test_arg_tool' / 'test_update_parser_defaults_with_conf'
    d.mkdir(parents=True)

    val_type = {'param_w_type_wo_default2': float}
    val_default = {'param_w_type_wo_default3': 'hello', 'param_w_int_default3': 50}

    p1 = get_test_parser()
    c1 = d / 'c1.conf'

    # can mix up _ and -
    c1.write_text(
        dedent(
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
    """
        )
    )
    update_parser_defaults_with_conf(
        argparser=p1, conf_file=str(c1), val_type=val_type, val_default=val_default
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
