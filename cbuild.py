import os
import sys
import importlib.util
import CbuildProjects
import shutil
import BuildConfiguration
import Errors
import Toolchain


def load_project(directory):
	module_file = os.path.join(directory, "cproj.py")
	if not os.path.exists(module_file):
		raise Errors.CBuildError(f"No project file in {directory}")
	# load module
	module_name = module_file
	spec = importlib.util.spec_from_file_location(module_name, module_file)
	module = importlib.util.module_from_spec(spec)
	# pass arguments to the module
	module.cbuild = CbuildProjects
	CbuildProjects.global_project_directory = os.path.abspath(directory)
	# execute module
	spec.loader.exec_module(module)
	# initialize project
	project = module.Project()
	project.load_dependencies(CbuildProjects)
	return project


def init_cmd(args):
	current_file_dir = os.path.dirname(os.path.abspath(__file__))
	directory = args["directory"]

	project_file = os.path.join(directory, "cproj.py")
	if os.path.exists(project_file):
		raise Errors.CBuildError("Project file already exists")

	if not os.path.exists(directory):
		os.makedirs(directory)

	with open(project_file, "w") as f:
		# Write the initial code to the file
		project_type = getattr(CbuildProjects, args["type"].capitalize() + "Project")
		project_sample_source = open(os.path.join(current_file_dir, 'cproj.py'), 'r').read()
		f.write(project_sample_source.format(project_type.__name__, args["name"], str(args["dep"])))

	if args["files"]:
		if args["type"] == "binary":
			out_dir = os.path.join(directory, "private")
			if not os.path.exists(out_dir):
				os.makedirs(out_dir)
			shutil.copy(os.path.join(current_file_dir, "Entry.cpp"), out_dir)

		elif args["type"] == "library":
			src_path = os.path.join(directory, "private")
			header_path = os.path.join(directory, "public")

			if not os.path.exists(src_path):
				os.makedirs(src_path)

			if not os.path.exists(header_path):
				os.makedirs(header_path)

			shutil.copy(os.path.join(current_file_dir, "Library.cpp"), src_path)
			shutil.copy(os.path.join(current_file_dir, "Library.hpp"), header_path)


def get_config(args):
	config = BuildConfiguration.CompilationProperties()
	if args["cfg"]:
		config.load(args["directory"], args["cfg"])
	return config


def compile_cmd(args):
	load_project(args["directory"]).compile(get_config(args))


def run_cmd(args):
	project = load_project(args["directory"])
	cfg = get_config(args)
	project.compile(cfg)
	project.ProjectRun(cfg)


def clear_cmd(args):
	load_project(args["directory"]).clear(get_config(args))


def make_cfg_cmd(args):
	cfg = BuildConfiguration.CompilationProperties()
	cfg.read()
	name = input("Configuration name:")
	cfg.save(args["directory"], name)


commands = {
	"init": {
		"exec": init_cmd,
		"args": {
			"name": {"required": False, "default": "TempProject"},
			"type": {"required": False, "default": "binary"},
			"dep": {"required": False, "default": []},
			"files": {"required": False, "default": True}
		},
	},
	"compile": {"exec": compile_cmd, "args": {"cfg": {"required": False, "default": None}}},
	"run": {"exec": run_cmd, "args": {"cfg": {"required": False, "default": None}}},
	"configure": {"exec": make_cfg_cmd, "args": {}},
	"clear": {"exec": clear_cmd, "args": {"cfg": {"required": False, "default": None}}},
	"exit": {"exec": lambda: exit(0), "args": {}}
}


def parse_command(cmd_args):
	args_idx = 3

	if len(cmd_args) < 2:
		raise Errors.CBuildError("Expected working directory (optional) and a command")

	command = cmd_args[1]
	if command in commands:
		directory = os.path.abspath(".")
		args_idx -= 1
	else:
		directory = os.path.abspath(cmd_args[1])
		command = cmd_args[2]
		if not os.path.exists(directory):
			Errors.warn(f"Given path does not exists. Automatically creating working directory \"{directory}\"")
			os.makedirs(directory)
		if command not in commands:
			raise Errors.CBuildError(f"Command {command} is not recognized\n Commands are: {commands}")
	
	args = {}
	for arg in cmd_args[args_idx:]:
		if ':' in arg:
			name, value = arg.split(':')
			name = name.strip()
			value = value.strip()
			if name not in commands[command]["args"]:
				Errors.warn(f"Argument {name} is not recognized for command {command}")
			if name in args:
				args[name] = value
		else:
			raise Errors.CBuildError("Invalid Syntax must be name:value ")

	for arg_name, arg_info in commands[command]["args"].items():
		if arg_name not in args:
			if arg_info["required"]:
				raise Errors.CBuildError(f"Argument {arg_name} is required for command {command}")
			args[arg_name] = arg_info["default"]

	args["directory"] = directory
	return {"command": command, "args": args}


def run():
	# sys.argv += "example/binExample init name:App type:binary".split() if len(sys.argv) < 2 else []
	sys.argv += "example/binExample compile cfg:Debi64".split() if len(sys.argv) < 2 else []
	# sys.argv += "example/binExample clear cfg:Debi64".split() if len(sys.argv) < 2 else []
	# sys.argv += "example/binExample configure".split() if len(sys.argv) < 2 else []

	try:
		# parse and execute command
		command = parse_command(sys.argv)
		commands[command["command"]]["exec"](command["args"]) if command else None

	except (Errors.CBuildError, Toolchain.ToolchainError) as error:
		Errors.err(f"Unsuccessful run : {error.message}")


run()
