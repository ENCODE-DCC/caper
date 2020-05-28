import os
from configparser import ConfigParser, MissingSectionHeaderError
from distutils.util import strtobool


def update_parser_defaults_with_conf(
    argparser,
    conf_file,
    conf_section='defaults',
    val_type=None,
    val_default=None,
    no_strip_quote=False,
):
    """Update argparse.ArgumentParser's defaults with key/val
    pairs in conf_file.

    This function does not work with a parser with subparsers
    (parser._subparsers).
    Therefore, call this function with each subparser itself.
    This function will update default of a key that exists in
    conf_file.

    It is important to convert string value in a conf file to a correct
    type defined in argparser's argument definition.

    However, argparse does not allow direct access to each argument's type.
    Therefore, this function tries to best-guess such type from
        - default value of argparse's argument.
        - val_type if it's given.
        - val_default if it's given.

    Args:
        argparser:
            argparse.ArgumentParser object to be updated with
            new defaults defined in conf_file.
        conf_file:
            Config file. This will override value for key
            conf_file_key_in_argparser in argparser.
        conf_section:
            Section in conf_file.
        val_type:
            {key: value's type} where key is a key in conf_file.
            If not defined, var's type can be guessed either from
            argparser's default value or from val_default.
            argparser's default will override all otehrs.
        val_default:
            {key: value's default} where key is a key in conf_file.
            Type can be guessed from argument's default value.
        no_strip_quote:
            Do not strip single/double quotes from values in conf_file.

    Returns:
        Updated parser.
    """
    conf_file = os.path.expanduser(conf_file)
    if not os.path.exists(conf_file):
        raise FileNotFoundError('conf_file does not exist. f={f}'.format(f=conf_file))

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
        if not no_strip_quote:
            v = v.strip('"\'')
        if v:
            defaults[k.replace('-', '_')] = v

    if val_default:
        for k, v in val_default.items():
            if k not in defaults:
                defaults[k] = None

    # used "is not None" for guessed_default to catch boolean false
    for k, v in defaults.items():
        if val_default and k in val_default:
            guessed_default = val_default[k]
        else:
            guessed_default = argparser.get_default(k)
        if val_type and k in val_type:
            guessed_type = val_type[k]
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
