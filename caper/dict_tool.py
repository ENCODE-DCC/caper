"""dictTool: merge/split/flatten/unflatten dict

Author:
    Jin Lee (leepc12@gmail.com) at ENCODE-DCC
"""

import re
from collections import defaultdict

try:
    from collections.abc import MutableMapping
except AttributeError:
    from collections import MutableMapping


def merge_dict(a, b):
    """Merges b into a recursively. This mutates a and overwrites
    items in b on a for conflicts.

    Ref: https://stackoverflow.com/questions/7204805/dictionaries
    -of-dictionaries-merge/7205107#7205107
    """
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge_dict(a[key], b[key])
            elif a[key] == b[key]:
                pass
            else:
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a


def flatten_dict(d, reducer=None, parent_key=()):
    """Flattens dict into single-level-tuple-keyed dict with
        {(tuple of keys of parents and self): value}

    Args:
        reducer:
            Character to join keys in a tuple.
            If None, returns with key as a tuple.
    Returns:
        dict of {
            (key_lvl1, key_lvl2, key_lvl3, ...): value
        }
    """
    items = []
    for k, v in d.items():
        new_key = parent_key + (k if isinstance(k, tuple) else (k,))
        if isinstance(v, MutableMapping):
            items.extend(flatten_dict(v, parent_key=new_key).items())
        else:
            items.append((new_key, v))
    if reducer:
        return {reducer.join(k): v for k, v in type(d)(items).items()}
    else:
        return type(d)(items)


def recurse_dict_value(d, fnc):
    if isinstance(d, dict):
        for k, v in d.items():
            recurse_dict_value(v, fnc)

    elif isinstance(d, (list, tuple)):
        for v in d:
            recurse_dict_value(v, fnc)
    else:
        fnc(d)


def unflatten_dict(d_flat):
    """Unflattens single-level-tuple-keyed dict into dict
    """
    result = type(d_flat)()
    for k_tuple, v in d_flat.items():
        d_curr = result
        for i, k in enumerate(k_tuple):
            if i == len(k_tuple) - 1:
                d_curr[k] = v
            elif k not in d_curr:
                d_curr[k] = type(d_flat)()
            d_curr = d_curr[k]
    return result


def split_dict(d, rules=None):
    """Splits dict according to "rule"

    Returns:
        List of split dict

    Args:
        rule:
            A list of tuple (RULE_NAME: REGEX)

            If a key name in an JSON object matches with this REGEX
            then ALL objects with the same key will be separated from
            the original root JSON object while keeping their hierachy.
            RULE_NAME will be added to root of each new JSON object.

            For example, we have a JSON object like the following
            [
                {
                    "flagstat_qc": {
                        "rep1": {
                            "read1": 100,
                            "read2": 200
                        },
                        "rep2": {
                            "read1": 300,
                            "read2": 400
                        }
                    },
                    "etc": {
                        "samstat_qc": {
                            "rep1": {
                                "unmapped": 500,
                                "mapped": 600
                            },
                            "rep2": {
                                "unmapped": 700,
                                "mapped": 800
                            }
                        }
                    },
                    "idr_qc": {
                        "qc_test1" : 900
                    }
                }
            ]
            with "new_row_rule" = "replicate:^rep\\d+$", this JSON object
            will be splitted into three (original, rep1, rep2) JSON object.
            [
                # original
                {
                    "idr_qc": {
                        "qc_test1" : 900
                    }
                },
                # rep1
                {
                    "replicate": "rep1",
                    "flagstat_qc": {
                        "read1": 100,
                        "read2": 200
                    },
                    "etc": {
                        "samstat_qc": {
                            "unmapped": 500,
                            "mapped": 600
                        }
                    }
                },
                # rep2
                {
                    "replicate": "rep2",
                    "flagstat_qc": {
                        "read1": 300,
                        "read2": 400
                    },
                    "etc": {
                        "samstat_qc": {
                            "unmapped": 700,
                            "mapped": 800
                        }
                    }
                },
            ]
    """
    if rules is None:
        return [d]
    if isinstance(rules, tuple):
        rules = [rules]

    d_flat = flatten_dict(d)
    result = []
    keys_matched_regex = set()
    d_each_rule = defaultdict(type(d))
    for rule_name, rule_regex in rules:
        for k_tuple, v in d_flat.items():
            new_k_tuple = ()
            pattern_matched_k = None
            for k in k_tuple:
                if re.findall(rule_regex, k):
                    pattern_matched_k = (rule_name, k)
                else:
                    new_k_tuple += (k,)
            if pattern_matched_k is not None:
                d_each_rule[pattern_matched_k][new_k_tuple] = v
                keys_matched_regex.add(k_tuple)

    for (rule_name, k), d_each_matched in d_each_rule.items():
        d_ = unflatten_dict(d_each_matched)
        d_[rule_name] = k
        result.append(d_)

    d_others = type(d)()
    for k_tuple, v in d_flat.items():
        if k_tuple not in keys_matched_regex:
            d_others[k_tuple] = v
    if d_others:
        d_ = unflatten_dict(d_others)
        result = [d_] + result
    return result


def dict_to_dot_str(d, parent_key='digraph D', indent='', base_indent=''):
    """Dict will be converted into DOT like the followings:
        1) Value string will not be double-quotted in DOT.
            - make sure to escape double-quotes in a string with special characters
            (e.g. whitespace, # and ;)
        2) If "value" is None then "key" will be just added to DOT without "="

    dict:
        { "key1": "val1", "key2": "val2", "key3": { "key3_1": "val3_1", }... }

    dot:
        digraph D {
            key1 = val1;
            key2 = val2;
            key3 {
                key3_1 = val3_1;
                ...
            }
            ...
        }

    Example in a Croo output def JSON file:
        (note that strings for "label" are double-quote-escaped).

    dict:
        {
            "rankdir": "TD",
            "start": "[shape=Mdiamond]",
            "end": "[shape=Msquare]",
            "subgraph cluster_rep1": {
                "style": "filled",
                "color": "mistyrose",
                "label": "\"Replicate 1\""
            },
            "subgraph cluster_rep2": {
                "style": "filled",
                "color": "azure",
                "label": "\"Replicate 2\""
            },
            "a0 -> b0": null,
            "c0 -> d0": null
        }

    Such dict will be converted into a dot:

    dot:
        digraph D {
            rankDir = TD;
            start = [shape=Mdiamond];
            end = [shape=Msquare];
            subgraph cluster_rep1 {
                style = filled;
                color = mistyrose;
                label = "Replicate 1"
            };
            subgraph cluster_rep2 {
                style = filled;
                color = azure;
                label = "Replicate 2"
            };
            a0 -> b0;
            c0 -> d0;
        }
    """
    result = ''
    if d is None:
        return '{}{};\n'.format(base_indent, parent_key)
    elif isinstance(d, str):
        return '{}{} = {};\n'.format(base_indent, parent_key, d)
    elif isinstance(d, dict):
        result += base_indent + parent_key + ' {\n'
        for k, v in d.items():
            result += dict_to_dot_str(
                v, parent_key=k, indent=indent, base_indent=base_indent + indent
            )
        result += base_indent + '}\n'
    else:
        raise ValueError(
            'Unsupported data type: {} '
            '(only str and dict/JSON are allowed).'.format(type(d))
        )
    return result
