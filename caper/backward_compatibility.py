"""Variables and functions for backward_compatibililty
"""

CAPER_1_0_0_PARAM_KEY_NAME_CHANGE = {
    'out_dir': 'local_out_dir',
    'out_gcs_bucket': 'gcp_out_dir',
    'out_s3_bucket': 'aws_out_dir',
    'tmp_dir': 'local_loc_dir',
    'tmp_gcs_bucket': 'gcp_loc_dir',
    'tmp_s3_bucket': 'aws_loc_dir',
    'ip': 'hostname',
}
