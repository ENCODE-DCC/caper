import fnmatch
import json
import logging
from abc import ABC, abstractmethod
from collections import defaultdict

import numpy as np
from matplotlib import pyplot
from matplotlib.backends.backend_pdf import PdfPages
from sklearn import linear_model

from .cromwell_metadata import CromwellMetadata, convert_type_np_to_py
from .dict_tool import flatten_dict

logger = logging.getLogger(__name__)


class ResourceAnalysis(ABC):
    """
    Class constants:
        DEFAULT_REDUCE_IN_FILE_VARS:
            Function to be used for reducing x vector.
            e.g. sum, min, max, ...
        DEFAULT_TARGET_RESOURCES:
            Keys to make y vector.
    """

    DEFAULT_REDUCE_IN_FILE_VARS = sum
    DEFAULT_TARGET_RESOURCES = ('stats.max.mem', 'stats.max.disk')

    def __init__(self):
        """Solves y = f(X) in a statistical way where
        X is a matrix vector of input file sizes (e.g. size_each([bam, bowtie2_index_tar, ...]))
        y is a vector of resources (e.g. [max_mem, max_disk, ...])
        """
        self._task_resources = []

    @property
    def task_resources(self):
        return self._task_resources

    def collect_resource_data(self, metadata_jsons):
        """Collect resource data from parsing metadata JSON files.

        self._task_resources is an extended (across all workflows) list of resource monitoring
        result from CromwellMetadata.gcp_monitor():
        [
            {
                'task_name': TASK1,
                'workflow_id': WORKFLOW_ID_OF_TASK1,
                ...
            },
            {
                'task_name': TASK2,
                'workflow_id': WORKFLOW_ID_OF_TASK2,
                ...
            }
        ]

        Args:
            metadata_jsons:
                List of metadata JSON file URIs or metadata JSONs
                or CromwellMetadata objects.
        """
        self._task_resources = []
        for metadata_json in metadata_jsons:
            self._task_resources.extend(CromwellMetadata(metadata_json).gcp_monitor())

    def analyze(
        self,
        in_file_vars=None,
        reduce_in_file_vars=DEFAULT_REDUCE_IN_FILE_VARS,
        target_resources=DEFAULT_TARGET_RESOURCES,
        plot_pdf=None,
    ):
        """Find and analyze all tasks.
        Run `self.collect_resource_data()` first to collect resource data before analysis.

        Args:
            in_file_vars:
                Dict { TASK_NAME: [IN_FILE_VAR1, ...] }.
                If not None, only tasks defined in it will be analyzed.
                See ResourceAnalysis.analyze_per_task.__doc__ for details.
            reduce_in_file_vars:
                Python function (e.g. sum, max) to reduce x matrix into a vector.
                See ResourceAnalysis.analyze_per_task.__doc__ for details.
            target_resources:
                Keys (in dot notation) to make vector y.
            plot_pdf:
                Local file name for a PDF plot.
        Returns:
            Results in a dict form: {
                TASK_NAME: {
                    'x': X_DATA,
                    'y': Y_DATA,
                    'coeffs': ANALYSIS_RESULT
                }
            }
        """
        plot_pp = None
        if plot_pdf:
            plot_pp = PdfPages(plot_pdf)

        result = {}

        if in_file_vars:
            all_tasks = in_file_vars.keys()
        else:
            all_tasks = list(set([task['task_name'] for task in self.task_resources]))

        for task_name in all_tasks:
            result[task_name] = self.analyze_task(
                task_name,
                in_file_vars=in_file_vars[task_name] if in_file_vars else None,
                reduce_in_file_vars=reduce_in_file_vars,
                target_resources=target_resources,
                plot_pp=plot_pp,
            )

        if plot_pdf:
            plot_pp.close()

        return result

    def analyze_task(
        self,
        task_name,
        in_file_vars=None,
        reduce_in_file_vars=DEFAULT_REDUCE_IN_FILE_VARS,
        target_resources=DEFAULT_TARGET_RESOURCES,
        plot_pp=None,
    ):
        """Does resource analysis on a task.
        Run `self.collect_resource_data()` first to collect resource data before analysis.
        Then you can such collected data for each task.

        To use a general solver for y = f(x),
        convert task's raw resouce data into (x_matrix, y_vector) form.

        Input file sizes are converted into one single matrix.
        Such x_matrix should look like:
            [
                [IN_FILE1_SIZE1, IN_FILE2_SIZE1, ...],
                [IN_FILE1_SIZE2, IN_FILE2_SIZE2, ...],
                ...
            ]
        If reduce_in_file_vars is defined (e.g. sum).
        Such x_matrix will be reduced to a vector.
            [
                [SUM_ALL_IN_FILES_SIZE1],
                [SUM_ALL_IN_FILES_SIZE2],
                ...
            ]

        Each resource metric in `target_resources` becomes a y_vec.
        For example, there are two kinds of default resource metrics.
        i.e. max_mem and max_disk.
        Therefore, y_vec_1 should look like:
            [
                STATS_MAX_MEM1,
                STATS_MAX_MEM2,
                ...
            ]
        y_vec_2 should look like:
            [
                STATS_MAX_DISK1,
                STATS_MAX_DISK2,
                ...
            ]
        They are two separate problems.

        Args:
            in_file_vars:
                List of input file vars. [IN_FILE_VAR1, ...].
                Matching input file will be included in x_matrix of analysis.
                See `input_file_sizes` in CromwellMetadata.gcp_monitor.__doc__ for details.
                If None or False, then all input files will be used to make x_matrix.
            reduce_in_file_vars:
                Python function to reduce x_vector. e.g. sum, max.
                If None, then no reduction of vector x.
                If you don't reduce x, make sure that you have enough number of data (>=dim(x)).
                Some solver can fail due to lack of data. i.e. dim(problem, solver) > dim(data).
                For example, even a linear solver will fail with only one dataset.
            target_resources:
                Keys (in dot notation) to make vector y. e.g. ('stats.max.mem', 'stats.max.disk').
                See CromwellMetadata.gcp_monitor.__doc__ to find available keys.
                One vector y for each key, which means one solving for each key.
            plot_pp:
                Matplotlib's PDF backend PdfPages object to write plots on multiple pages.
                (task/resource per page).

        Returns:
            coeffs:
                Analysis result.
                e.g. (coeffs, intercept) for linear regression.
        """
        result = {}

        in_file_vars_found = set()
        x_data = defaultdict(list)
        y_data = defaultdict(list)

        logger.info('Analyzing task={task}'.format(task=task_name))
        # first look at task's optional/empty input file vars across all workflows
        # e.g. SE (single-ended) pipeline runs does not have fastqs_R2
        # but we want to mix both SE/PE (paired-ended) data.
        # so need to look at all workflows to check if optional/empty var is
        # actully a file var.
        matched_task_resources = []
        for task in self.task_resources:
            if not fnmatch.fnmatchcase(task['task_name'], task_name):
                continue
            matched_task_resources.append(task)

            for in_file_var, in_file_size in task['input_file_sizes'].items():
                if in_file_vars and in_file_var not in in_file_vars:
                    continue

                if in_file_size:
                    in_file_vars_found.add(in_file_var)

        for task in matched_task_resources:
            # gather y_data
            found_y_data = False
            for res_metric, res_val in flatten_dict(task, reducer='.').items():
                if res_metric in target_resources and res_val:
                    y_data[res_metric].append(res_val)
                    found_y_data = True

            # it's possible that y_data doesn't exists
            # if a task is done immediately after initializing
            # even before the monitoring script runs
            # so if there is no y_data, then ignore x_data too.
            if not found_y_data:
                continue

            # gather x_data
            for in_file_var in in_file_vars_found:
                in_file_size = task['input_file_sizes'].get(in_file_var)
                if in_file_size:
                    x_data[in_file_var].append(sum(in_file_size))
                else:
                    x_data[in_file_var].append(0)

        if reduce_in_file_vars:
            key = '{reduce_name}({vars})'.format(
                reduce_name=reduce_in_file_vars.__name__,
                vars=','.join(sorted(x_data.keys())),
            )
            # transpose to reduce(sum by default) file sizes
            # over all in_file_vars
            tranposed = np.transpose([vec for vec in x_data.values()])
            reduced = [reduce_in_file_vars(vec) for vec in tranposed]
            x_data = {key: reduced}

        # tranpose it to make x matrix
        x_matrix = np.transpose([vec for vec in x_data.values()])

        result = {'x': x_data, 'y': y_data, 'coeffs': {}}
        for res_metric, y_vec in y_data.items():
            result['coeffs'][res_metric] = self._solve(
                x_matrix=x_matrix,
                y_vec=y_vec,
                plot_y_label=res_metric,
                plot_title=task_name,
                plot_pp=plot_pp,
            )

        # a bit hacky way to recursively convert numpy type into python type
        json_str = json.dumps(result, default=convert_type_np_to_py)
        return json.loads(json_str)

    @abstractmethod
    def _solve(self, x_matrix, y_vec, plot_y_label=None, plot_title=None, plot_pp=None):
        raise NotImplementedError


class LinearResourceAnalysis(ResourceAnalysis):
    def _solve(self, x_matrix, y_vec, plot_y_label=None, plot_title=None, plot_pp=None):
        """Solve y = A(X) with linear regression.
        Also make a scatter plot (for one-dimensional x_matrix only).
        Use `reduce_in_file_vars` in ResourceAnalysis.analyze()
        to reduce a matrix into a vector.

        Args:
            x_matrix:
                X Matrix.
            y_vec:
                y vector.
            plot_y_label:
                y label for plot.
            plot_title:
                Plot title.
            plot_pp:
                Matplotlib's PDF backend PdfPages object.
        Returns:
            Tuple of (coeffs, intercept).
        """
        x_matrix = np.array(x_matrix)

        try:
            model = linear_model.LinearRegression().fit(x_matrix, y_vec)

        except ValueError:
            logger.error(
                'Failed to solve due to type/dim mismatch? '
                'Too few data or invalid resource monitoring script? '
                'title: {title}, y_label: {y_label}, '
                'y_vec={y_vec}, x_matrix: {x_matrix}'.format(
                    title=plot_title,
                    y_label=plot_y_label,
                    y_vec=y_vec,
                    x_matrix=x_matrix,
                ),
                exc_info=True,
            )
            return

        if plot_pp:
            if x_matrix.shape[1] > 1:
                logger.warning(
                    'Cannot make a 2D scatter plot. dim(x_matrix) > 1. '
                    'Multi-dimensional analysis without reducing x matrix?'
                )
            else:
                x_vec = x_matrix[:, 0]
                # scatter plot with a fitting line
                pyplot.scatter(x_vec, y_vec, s=np.pi * 3, color=(0, 0, 0), alpha=0.5)
                pyplot.plot(x_vec, model.coef_ * x_vec + model.intercept_)
                pyplot.title(plot_title)
                pyplot.xlabel('input_file_size')
                pyplot.ylabel(plot_y_label)
                pyplot.savefig(plot_pp, format='pdf')
                pyplot.clf()

        return list(model.coef_), model.intercept_
