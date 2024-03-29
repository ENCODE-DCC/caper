import logging
import os

from autouri import AbsPath, AutoURI, URIBase
from autouri.loc_aux import recurse_json

logger = logging.getLogger(__name__)


DEFAULT_COMMON_ROOT_SEARCH_LEVEL = 5


def find_bindpath(json_file, common_root_search_level=DEFAULT_COMMON_ROOT_SEARCH_LEVEL):
    """Recursively find paths to be bound for singularity.
    Find common roots for all files in an input JSON file.
    This function will recursively visit all values in input JSON and
    also JSON, TSV, CSV files in the input JSON itself.

    This function visit all files in input JSON.
    Files with some extensions (defined by Autouri's URIBase.LOC_RECURSE_EXT_AND_FNC)
    are recursively visited.

    Add all (but not too high level<4) parent directories
    to all_dirnames. start from original
    For example, we have /a/b/c/d/e/f/g/h with common_root_search_level = 5
        add all the followings:
        /a/b/c/d/e/f/g/h (org)
        /a/b/c/d/e/f/g
        /a/b/c/d/e/f
        /a/b/c/d/e
        /a/b/c/d (minimum level = COMMON_ROOT_SEARCH_LEVEL-1)

    Args:
        json_file:
            Input JSON file which have local paths in it.
            Non-path values will be just ignored.
        common_root_search_level:
            See above description.
    """
    json_contents = AutoURI(json_file).read()
    all_dirnames = []

    def find_dirname(s):
        u = AbsPath(s)
        if u.is_valid:
            for ext, recurse_fnc_for_ext in URIBase.LOC_RECURSE_EXT_AND_FNC.items():
                if u.ext == ext:
                    _, _ = recurse_fnc_for_ext(u.read(), find_dirname)
            # file can be a soft-link
            # singularity will want to have access to both soft-link and real one
            # so add dirnames of both soft-link and realpath
            all_dirnames.append(u.dirname)
            all_dirnames.append(os.path.dirname(os.path.realpath(u.uri)))
        return None, False

    _, _ = recurse_json(json_contents, find_dirname)

    all_dnames_incl_parents = set(all_dirnames)
    for d in all_dirnames:
        dir_arr = d.split(os.sep)
        for i, _ in enumerate(dir_arr[common_root_search_level:]):
            d_child = os.sep.join(dir_arr[: i + common_root_search_level])
            all_dnames_incl_parents.add(d_child)

    bindpaths = set()
    # remove overlapping directories
    for i, d1 in enumerate(sorted(all_dnames_incl_parents, reverse=True)):
        overlap_found = False
        for j, d2 in enumerate(sorted(all_dnames_incl_parents, reverse=True)):
            if i >= j:
                continue
            if d1.startswith(d2):
                overlap_found = True
                break
        if not overlap_found:
            bindpaths.add(d1)

    return ','.join(bindpaths)
