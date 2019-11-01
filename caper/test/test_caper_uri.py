#!/usr/bin/env python3
"""Tester for CaperURI

Author:
    Jin Lee (leepc12@gmail.com) at ENCODE-DCC
"""

import unittest
import os
import json

try:
    import caper
except:
    import sys, os
    script_path = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(os.path.join(script_path, '../'))
    import caper

from caper import caper_uri
from caper.caper_uri import CaperURI, URI_GCS, URI_LOCAL

class TestCaperURI(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestCaperURI, self).__init__(*args, **kwargs)
        caper_uri.init_caper_uri(
            tmp_dir='~/.caper/test/tmp_dir',
            tmp_s3_bucket='s3://encode-pipeline-test-runs/caper_tmp',
            tmp_gcs_bucket='gs://encode-pipeline-test-runs/caper_tmp',
            verbose=True)

    def test_deepcopy(self):
        tmp_json = {
            # 'file1' : 'gs://encode-pipeline-genome-data/hg38_chr19_chrM_caper.tsv',
            'file2' : 'string',
            'file3' : 'gs://xxx',
            'file3' : '~/.bashrc',
            'file4' : 's3://encode-pipeline-genome-data/hg38_chr19_chrM_aws.tsv',
        }
        tmp_json_file = os.path.expanduser('~/.caper/test/tmp.json')
        with open(tmp_json_file, 'w') as fp:
            fp.write(json.dumps(tmp_json, indent=4))
        f, _ = CaperURI(tmp_json_file).deepcopy(URI_GCS, uri_exts=('.tsv','.json'))
        print(f)
        # c.get_local_file()
        # c = CaperURI('gs://encode-pipeline-genome-data/hg38_chr19_chrM_caper.tsv').deepcopy(URI_LOCAL, uri_exts=('.tsv'))
        # c = CaperURI('https://storage.googleapis.com/encode-pipeline-genome-data/hg38_chr19_chrM_caper.tsv').deepcopy(URI_GCS, uri_exts=('.tsv'))
        # c = CaperURI('https://storage.googleapis.com/encode-pipeline-genome-data/hg38_chr19_chrM_caper.tsv').deepcopy(URI_GCS, uri_exts=('.tsv'))

if __name__ == '__main__':
    unittest.main()
