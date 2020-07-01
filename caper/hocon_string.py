import json
import logging
import re

from pyhocon import ConfigFactory, HOCONConverter

from .dict_tool import merge_dict

logger = logging.getLogger(__name__)


class HOCONString:
    RE_INCLUDE_LINE = r'^\s*include\s'

    def __init__(self, hocon_str):
        """Splits HOCON string into "include" lines and the rest.
        Ignore "include" lines while parsing it.
        """
        lines_include = []
        lines_wo_include = []
        for line in hocon_str.split('\n'):
            if re.findall(HOCONString.RE_INCLUDE_LINE, line):
                lines_include.append(line)
            else:
                lines_wo_include.append(line)

        self._include = '\n'.join(lines_include)
        self._contents_wo_include = '\n'.join(lines_wo_include)

    def __str__(self):
        return self.get_contents()

    @classmethod
    def from_dict(cls, d, include=''):
        hocon = ConfigFactory.from_dict(d)
        hocon_str = HOCONConverter.to_hocon(hocon)
        if include:
            hocon_str = include + '\n' + hocon_str
        return cls(hocon_str=hocon_str)

    def to_dict(self):
        """Convert contents without include to dict.
        """
        c = ConfigFactory.parse_string(self._contents_wo_include)
        j = HOCONConverter.to_json(c)
        return json.loads(j)

    def merge(self, b):
        if isinstance(b, HOCONString):
            d = b.to_dict()
        elif isinstance(b, str):
            d = HOCONString(b).to_dict()
        elif isinstance(b, dict):
            d = b
        else:
            raise TypeError('Unsupported type {t}'.format(t=type(b)))

        self_d = self.to_dict()
        merge_dict(self_d, d)

        hocon = ConfigFactory.from_dict(self_d)
        return self._include + '\n' + HOCONConverter.to_hocon(hocon)

    def get_include(self):
        return self._include

    def get_contents(self, without_include=False):
        if without_include:
            return self._contents_wo_include
        else:
            return self._include + '\n' + self._contents_wo_include
