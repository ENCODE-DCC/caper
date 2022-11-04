# Resource parameters for HPC backends (slurm, sge, pbs, lsf)

Note that Cromwell's implicit type conversion (`String` to `Integer`) seems to be buggy for WomLong type memory variables (`memory_mb` and `memory_gb`). So be careful about using the `+` operator between `WomLong` and other types (`String`, even `Int`). See https://github.com/broadinstitute/cromwell/issues/4659

For example, `${"--mem=" + memory_mb}` will not work since `memory_mb` is `WomLong`. Use `${"if defined(memory_mb) then "--mem=" else ""}{memory_mb}${"if defined(memory_mb) then "mb " else " "}`.

You can use Cromwell's built-in variables (attributes defined in WDL task's runtime) within Cromwell's `${}` notation.
- `cpu`: Number of cores for a job (default = 1)
- `memory_mb`, `memory_gb`: Total memory for a job in MB or GB. These are converted from 'memory' string attribute (including size unit)
 defined in WDL task's runtime
- `time`: Time limit for a job in hour
- `gpu`: Specified gpu name or number of gpus (it's declared as String)

# How to configure resource parameters on HPCs

Open `~/.caper/default.conf` with a text editor and add the following code lines according to your HPC type. Following commented instructions to customize resource parameters of HPC's submit/monitor/delete commands.

## SLURM

```ini
# This parameter defines resource parameters for Caper's leader job only.
slurm-leader-job-resource-param=-t 48:00:00 --mem 4G

# This parameter defines resource parameters for submitting WDL task to job engine.
# It is for HPC backends only (slurm, sge, pbs and lsf).
# It is not recommended to change it unless your cluster has custom resource settings.
# See https://github.com/ENCODE-DCC/caper/blob/master/docs/resource_param.md for details.
slurm-resource-param=-n 1 --ntasks-per-node=1 --cpus-per-task=${cpu} ${if defined(memory_mb) then "--mem=" else ""}${memory_mb}${if defined(memory_mb) then "M" else ""} ${if defined(time) then "--time=" else ""}${time*60} ${if defined(gpu) then "--gres=gpu:" else ""}${gpu}

```

## SGE

```ini
# This parameter defines resource parameters for Caper's leader job only.
sge-leader-job-resource-param=-l h_rt=48:00:00,h_vmem=4G

# Parallel environment of SGE:
# Find one with `$ qconf -spl` or ask you admin to add one if not exists.
# If your cluster works without PE then edit the below sge-resource-param
sge-pe=

# This parameter defines resource parameters for submitting WDL task to job engine.
# It is for HPC backends only (slurm, sge, pbs and lsf).
# It is not recommended to change it unless your cluster has custom resource settings.
# See https://github.com/ENCODE-DCC/caper/blob/master/docs/resource_param.md for details.
sge-resource-param=${if cpu > 1 then "-pe " + sge_pe + " " else ""} ${if cpu > 1 then cpu else ""} ${true="-l h_vmem=$(expr " false="" defined(memory_mb)}${memory_mb}${true=" / " false="" defined(memory_mb)}${if defined(memory_mb) then cpu else ""}${true=")m" false="" defined(memory_mb)} ${true="-l s_vmem=$(expr " false="" defined(memory_mb)}${memory_mb}${true=" / " false="" defined(memory_mb)}${if defined(memory_mb) then cpu else ""}${true=")m" false="" defined(memory_mb)} ${"-l h_rt=" + time + ":00:00"} ${"-l s_rt=" + time + ":00:00"} ${"-l gpu=" + gpu}
```

## PBS

```ini
# This parameter defines resource parameters for Caper's leader job only.
pbs-leader-job-resource-param=-l walltime=48:00:00,mem=4gb

# This parameter defines resource parameters for submitting WDL task to job engine.
# It is for HPC backends only (slurm, sge, pbs and lsf).
# It is not recommended to change it unless your cluster has custom resource settings.
# See https://github.com/ENCODE-DCC/caper/blob/master/docs/resource_param.md for details.
pbs-resource-param=${"-lnodes=1:ppn=" + cpu}${if defined(gpu) then ":gpus=" + gpu else ""} ${if defined(memory_mb) then "-l mem=" else ""}${memory_mb}${if defined(memory_mb) then "mb" else ""} ${"-lwalltime=" + time + ":0:0"}
```

## LSF

```ini
# This parameter defines resource parameters for Caper's leader job only.
lsf-leader-job-resource-param=-W 2880 -M 4g

# This parameter defines resource parameters for submitting WDL task to job engine.
# It is for HPC backends only (slurm, sge, pbs and lsf).
# It is not recommended to change it unless your cluster has custom resource settings.
# See https://github.com/ENCODE-DCC/caper/blob/master/docs/resource_param.md for details.
lsf-resource-param=${"-n " + cpu} ${if defined(gpu) then "-gpu " + gpu else ""} ${if defined(memory_mb) then "-M " else ""}${memory_mb}${if defined(memory_mb) then "m" else ""} ${"-W " + 60*time}
```
