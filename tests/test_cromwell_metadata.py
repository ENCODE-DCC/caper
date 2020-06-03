from caper.cromwell import Cromwell


def get_succeeded_metadata_file(wdl, directory, cromwell, womtool):
    """Run Cromwell and get metadata JSON file.
    """
    if not hasattr(get_succeeded_metadata_file, 'has_output'):
        get_succeeded_metadata_file.metadata_file = None

    if not get_succeeded_metadata_file.metadata:
        c = Cromwell(cromwell=cromwell, womtool=womtool)
        get_succeeded_metadata_file.metadata_file = c.run(wdl, tmp_dir=directory)

    return get_succeeded_metadata_file.metadata_file


def get_failed_metadata_file(failing_wdl, directory, cromwell, womtool):
    """Run Cromwell and get metadata JSON file.
    """
    if not hasattr(get_failed_metadata_file, 'has_output'):
        get_failed_metadata_file.metadata_file = None

    if not get_failed_metadata_file.metadata:
        c = Cromwell(cromwell=cromwell, womtool=womtool)
        get_failed_metadata_file.metadata_file = c.run(failing_wdl, tmp_dir=directory)

    return get_failed_metadata_file.metadata_file
