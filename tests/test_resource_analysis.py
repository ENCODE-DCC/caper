"""Test is based on a metadata JSON file generated from
running atac-seq-pipeline v1.8.0 with the following input JSON.
gs://encode-pipeline-test-samples/encode-atac-seq-pipeline/ENCSR356KRQ_subsampled_caper.json
"""

import pytest

from caper.resource_analysis import LinearResourceAnalysis, ResourceAnalysis


def test_resource_analysis_abstract_class(gcp_res_analysis_metadata):
    with pytest.raises(TypeError):
        # abstract base-class
        ResourceAnalysis()


def test_resource_analysis_analyze_task(gcp_res_analysis_metadata):
    analysis = LinearResourceAnalysis()
    analysis.collect_resource_data([gcp_res_analysis_metadata])

    result_align1 = analysis.analyze_task(
        'atac.align',
        in_file_vars=['fastqs_R1'],
        reduce_in_file_vars=None,
        target_resources=['stats.max.mem', 'stats.mean.cpu_pct'],
    )
    assert result_align1['x'] == {'fastqs_R1': [15643136, 18963919]}
    assert 'stats.mean.cpu_pct' in result_align1['y']
    assert 'stats.max.mem' in result_align1['y']
    assert 'stats.max.disk' not in result_align1['y']
    assert list(result_align1['y'].keys()) == list(result_align1['coeffs'].keys())
    assert result_align1['coeffs']['stats.mean.cpu_pct'][0][0] == pytest.approx(
        1.6844513715565233e-06
    )
    assert result_align1['coeffs']['stats.mean.cpu_pct'][1] == pytest.approx(
        42.28561239506905
    )
    assert result_align1['coeffs']['stats.max.mem'][0][0] == pytest.approx(
        48.91222341236991
    )
    assert result_align1['coeffs']['stats.max.mem'][1] == pytest.approx(
        124314029.09791338
    )

    result_align2 = analysis.analyze_task(
        'atac.align', in_file_vars=['fastqs_R2'], reduce_in_file_vars=sum
    )
    assert result_align2['x'] == {'sum(fastqs_R2)': [16495088, 20184668]}
    assert 'stats.mean.cpu_pct' not in result_align2['y']
    assert 'stats.max.mem' in result_align2['y']
    assert 'stats.max.disk' in result_align2['y']
    assert list(result_align2['y'].keys()) == list(result_align2['coeffs'].keys())

    result_align_star = analysis.analyze_task('atac.align*', reduce_in_file_vars=max)
    assert result_align_star['x'] == {
        'max(chrsz,fastqs_R1,fastqs_R2,idx_tar,tmp_fastqs)': [
            32138224,
            39148587,
            3749246230,
            3749246230,
        ]
    }


def test_resource_analysis_analyze(gcp_res_analysis_metadata):
    """Test method analyze() which analyze all tasks defined in in_file_vars.
    """
    analysis = LinearResourceAnalysis()
    analysis.collect_resource_data([gcp_res_analysis_metadata])

    result = analysis.analyze(
        in_file_vars={
            'atac.align*': ['fastqs_R1', 'fastqs_R2'],
            'atac.filter*': ['bam'],
        }
    )
    assert len(result) == 2
    assert result['atac.align*']['x'] == {
        'sum(fastqs_R1,fastqs_R2)': [32138224, 39148587, 32138224, 39148587]
    }
    assert result['atac.filter*']['x'] == {
        'sum(bam)': [61315022, 76789196, 61315022, 76789196]
    }

    result_all = analysis.analyze()
    # 38 tasks in total
    assert len(result_all) == 38
