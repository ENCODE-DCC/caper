import json
import logging
from collections import defaultdict

import numpy as np
from sklearn import linear_model

from .cromwell_metadata import CromwellMetadata, convert_type_np_to_py
from .dict_tool import flatten_dict

logger = logging.getLogger(__name__)


def solve_linear_problem(x, y):
    """Solve y = A(X) by using linear regression.
    Args:
        x:
            X Matrix.
        y:
            y vector.
    Returns:
        Tuple of (coeffs, intercept).
    """
    try:
        model = linear_model.LinearRegression().fit(x, y)
        return list(model.coef_), model.intercept_

    except (TypeError, ValueError):
        logger.error(
            'Linear regression failed due to type/dim mismatch. ' 'Too few data?'
        )


class ResourceAnalysis:
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
    DEFAULT_SOLVER = solve_linear_problem

    def __init__(self, metadata_jsons):
        """Solves y = f(x) in a statistical way where
        x is a vector of input file sizes (e.g. size_each([bam, bowtie2_index_tar, ...]))
        y is a vector of resources (e.g. [max_mem, max_disk, ...])

        self._tasks is extended (across all workflows) list of resource monitoring
        result from gcp_monitor():
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
        self._tasks = []
        for metadata_json in metadata_jsons:
            if isinstance(metadata_json, CromwellMetadata):
                cm = metadata_json
            else:
                cm = CromwellMetadata(metadata_json)
            self._tasks.extend(cm.gcp_monitor())

    def analyze(
        self,
        in_file_vars=None,
        reduce_in_file_vars=DEFAULT_REDUCE_IN_FILE_VARS,
        target_resources=DEFAULT_TARGET_RESOURCES,
        solver=DEFAULT_SOLVER,
    ):
        """Find and analyze all tasks.

        Args:
            in_file_vars:
                Dict { TASK_NAME: [IN_FILE_VAR1, ...] }.
                See ResourceAnalysis.analyze_per_task.__doc__ for details
            reduce_in_file_vars:
                Python function (e.g. sum, max) to reduce x matrix into a vector.
                See ResourceAnalysis.analyze_per_task.__doc__ for details.
            target_resources:
                Keys (in dot notation) to make vector y.
            solver:
                Currently `linear` (linear regression) only.
        Returns:
            Results in a dict form: {
                'x': X_DATA,
                'y': Y_DATA,
                'coeffs': RESULT_FROM_SOLVER_FOR_EACH_COL_IN_Y
            }
        """
        result = {}

        for task_name in self._get_all_task_names():
            if in_file_vars and task_name in in_file_vars:
                in_file_vars_per_task = in_file_vars[task_name]
            else:
                in_file_vars_per_task = None

            result[task_name] = self.analyze_task(
                task_name,
                in_file_vars=in_file_vars_per_task,
                reduce_in_file_vars=reduce_in_file_vars,
                target_resources=target_resources,
                solver=solver,
            )

        return result

    def analyze_task(
        self,
        task_name,
        in_file_vars=None,
        reduce_in_file_vars=DEFAULT_REDUCE_IN_FILE_VARS,
        target_resources=DEFAULT_TARGET_RESOURCES,
        solver=DEFAULT_SOLVER,
    ):
        """Does resource analysis on a task.
        Convert task's raw data into a (x_matrix, y_vector) form
        to use a general solver for y = f(x).

        Input file sizes are converted into one single matrix.
        Such x_matrix should look like:
            [
                [IN_FILE1_SIZE1, IN_FILE2_SIZE1, ...],
                [IN_FILE1_SIZE2, IN_FILE2_SIZE2, ...],
                ...
            ]
        If reduce_in_file_vars is defined (e.g. sum).
        Such x_matrix can be reduced to a vector.
            [
                [SUM_ALL_IN_FILES_SIZE1],
                [SUM_ALL_IN_FILES_SIZE2],
                ...
            ]

        Each resource in `target_resources` becomes a y_vec.
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
            solver:
                Solver takes in x matrix and y vec and returns coeffs.

        Returns:
            Analysis result.
        """
        result = {}

        x_data = defaultdict(list)
        y_data = defaultdict(list)

        # gather data for a given task across workflows
        for task in self._tasks:
            if task_name != task['task_name']:
                continue

            for in_file_var, in_file_size in task['input_file_sizes'].items():
                if in_file_vars and in_file_var not in in_file_vars:
                    continue
                if in_file_size:
                    # in_file_size is a list of file sizes.
                    # sum them up. this is different from reduce_in_file_vars.
                    x_data[in_file_var].append(sum(in_file_size))

            for res_key, res_val in flatten_dict(task, reducer='.').items():
                if res_key in target_resources and res_val:
                    y_data[res_key].append(res_val)

        if reduce_in_file_vars:
            key = '{reduce_name}({vars})'.format(
                reduce_name=reduce_in_file_vars.__name__, vars=','.join(x_data.keys())
            )
            # transpose to reduce(sum by default) file sizes
            # over all in_file_vars
            tranposed = np.transpose([vec for vec in x_data.values()])
            reduced = [reduce_in_file_vars(vec) for vec in tranposed]
            x_data = {key: reduced}

        # tranpose it to make x matrix
        x_matrix = np.transpose([vec for vec in x_data.values()])

        result = {
            'x': x_data,
            'y': y_data,
            'coeffs': {
                res_key: solver(x_matrix, y_vec) for res_key, y_vec in y_data.items()
            },
        }
        # a bit hacky way to recursively convert numpy type into python type
        json_str = json.dumps(result, default=convert_type_np_to_py)
        return json.loads(json_str)

    def _get_all_task_names(self):
        """Get all task names.
        """
        return list(set([task['task_name'] for task in self._tasks]))
