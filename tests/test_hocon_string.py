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


def get_test_hocon_str_multiple_includes():
    return dedent(
        """\
        include required(classpath("application"))
        include required(file("application"))
        include required(url("application"))
        include required("application.conf")
        level1 {
          include file("/srv/test.conf")
          level2 {
            include url("http://ok.com/test.conf")
            level3 {
              include classpath("test")
              level4 {
                include "test.conf"
                level5 {
                  include "test.hocon"
                }
              }
            }
          }
        }"""
    )


def get_test_dict(with_include=False):
    base_dict = {
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
    if with_include:
        base_dict[
            'HOCONSTRING_INCLUDE_ad5c3c187d5107c099f66681f1896c70'
        ] = 'include required(classpath("application"))'

    return base_dict


def get_test_dict2():
    """Without "include" lines.
    """
    return {'backend': {'providers': {'gcp': {'actor-factory': 'GOOGLE'}}}}


def get_test_multiple_includes(with_include=False):
    if with_include:
        return {
            "HOCONSTRING_INCLUDE_ad5c3c187d5107c099f66681f1896c70": "include required(classpath(\"application\"))",
            "HOCONSTRING_INCLUDE_61b86ce2e19939719a2e043b923774e4": "include required(file(\"application\"))",
            "HOCONSTRING_INCLUDE_543d042c69d8a730bc2b5785ac2f13c9": "include required(url(\"application\"))",
            "HOCONSTRING_INCLUDE_9456b859a44adad9a3d00ff3fcbbc5ae": "include required(\"application.conf\")",
            "level1": {
                "HOCONSTRING_INCLUDE_0714deb341d3d6291199d4738656c32b": "include file(\"/srv/test.conf\")",
                "level2": {
                    "HOCONSTRING_INCLUDE_91f31b362d72089d09f6245e912efb30": "include url(\"http://ok.com/test.conf\")",
                    "level3": {
                        "HOCONSTRING_INCLUDE_906d6e6eff885e840b705c2e7be3ba2d": "include classpath(\"test\")",
                        "level4": {
                            "HOCONSTRING_INCLUDE_c971be2dbb00ef0b44b9e4bf3c57f5cb": "include \"test.conf\"",
                            "level5": {
                                "HOCONSTRING_INCLUDE_44cb98470497b76dde0ab244c70870f0": "include \"test.hocon\""
                            },
                        },
                    },
                },
            },
        }
    else:
        return {'level1': {'level2': {'level3': {'level4': {'level5': {}}}}}}


def test_from_dict():
    ref_d = get_test_dict()
    hs = HOCONString.from_dict(ref_d, include=INCLUDE_CROMWELL)
    print(str(hs))
    print(get_test_hocon_str())
    assert str(hs) == get_test_hocon_str()


def test_to_dict():
    hs = HOCONString(get_test_hocon_str())
    assert hs.to_dict(with_include=False) == get_test_dict(with_include=False)
    assert hs.to_dict(with_include=True) == get_test_dict(with_include=True)

    hs = HOCONString(get_test_hocon_str_multiple_includes())
    assert hs.to_dict(with_include=False) == get_test_multiple_includes(
        with_include=False
    )
    assert hs.to_dict(with_include=True) == get_test_multiple_includes(
        with_include=True
    )


def test_merge():
    s1 = get_test_hocon_str()
    s2 = get_test_hocon_str2()
    s3 = get_test_hocon_str_multiple_includes()

    d1 = get_test_dict()
    d2 = get_test_dict2()
    d3 = get_test_multiple_includes(True)

    dm12 = deepcopy(d1)
    merge_dict(dm12, d2)
    dm32 = deepcopy(d3)
    merge_dict(dm32, d2)

    hs1 = HOCONString(s1)
    hs2 = HOCONString(s2)
    hs3 = HOCONString(s3)
    hsm12 = HOCONString.from_dict(dm12, include=INCLUDE_CROMWELL)
    hsm32 = HOCONString.from_dict(dm32)

    assert str(hsm12) == hs1.merge(hs2)
    assert str(hsm12) == hs1.merge(d2)
    assert str(hsm12) == hs1.merge(s2)

    assert str(hsm32) == hs3.merge(hs2)
    assert str(hsm32) == hs3.merge(d2)
    assert str(hsm32) == hs3.merge(s2)

    # merge with update
    # item 1 should be updated with merged
    hs1_original_str = str(hs1)
    assert str(hsm12) == hs1.merge(hs2, update=True)
    assert str(hs1) == str(hsm12)
    assert hs1_original_str != str(hs1)


def test_get_contents():
    s2 = get_test_hocon_str2()
    hs2 = HOCONString(s2)

    assert hs2.get_contents(with_include=True).strip() == s2
    assert (
        hs2.get_contents(with_include=False).strip()
        == s2.replace(INCLUDE_CROMWELL, '').strip()
    )
