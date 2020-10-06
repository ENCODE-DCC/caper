import json
import logging
import os
import pwd
import re

from autouri import AutoURI

from .dict_tool import merge_dict

logger = logging.getLogger(__name__)


RE_ILLEGAL_STR_LABEL_CHRS = r'[\:\?\*]'
SUB_ILLEGAL_STR_LABEL_CHRS = '_'


class CaperLabels:
    KEY_CAPER_STR_LABEL = 'caper-str-label'
    KEY_CAPER_USER = 'caper-user'
    KEY_CAPER_BACKEND = 'caper-backend'
    BASENAME_LABELS = 'labels.json'

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
                Wildcards ('*' and '?') and ':' are not allowed by default.
                These will be replaced with '_' by default.
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
            new_str_label = re.sub(
                RE_ILLEGAL_STR_LABEL_CHRS, SUB_ILLEGAL_STR_LABEL_CHRS, str_label
            )
            if str_label != new_str_label:
                logger.warning(
                    'Found illegal characters in str_label matching with {regex}. '
                    'Replaced with {sub}'.format(
                        regex=RE_ILLEGAL_STR_LABEL_CHRS, sub=SUB_ILLEGAL_STR_LABEL_CHRS
                    )
                )
            template[CaperLabels.KEY_CAPER_STR_LABEL] = new_str_label

        template[CaperLabels.KEY_CAPER_USER] = (
            user if user else pwd.getpwuid(os.getuid())[0]
        )

        labels_file = os.path.join(directory, basename)
        AutoURI(labels_file).write(json.dumps(template, indent=4))

        return labels_file
