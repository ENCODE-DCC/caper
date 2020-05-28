import json
import os

from caper.caper_labels import CaperLabels


def test_create_file(tmp_path):
    d = tmp_path / 'test_caper_labels' / 'test_create_file'
    d.mkdir(parents=True)
    directory = str(d)

    cl = CaperLabels()

    backend = 'my_backend'

    custom_labels = d / 'my_custom_labels.json'
    custom_labels_dict = {'hello': 'world', 'good': {'bye': 'bro'}}
    custom_labels.write_text(json.dumps(custom_labels_dict, indent=4))

    str_label = 'my_str_label'
    user = 'my_user'
    basename = 'my_basename.json'

    f = cl.create_file(
        directory=directory,
        backend=backend,
        custom_labels=str(custom_labels),
        str_label=str_label,
        user=user,
        basename=basename,
    )

    with open(f) as fp:
        d = json.loads(fp.read())

    assert d[CaperLabels.KEY_CAPER_BACKEND] == backend
    assert d['hello'] == 'world'
    assert d['good']['bye'] == 'bro'
    assert d[CaperLabels.KEY_CAPER_STR_LABEL] == str_label
    assert d[CaperLabels.KEY_CAPER_USER] == user
    assert os.path.basename(f) == basename
    assert os.path.dirname(f) == directory
