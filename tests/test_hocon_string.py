from copy import deepcopy
from textwrap import dedent

from caper.dict_tool import merge_dict
from caper.hocon_string import HOCONString

INCLUDE_CROMWELL = 'include required(classpath("application"))'


def get_test_hocon_str():
    hocon_str = dedent(
        """\
        include required(classpath("application"))
        backend {
          default = "gcp"
          providers {
            Local {
              actor-factory = "cromwell.backend.impl.sfs.config.ConfigBackendLifecycleActorFactory"
              config {
                default-runtime-attributes {
                  docker = "ubuntu:latest"
                }
                root = "/mnt/data/scratch/leepc12/caper_out"
              }
            }
          }
        }"""
    )
    return hocon_str


def get_test_hocon_str2():
    hocon_str2 = dedent(
        """\
        include required(classpath("application"))
        backend {
          providers {
            gcp {
              actor-factory = "GOOGLE"
            }
          }
        }"""
    )
    return hocon_str2


def get_test_dict():
    """Without "include" lines.
    """
    return {
        'backend': {
            'default': 'gcp',
            'providers': {
                'Local': {
                    'actor-factory': 'cromwell.backend.impl.sfs.config.ConfigBackendLifecycleActorFactory',
                    'config': {
                        'default-runtime-attributes': {'docker': 'ubuntu:latest'},
                        'root': '/mnt/data/scratch/leepc12/caper_out',
                    },
                }
            },
        }
    }


def get_test_dict2():
    """Without "include" lines.
    """
    return {'backend': {'providers': {'gcp': {'actor-factory': 'GOOGLE'}}}}


def test_from_dict():
    ref_d = get_test_dict()
    hs = HOCONString.from_dict(ref_d, include=INCLUDE_CROMWELL)
    print(str(hs))
    print(get_test_hocon_str())
    assert str(hs) == get_test_hocon_str()


def test_to_dict():
    hs = HOCONString(get_test_hocon_str())
    assert hs.to_dict() == get_test_dict()


def test_merge():
    s1 = get_test_hocon_str()
    s2 = get_test_hocon_str2()

    d1 = get_test_dict()
    d2 = get_test_dict2()
    dm = deepcopy(d1)
    merge_dict(dm, d2)

    hs1 = HOCONString(s1)
    hs2 = HOCONString(s2)
    hsm = HOCONString.from_dict(dm, include=INCLUDE_CROMWELL)

    assert str(hsm) == hs1.merge(hs2)
    assert str(hsm) == hs1.merge(d2)
    assert str(hsm) == hs1.merge(s2)


def test_get_include():
    s2 = get_test_hocon_str2()
    hs2 = HOCONString(s2)

    assert hs2.get_include() == INCLUDE_CROMWELL


def test_get_contents():
    s2 = get_test_hocon_str2()
    hs2 = HOCONString(s2)

    c2 = hs2.get_contents(without_include=False)
    assert c2 == s2

    c2_wo_i = hs2.get_contents(without_include=True)
    assert c2_wo_i == s2.replace(INCLUDE_CROMWELL + '\n', '')
