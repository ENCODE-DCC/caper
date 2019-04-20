#!/usr/bin/env python
"""
Cromweller Utils: Libraries for Cromweller
"""

from cromweller_uri import CromwellerURI
from logged_bash_cli import bash_run_cmd


class CromwellerBackend(object):
    """Backends for Cromweller

    Supported backend types
        local: using local filesystem
        gc: using gcs (google cloud storage) bucket
        aws: using s3 bucket
    """
    

    def __init__(self, backend_type, out, tmp):
        self.backend_type = backend_type
        self.active = False
        
        if out is not None:
            self.out_dir = CromwellerURI(out)
            self.active = True
        if tmp is not None:
            self.tmp_dir = CromwellerURI(tmp)

def main():
    pass

if __name__ == '__main__':
    main()
