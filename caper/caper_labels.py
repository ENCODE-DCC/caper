import json
import logging
import os
import pwd

from autouri import AutoURI

from .dict_tool import merge_dict

logger = logging.getLogger(__name__)


class CaperLabels:
    KEY_CAPER_STR_LABEL = 'caper-str-label'
    KEY_CAPER_USER = 'caper-user'
    KEY_CAPER_BACKEND = 'caper-backend'
    BASENAME_LABELS = 'labels.json'

    def __init__(self):
        pass

    def create_file(
        self,
        directory,
        backend=None,
        custom_labels=None,
        str_label=None,
        user=None,
        basename=BASENAME_LABELS,
    ):
        """Create labels JSON file.

        Args:
            directory:
                Directory to create a labels JSON file.
            backend:
                Backend
            custom_labels:
                User's labels file to be merged.
            str_label:
                Caper's string label.
            basename:
                Basename of labels file.
        """
        template = {}

        if custom_labels:
            s = AutoURI(custom_labels).read()
            merge_dict(template, json.loads(s))

        if backend:
            template[CaperLabels.KEY_CAPER_BACKEND] = backend

        if str_label:
            template[CaperLabels.KEY_CAPER_STR_LABEL] = str_label

        template[CaperLabels.KEY_CAPER_USER] = (
            user if user else pwd.getpwuid(os.getuid())[0]
        )

        labels_file = os.path.join(directory, basename)
        AutoURI(labels_file).write(json.dumps(template, indent=4))

        return labels_file
