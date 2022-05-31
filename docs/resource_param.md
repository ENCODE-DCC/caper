# Resource parameters for HPC backends (slurm, sge, pbs, lsf)

Note that Cromwell's implicit type conversion (`String` to `Integer`) seems to be buggy for WomLong type memory variables (`memory_mb` and `memory_gb`). So be careful about using the `+` operator between `WomLong` and other types (`String`, even `Int`). See https://github.com/broadinstitute/cromwell/issues/4659

For example, `${"--mem=" + memory_mb}` will not work since `memory_mb` is `WomLong`. Use `${"if defined(memory_mb) then "--mem=" else ""}{memory_mb}${"if defined(memory_mb) then "mb " else " "}`.

You can use Cromwell's built-in variables (attributes defined in WDL task's runtime) within Cromwell's `${}` notation.
- `cpu`: Number of cores for a job (default = 1)
- `memory_mb`, `memory_gb`: Total memory for a job in MB or GB. These are converted from 'memory' string attribute (including size unit)
 defined in WDL task's runtime
- `time`: Time limit for a job in hour
- `gpu`: Specified gpu name or number of gpus (it's declared as String)
