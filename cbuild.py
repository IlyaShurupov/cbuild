import os
import sys
import importlib.util
import CbuildProjects
import shutil
import BuildConfiguration
import Errors
import Toolchain
import json


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
		f.write(project_sample_source.format(project_type.__name__, args["name"]))

	if args["add-files"] != "False":
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
	cbuild_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), args["cfg"] + ".json")
	user_config = os.path.join(args["directory"], args["cfg"] + ".json")

	if os.path.exists(user_config):
		config.load(args["directory"], args["cfg"])
	else:
		config.load(os.path.dirname(os.path.abspath(__file__)), args["cfg"])

	return config


def compile_cmd(args):
	load_project(args["directory"]).compile(get_config(args))


def recompile_cmd(args):
	load_project(args["directory"]).compile(get_config(args), True)


def run_cmd(args):
	project = load_project(args["directory"])
	cfg = get_config(args)
	project.compile(cfg)
	project.run(cfg)


def debug_cmd(args):
	project = load_project(args["directory"])
	cfg = get_config(args)
	project.compile(cfg)
	project.debug(cfg)


def clear_cmd(args):
	load_project(args["directory"]).clear(get_config(args))


def make_cfg_cmd(args):
	cfg = BuildConfiguration.CompilationProperties()
	cfg.read()
	name = input("Configuration name:")
	cfg.save(args["directory"], name)


def set_cfg_cmd(args):
	file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DefaultConfig.json")
	with open(file_path, 'w') as file:
		json.dump({"default-config": args["cfg"]}, file)


commands = {}


def initialize_commands():
	global commands

	default_config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DefaultConfig.json")
	with open(default_config_file) as f:
		config = json.load(f)
	default_config_name = config["default-config"]

	commands = {
		"init": {"exec": init_cmd, "args": {"name": None, "type": None, "add-files": "False"}},
		"configure": {"exec": make_cfg_cmd, "args": {}},
		"compile": {"exec": compile_cmd, "args": {"cfg": default_config_name}},
		"clear": {"exec": clear_cmd, "args": {"cfg": default_config_name}},
		"recompile": {"exec": recompile_cmd, "args": {"cfg": default_config_name}},
		"run": {"exec": run_cmd, "args": {"cfg": default_config_name}},
		"debug": {"exec": debug_cmd, "args": {"cfg": default_config_name}},
		"set-default-config": {"exec": set_cfg_cmd, "args": {"cfg": None}},
	}


command_macros = {
	"init": ["i", "ini", "initialize"],
	"configure": ["cfg", "config"],
	"compile": ["c", "build", "b"],
	"clear": ["clean", "del", "delete"],
	"recompile": ["rebuild", "rb", "rc"],
	"run": ["r"],
	"debug": ["dbg", "deb"],
	"set-default-config": ["set"]
}


def command_descr(cmd_name, cmd) -> str:
	args = cmd['args']
	out = f"{cmd_name} {command_macros[cmd_name]}:\n"
	if args:
		for arg_name, arg_val in args.items():
			default_val = str(arg_val) if arg_val is not None else "(required)"
			out += f"\t{arg_name} : {default_val}\n"
	else:
		out += "\tNo arguments\n"
	return out


def commands_descr() -> str:
	out = "Commands:\n"
	for cmd_name, cmd in commands.items():
		out += command_descr(cmd_name, cmd)
	return out


def parse_command(cmd_args):
	if len(cmd_args) < 2:
		raise Errors.CBuildError("\nInvalid invocation. Must be <working-directory> <command-name> <arg-1> ... <arg-n>")

	directory = cmd_args[0]
	if not os.path.exists(directory):
		raise Errors.CBuildError(f"\nSpecified working directory does not exists. Given '{directory}'")

	command = cmd_args[1]
	if not (command in commands):
		for name, val in command_macros.items():
			for macro in val:
				if macro == command:
					command = name
					break

		if not (command in commands):
			raise Errors.CBuildError(f"\nCant resolve command.\n {commands_descr()}")

	args = {}
	args_passed = [arg for arg in cmd_args[2:]]
	for arg_name, arg_val in commands[command]["args"].items():
		if not(arg_val is None):
			if not len(args_passed):
				args[arg_name] = arg_val
			else:
				args[arg_name] = args_passed.pop(0)
		else:
			if not len(args_passed):
				raise Errors.CBuildError(f"\nToo few arguments given for the command: {command_descr(command, commands[command])}")
			else:
				args[arg_name] = args_passed.pop(0)

	if len(args_passed):
		raise Errors.CBuildError(f"\nToo many arguments given:\n for command: {command_descr(command, commands[command])}")

	args["directory"] = directory
	return {"command": command, "args": args}


def run():
	# sys.argv += "example/App init App binary true".split()
	# sys.argv += "example/App c".split()
	# sys.argv += "example/binExample clear cfg:Debi64".split()
	# sys.argv += "example/App debug cfg:Debug-Intel-64".split()
	# sys.argv += ". configure".split()

	try:
		# parse and execute command
		command = parse_command(sys.argv[1:])
		commands[command["command"]]["exec"](command["args"]) if command else None

	except (Errors.CBuildError, Toolchain.ToolchainError) as error:
		Errors.err(f"Unsuccessful run : {error}")


initialize_commands()
run()
