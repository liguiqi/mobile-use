import os
import sys
import argparse
import yaml

parant_dir = os.path.dirname(__file__)
project_home = os.path.dirname(os.path.dirname(parant_dir))
sys.path = [
    os.path.join(project_home, 'third_party/Android-Lab')
] + sys.path

from agent import get_agent
from evaluation.auto_test import *
from evaluation.parallel import parallel_worker
from generate_result import find_all_task_files
from evaluation.configs import AppConfig, TaskConfig
from mobile_use_auto_test import *
from mobile_use_executor import *


if __name__ == '__main__':
    android_lab_dir = os.path.join(project_home, 'third_party/Android-Lab')
    task_yamls = os.listdir(f'{android_lab_dir}/evaluation/config')
    task_yamls = [f"{android_lab_dir}/evaluation/config/" + i for i in task_yamls if i.endswith(".yaml")]

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("-n", "--name", default=None, type=str)
    arg_parser.add_argument("-c", "--config", default=f"{parant_dir}/config.yaml", type=str)
    arg_parser.add_argument("--task_config", nargs="+", default=task_yamls, help="All task config(s) to load")
    arg_parser.add_argument("--task_id", nargs="+", default=None)
    arg_parser.add_argument("--debug", action="store_true", default=False)
    arg_parser.add_argument("--app", nargs="+", default=None)
    arg_parser.add_argument("-p", "--parallel", default=1, type=int)

    args = arg_parser.parse_args()
    with open(args.config, "r") as file:
        yaml_data = yaml.safe_load(file)

    agent_config = yaml_data["agent"]
    task_config = yaml_data["task"]
    eval_config = yaml_data["eval"]

    if args.name is None:
        args.name = f"{yaml_data.get('name', agent_config['name'])}_{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}"

    autotask_class = task_config["class"] if "class" in task_config else "ScreenshotMobileTask_AutoTest"

    single_config = TaskConfig(**task_config["args"])
    single_config = single_config.add_config(eval_config)
    if "True" == agent_config.get("relative_bbox"):
        single_config.is_relative_bbox = True
    agent_class = globals().get(agent_config["name"])
    if agent_class is None:
        agent = get_agent(agent_config["name"], **agent_config["args"])
    else:
        agent = agent_class(**agent_config["args"])

    task_files = find_all_task_files(args.task_config)
    print(f"Evaluation saved name: {args.name}")
    if os.path.exists(os.path.join(single_config.save_dir, args.name)):
        already_run = os.listdir(os.path.join(single_config.save_dir, args.name))
        already_run = [i.split("_")[0] + "_" + i.split("_")[1] for i in already_run]
    else:
        already_run = []

    all_task_start_info = []
    for app_task_config_path in task_files:
        app_config = AppConfig(app_task_config_path)
        if args.task_id is None:
            task_ids = list(app_config.task_name.keys())
        else:
            task_ids = args.task_id
        for task_id in task_ids:
            if task_id in already_run:
                print(f"Task {task_id} already run, skipping")
                continue
            if task_id not in app_config.task_name:
                continue
            task_instruction = app_config.task_name[task_id].strip()
            app = app_config.APP
            if args.app is not None:
                print(app, args.app)
                if app not in args.app:
                    continue
            package = app_config.package
            command_per_step = app_config.command_per_step.get(task_id, None)

            task_instruction = f"You should use {app} to complete the following task: {task_instruction}"
            all_task_start_info.append({
                "agent": agent,
                "task_id": task_id,
                "task_instruction": task_instruction,
                "package": package,
                "command_per_step": command_per_step,
                "app": app
            })

    class_ = globals().get(autotask_class)
    if class_ is None:
        raise AttributeError(f"Class {autotask_class} not found. Please check the class name in the config file.")

    if args.parallel == 1:
        Auto_Test = class_(single_config.subdir_config(args.name))
        print("Auto_Test", Auto_Test)
        Auto_Test.run_serial(all_task_start_info)
    else:
        parallel_worker(class_, single_config.subdir_config(args.name), args.parallel, all_task_start_info)
