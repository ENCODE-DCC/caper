"""There are lots of UserDict-based classesi n caper/cromwell_backend.py
In this test, only the followings classes with public methods
will be tested.
    - CromwellBackendBase

"""
from caper.cromwell_backend import CromwellBackendBase


def test_cromwell_backend_base_backend():
    """Test a property backend's getter, setter
    """
    bb1 = CromwellBackendBase('test1')
    backend_dict = {'a': 1, 'b': '2'}

    bb1.backend = backend_dict
    assert bb1.backend == backend_dict


def test_cromwell_backend_base_merge_backend():
    bb1 = CromwellBackendBase('test1')
    bb1.backend = {'a': 1, 'b': '2'}
    backend_dict = {'c': 3.0, 'd': '4.0'}

    bb1.merge_backend(backend_dict)
    assert bb1.backend == {'a': 1, 'b': '2', 'c': 3.0, 'd': '4.0'}


def test_cromwell_backend_base_backend_config():
    bb1 = CromwellBackendBase('test1')
    bb1.backend = {'config': {'root': 'test/folder'}}
    assert bb1.backend_config == {'root': 'test/folder'}


def test_cromwell_backend_base_backend_config_dra():
    bb1 = CromwellBackendBase('test1')
    bb1.backend = {
        'config': {
            'root': 'test/folder',
            'default-runtime-attributes': {'docker': 'ubuntu:latest'},
        }
    }
    assert bb1.default_runtime_attributes == {'docker': 'ubuntu:latest'}
