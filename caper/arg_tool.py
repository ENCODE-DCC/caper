import os
from argparse import ArgumentParser
from configparser import ConfigParser
from configparser import MissingSectionHeaderError
from distutils.util import strtobool


def update_parser_defaults_with_conf(
        argparser, conf_file,
        conf_section='defaults', strip_quote_in_conf=True,
        conf_val_type=None, conf_val_default=None):
    """Update argparse.ArgumentParser's defaults with key/val
    pairs in conf_file.

    This function does not work with a parser with subparsers
    (parser._subparsers).
    Therefore, call this function with each subparser itself.
    This function will update default of a key that exists in
    conf_file.

    Boolean flags (argument defined with action='store_true')
    must have default value with "False". For example, 

        parser.add_argument(
            '--verbose', action='store_true', default=False,
            help='Be verbose')

    If conf_val_type is not explicitly defined type can be
    guessed from argparser's default value.

    If conf_val_default is not explicitly defined then default
    can be taken from argparser's default value.

    Args:
        argparser:
            argparse.ArgumentParser object to be updated with
            new defaults defined in conf_file.
        conf_file:
            Config file. This will override value for key
            conf_file_key_in_argparser in argparser.
        conf_section:
            Section in conf_file.
        strip_quote_in_conf:
            Strip quotes from values in conf_file.
        conf_val_type:
            {key: value's type} where key is a key in conf_file.
            If not defined, var's type can be guessed either from 
            argparser's default value or from conf_val_default.
            argparser's default will override all otehrs.
        conf_val_default:
            {key: value's default} where key is a key in conf_file.
            Type can be guessed from argument's default value.

    Returns:
        Updated parser.
    """
    conf_file = os.path.expanduser(conf_file)
    if not os.path.exists(conf_file):
        raise FileNotFound(
            'conf_file does not exist. f={f}'.format(f=conf_file))

    config = ConfigParser()
    with open(conf_file) as fp:
        s = fp.read()
        try:
            config.read_string(s)
        except MissingSectionHeaderError:
            section = '[{sect}]\n'.format(sect=conf_section)
            config.read_string(section + s)
    d_ = dict(config.items(conf_section))
    defaults = {}
    for k, v in d_.items():
        if strip_quote_in_conf:
            v = v.strip('"\'')
        if v:
            defaults[k.replace('-', '_')] = v

    if conf_val_default:
        for k, v in conf_val_default.items():
            if k not in defaults:
                defaults[k] = None

    for k, v in defaults.items():
        if conf_val_default and k in conf_val_default:
            guessed_default = conf_val_default[k]
        else:
            guessed_default = argparser.get_default(k)

        if conf_val_type:
            guessed_type = conf_val_type[k]
        elif guessed_default is not None:
            guessed_type = type(guessed_default)
        else:
            guessed_type = None

        if v is None and guessed_default is not None:
            v = guessed_default
            defaults[k] = v

        if guessed_type:
            if guessed_type is bool and isinstance(v, str):
                defaults[k] = bool(strtobool(v))
            else:
                defaults[k] = guessed_type(v)

    argparser.set_defaults(**defaults)
