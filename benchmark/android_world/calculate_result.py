import gzip
import io
import os
import pickle
from typing import Any
import numpy as np

from android_world import registry, suite_utils


def _unzip_and_read_pickle(file_path: str) -> Any:
  """Reads a gzipped pickle file using 'with open', unzips, and unpickles it.

  Args:
      file_path: The path to the gzipped pickle file.

  Returns:
      The original Python object that was pickled and gzipped.
  """
  with open(file_path, 'rb') as f:
    compressed = f.read()

  with gzip.open(io.BytesIO(compressed), 'rb') as f_in:
    return pickle.load(f_in)


def remove_click_before_type(data):
    episode_length = data[0]['episode_length']
    remove_count = 0
    trajectory = data[0]['episode_data']['step_data']
    for i, step in enumerate(trajectory):
        if step.action and step.action.name == 'type':
            if i > 0 and trajectory[i-1].action and trajectory[i-1].action.name == 'click':
                remove_count += 1
    return episode_length - remove_count


"Read ckpt and print result"
path = r"E:\androidworld\runs\run_missing_reflector"
files = os.listdir(path)
files = [file for file in files if file.endswith(".pkl.gz")]

n_trials = max([int(name.split("_")[1][0]) for name in files]) + 1
print(n_trials)

files = list(sorted(files))

task_registry = registry.TaskRegistry()
suite = suite_utils.create_suite(
      task_registry.get_registry(family='android_world'),
      n_task_combinations=1,
      seed=30,
      tasks=None,
      use_identical_params=False,
  )

srs, steps = [], []  # 1.5x_max_step
fixed_srs = []  # 修正后的1.0x_max_step
raw_srs = []  # 1.0x_max_step
srs_for_std, fixed_srs_for_std, raw_srs_for_std = [], [], []
exceed_max_step_tasks = []
fixed_not_exceed_max_step_tasks = []

outputs = []
output = f"{'task_name':<{50}} {'n_trials':<{10}} {'sr':<{10}} {'steps':<{10}} {'1.0x_max_step'}"
print(output)
outputs.append(output)

for task, item in suite.items():
    task_name = task
    is_successfuls, episode_lengths = [], []
    fixed_is_successfuls = []
    raw_is_successfuls = []
    for i in range(n_trials):
        if f"{task}_{i}.pkl.gz" not in files:
            print(f"{task}_{i}.pkl.gz not in {path}")
            outputs.append(f"{task}_{i}.pkl.gz not in {path}")
            srs_for_std.append(np.nan)
            fixed_srs_for_std.append(np.nan)
            raw_srs_for_std.append(np.nan)
            continue

        file = f"{task}_{i}.pkl.gz"
        data = _unzip_and_read_pickle(os.path.join(path, file))
        is_successful = data[0]['is_successful']
        episode_length = data[0]['episode_length']
        if is_successful > -1:
            if is_successful > 0 and episode_length > item[0].complexity * 10:
                raw_is_successful = 0
                exceed_max_step_tasks.append(file)
                fixed_episode_length = remove_click_before_type(data)
                if fixed_episode_length > item[0].complexity * 10:
                    fixed_is_successful = 0
                else:
                    fixed_is_successful = is_successful
                    fixed_not_exceed_max_step_tasks.append((file, fixed_episode_length))
            else:
                raw_is_successful = is_successful
                fixed_is_successful = is_successful
                fixed_episode_length = episode_length
            is_successfuls.append(is_successful)
            episode_lengths.append(episode_length)
            fixed_is_successfuls.append(fixed_is_successful)
            raw_is_successfuls.append(raw_is_successful)
            srs_for_std.append(is_successful)
            fixed_srs_for_std.append(fixed_is_successful)
            raw_srs_for_std.append(raw_is_successful)
        else:
            print(f"Failed task: {file}, Is_successful: {is_successful}")
            outputs.append(f"Failed task: {file}, Is_successful: {is_successful}")
            srs_for_std.append(np.nan)
            fixed_srs_for_std.append(np.nan)
            raw_srs_for_std.append(np.nan)
    num_runs = len(is_successfuls)
    if num_runs == 0:
        output = f"{task_name:<{50}} {num_runs:<{10}} {"None":<{10}} {"None":<{10}} {item[0].complexity * 10}"
    else:
        mean_is_successful = sum(is_successfuls) / num_runs
        mean_episode_length = sum(episode_lengths) / num_runs
        srs.append(mean_is_successful)
        steps.append(mean_episode_length)
        fixed_srs.append(sum(fixed_is_successfuls) / num_runs)
        raw_srs.append(sum(raw_is_successfuls) / num_runs)
        output = f"{task_name:<{50}} {num_runs:<{10}} {mean_is_successful:<{10}} {mean_episode_length:<{10}} {item[0].complexity * 10}"
    print(output)
    outputs.append(output)

print(f"Total tasks: {len(srs)}, Success tasks: {sum(srs)}")
outputs.append(f"Total tasks: {len(srs)}, Success tasks: {sum(srs)}")
print(f"Success rate: {sum(srs)/len(srs)}")
outputs.append(f"Success rate: {sum(srs)/len(srs)}")
print(f"Average steps: {sum(steps)/len(steps)}")
outputs.append(f"Average steps: {sum(steps)/len(steps)}")
print(f"Fixed success rate: {sum(fixed_srs)/len(fixed_srs)}")
outputs.append(f"Fixed success rate: {sum(fixed_srs)/len(fixed_srs)}")
print(f"Raw success rate: {sum(raw_srs)/len(raw_srs)}")
outputs.append(f"Raw success rate: {sum(raw_srs)/len(raw_srs)}")

if len(srs_for_std)  % n_trials == 0:
    srs_for_std = np.array(srs_for_std).reshape(-1, n_trials)
    means = np.nanmean(srs_for_std, axis=0)
    std = np.nanstd(means)
    print(f"Success rate mean by trials: {np.nanmean(means)}")
    outputs.append(f"Success rate mean by trials: {np.nanmean(means)}")
    print(f"Success rate std by trials: {std}")
    outputs.append(f"Success rate std by trials: {std}")

if len(fixed_srs_for_std)  % n_trials == 0:
    fixed_srs_for_std = np.array(fixed_srs_for_std).reshape(-1, n_trials)
    fixed_means = np.nanmean(fixed_srs_for_std, axis=0)
    fixed_std = np.nanstd(fixed_means)
    print(f"Fixed success rate mean by trials: {np.nanmean(fixed_means)}")
    outputs.append(f"Fixed success rate mean by trials: {np.nanmean(fixed_means)}")
    print(f"Fixed success rate std by trials: {fixed_std}")
    outputs.append(f"Fixed success rate std by trials: {fixed_std}")

if len(raw_srs_for_std)  % n_trials == 0:
    raw_srs_for_std = np.array(raw_srs_for_std).reshape(-1, n_trials)
    raw_means = np.nanmean(raw_srs_for_std, axis=0)
    raw_std = np.nanstd(raw_means)
    print(f"Raw success rate mean by trials: {np.nanmean(raw_means)}")
    outputs.append(f"Raw success rate mean by trials: {np.nanmean(raw_means)}")
    print(f"Raw success rate std by trials: {raw_std}")
    outputs.append(f"Raw success rate std by trials: {raw_std}")

print()
print(f"Exceed max step tasks: {len(exceed_max_step_tasks)}")
outputs.append(f"\nExceed max step tasks: {len(exceed_max_step_tasks)}")
for line in exceed_max_step_tasks:
    print(line)
    outputs.append(line)

print(f"Fixed not exceed max step tasks: {len(fixed_not_exceed_max_step_tasks)}")
outputs.append(f"\nFixed not exceed max step tasks: {len(fixed_not_exceed_max_step_tasks)}")
for line in fixed_not_exceed_max_step_tasks:
    print(line)
    outputs.append(str(line))

with open(os.path.join(path, "result.txt"), "w") as f:
    for line in outputs:
        f.write(line + "\n")