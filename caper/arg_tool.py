import os
from argparse import ArgumentParser
from configparser import ConfigParser, MissingSectionHeaderError
from distutils.util import strtobool


def read_from_conf(
    conf_file, conf_section='defaults', conf_key_map=None, no_strip_quote=False
):
    """Read key/value from conf_section of conf_file.
    Hyphens (-) in keys will be replace with underscores (_).
    All keys and values are considered as strings.

    Use update_parser_defaults_with_conf (2nd return value)
    instead to get result with values converted to correct types.

    Args:
        conf_file:
            INI-like conf file to find defaults key/value.
        conf_section:
            Section in conf_file.
            If section doesn't exist then make one and set as default.
        conf_key_map:
            Mapping of keys parsed from conf file.
            This is useful if you want to replace an old key name with a new one.
            e.g. to make your code backward compatible when you want to
            change parameter's name.
        no_strip_quote:
            Do not strip single/double quotes from values in conf_file.

    Returns:
        Dict of key/value in configuration file.
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
    result = {}
    for k, v in d_.items():
        if not no_strip_quote:
            v = v.strip('"\'')
        if v:
            k_ = k.replace('-', '_')
            if conf_key_map and k_ in conf_key_map:
                k_ = conf_key_map[k_]
            result[k_] = v

    return result


def update_parsers_defaults_with_conf(
    parsers,
    conf_file,
    conf_section='defaults',
    conf_key_map=None,
    no_strip_quote=False,
    val_type=None,
    val_default=None,
):
    """Updates argparse.ArgumentParser's defaults with key/value pairs
    defined in conf_file. Also, returns a dict of key/values defined in
    conf_file with correct type for each value.

    Type of each value in conf_file can be guessed from:
        - default value of ArgumentParser's argument.
        - val_type if it's given.
        - val_default if it's given.
    Otherwise it is considered as string type since ArgumentParser
    does not allow direct access to each argument's type.
    Therefore, this function tries to best-guess such type.

    This function does not work recursively with subparsers.
    Therefore, call this function with each subparser to update each
    subparser's defaults.

    Args:
        parsers:
            List of argparse.ArgumentParser objects to be updated with
            new defaults defined in conf_file. Useful for subparsers.
        conf_file:
            See read_from_conf()
        conf_section:
            See read_from_conf()
        conf_key_map:
            See read_from_conf()
        no_strip_quote:
            See read_from_conf()
        val_type:
            {key: value's type} where key is a key in conf_file.
            If not defined, var's type can be guessed either from
            parser's default value or from val_default.
            parser's default will override all otehrs.
        val_default:
            {key: value's default} where key is a key in conf_file.
            Type can be guessed from argument's default value.

    Returns:
        Dict of key/value pair parsed from conf_file.
        Such value is converted into a correct type which is
        guessed from val_type, val_default and arguments' defaults
        defined in parsers.
    """
    if isinstance(parsers, ArgumentParser):
        parsers = [parsers]

    defaults = read_from_conf(
        conf_file=conf_file,
        conf_section=conf_section,
        conf_key_map=conf_key_map,
        no_strip_quote=no_strip_quote,
    )

    if val_default:
        for k, v in val_default.items():
            if k not in defaults:
                defaults[k] = None

    # used "is not None" for guessed_default to catch boolean false
    for k, v in defaults.items():
        if val_default and k in val_default:
            guessed_default = val_default[k]
        else:
            for p in parsers:
                guessed_default = p.get_default(k)
                if guessed_default:
                    break
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

    # update ArgumentParser's default and then return defaults dict
    for p in parsers:
        p.set_defaults(**defaults)
    return defaults
