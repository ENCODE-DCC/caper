"""Based on metadata JSON files from several ENCODE ATAC-seq pipeline runs.

"""

from caper.resouce_analysis import ResourceAnalysis


def test_resource_analysis(gcs_metadata_files_for_res_analysis):
    res_analysis = ResourceAnalysis(gcs_metadata_files_for_res_analysis)
    res_analysis.analyze()
