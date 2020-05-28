from textwrap import dedent

from caper.dict_tool import (
    dict_to_dot_str,
    flatten_dict,
    merge_dict,
    split_dict,
    unflatten_dict,
)


def test_merge_dict():
    d1 = {
        'flagstat_qc': {'rep1': {'read1': 100}, 'rep2': {'read2': 400}},
        'etc': {'samstat_qc': {'rep1': {'unmapped': 500, 'mapped': 600}}},
    }
    d2 = {
        'flagstat_qc': {'rep1': {'read2': 200}, 'rep2': {'read1': 300}},
        'etc': {'samstat_qc': {'rep2': {'unmapped': 700, 'mapped': 800}}},
        'idr_qc': {'qc_test1': 900},
    }

    assert merge_dict(d1, d2) == {
        'flagstat_qc': {
            'rep1': {'read1': 100, 'read2': 200},
            'rep2': {'read1': 300, 'read2': 400},
        },
        'etc': {
            'samstat_qc': {
                'rep1': {'unmapped': 500, 'mapped': 600},
                'rep2': {'unmapped': 700, 'mapped': 800},
            }
        },
        'idr_qc': {'qc_test1': 900},
    }


def test_flatten_dict():
    d = {
        'flagstat_qc': {
            'rep1': {'read1': 100, 'read2': 200},
            'rep2': {'read1': 300, 'read2': 400},
        },
        'rep': 1,
    }
    assert flatten_dict(d) == {
        ('flagstat_qc', 'rep1', 'read1'): 100,
        ('flagstat_qc', 'rep1', 'read2'): 200,
        ('flagstat_qc', 'rep2', 'read1'): 300,
        ('flagstat_qc', 'rep2', 'read2'): 400,
        ('rep',): 1,
    }


def test_unflatten_dict():
    d_f = {
        ('flagstat_qc', 'rep1', 'read1'): 100,
        ('flagstat_qc', 'rep1', 'read2'): 200,
        ('flagstat_qc', 'rep2', 'read1'): 300,
        ('flagstat_qc', 'rep2', 'read2'): 400,
        ('rep',): 1,
    }
    assert unflatten_dict(d_f) == {
        'flagstat_qc': {
            'rep1': {'read1': 100, 'read2': 200},
            'rep2': {'read1': 300, 'read2': 400},
        },
        'rep': 1,
    }


def test_split_dict():
    d = {
        'flagstat_qc': {
            'rep1': {'read1': 100, 'read2': 200},
            'rep2': {'read1': 300, 'read2': 400},
        },
        'etc': {
            'samstat_qc': {
                'rep1': {'unmapped': 500, 'mapped': 600},
                'rep2': {'unmapped': 700, 'mapped': 800},
            }
        },
        'idr_qc': {'qc_test1': 900},
    }
    splits = split_dict(d, ('replicate', r'^rep\d+$'))
    splits_ref = [
        {'idr_qc': {'qc_test1': 900}},
        {
            'flagstat_qc': {'read1': 100, 'read2': 200},
            'etc': {'samstat_qc': {'unmapped': 500, 'mapped': 600}},
            'replicate': 'rep1',
        },
        {
            'flagstat_qc': {'read1': 300, 'read2': 400},
            'etc': {'samstat_qc': {'unmapped': 700, 'mapped': 800}},
            'replicate': 'rep2',
        },
    ]
    assert splits == splits_ref


def test_dict_to_dot_str():
    d = {
        'rankDir': 'TD',
        'start': '[shape=Mdiamond]',
        'end': '[shape=Msquare]',
        'subgraph cluster_rep1': {
            'style': 'filled',
            'color': 'mistyrose',
            'label': '"Replicate 1"',
        },
        'subgraph cluster_rep2': {
            'style': 'filled',
            'color': 'azure',
            'label': '"Replicate 2"',
        },
        'a0 -> b0': None,
        'c0 -> d0': None,
    }
    dot = dict_to_dot_str(d, parent_key='digraph D', indent=' ' * 4)
    ref = dedent(
        """\
        digraph D {
            rankDir = TD;
            start = [shape=Mdiamond];
            end = [shape=Msquare];
            subgraph cluster_rep1 {
                style = filled;
                color = mistyrose;
                label = "Replicate 1";
            }
            subgraph cluster_rep2 {
                style = filled;
                color = azure;
                label = "Replicate 2";
            }
            a0 -> b0;
            c0 -> d0;
        }
    """
    )
    assert dot == ref
