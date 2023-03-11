import os
import sys
import importlib.util
import CbuildProjects as cbuild
import shutil

def loadProject(directory):
	module_file = os.path.join(directory, "cproj.py")
	
	if not os.path.exists(module_file):
		return None

	# load module
	module_name = module_file
	spec = importlib.util.spec_from_file_location(module_name, module_file)
	module = importlib.util.module_from_spec(spec)

	# pass arguments to the module
	module.cbuild = cbuild
	cbuild.project_directory = os.path.abspath(directory)

	# execute module
	spec.loader.exec_module(module)

	# initialize project
	project = module.Project()
	project.ProjectLoadDependencies(cbuild)

	return project

def initCmd(args):
	current_file_dir = os.path.dirname(os.path.abspath(__file__))
	directory = args["directory"]
	project = loadProject(directory)

	if project:
		print("Project Already Exists")
	# Create the file in the specified directory with the given name
	filename = os.path.join(directory, "cproj.py")
	
	if not os.path.exists(directory):
		os.makedirs(directory)

	with open(filename, "w") as f:
		# Write the initial code to the file
		project_type = getattr(cbuild, args["type"].capitalize() + "Project")
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


def getConfig(args):
	config = cbuild.BuildConfiguration()
	if args["cfg"]:
		if not config.load(args["directory"], args["cfg"]):
			cfg_name = args["cfg"]
			print(f"Could not load configuration {cfg_name}")
			return
	return config

def compileCmd(args):
	project = loadProject(args["directory"])
	if not project:
		print("Could not load project")
		return

	if cfg := getConfig(args): 
		project.compile(cfg)

def runCmd(args):
	project = loadProject(args["directory"])
	if not project:
		print("Could not load project")
		return

	if cfg := getConfig(args): 
		project.compile(cfg)
		project.ProjectRun(cfg)

def clearCmd(args):
	project = loadProject(args["directory"])
	if not project:
		print("Could not load project")
		return

	if cfg := getConfig(args): 
		project.clear(cfg)

def makeCfgCmd(args):
	cfg = cbuild.BuildConfiguration()
	cfg.read_from_comsole()
	name = input("Configuration name:")
	cfg.save(args["directory"], name)

commands = {
	"init": {
		"exec": initCmd,
		"args": {
			"name": { "required": False, "default" : "TempProject" },
			"type": { "required": False, "default": "binary" },
			"dep": { "required": False, "default": [] },
			"files" : { "required": False, "default": True }
		},
	},
	"compile" : { "exec" : compileCmd, "args" : { "cfg" : { "required": False, "default" : None } } },
	"run" : { "exec" : runCmd, "args" : { "cfg" : { "required": False, "default" : None } }, },
	"makecfg" : {  "exec" : makeCfgCmd,  "args" : {} },
	"clear" : { "exec" : clearCmd, "args" : { "cfg" : { "required": False, "default" : None } } },
	"exit" : { "exec" : lambda : exit(0), "args" : {}	}
}

def parseCommandLine(cmd_args):
	directory = None
	args_idx = 3

	if len(cmd_args) < 2:
		print("Expected working directory (optional) and a command")
		return

	command = cmd_args[1]
	if command in commands:
		directory = "."
		args_idx -= 1
	else:
		directory = cmd_args[1]
		command = cmd_args[2]
		if not os.path.exists(directory):
			print(f"Given path does not exists. Automatically creating working directory \"{directory}\"")
			os.makedirs(directory)
		if command not in commands:
			print(f"Command {command} is not recognized")
			print(f"Commands are: \n", commands)
			return
	
	args = {}
	for arg in cmd_args[args_idx:]:
		if ':' in arg:
			name, value = arg.split(':')
			name = name.strip()
			value = value.strip()
			if name not in commands[command]["args"]:
				print(f"Argument {name} is not recognized for command {command}")
				return
			if name in args:
				print(f"Argument {name} passed more than one time")
				return
			args[name] = value
		else:
			print("Invalid Syntax must be name:value ")
			return

	for arg_name, arg_info in commands[command]["args"].items():
		if arg_name not in args:
			if arg_info["required"]:
				print(f"Argument {arg_name} is required for command {command}")
				return
			else:
				args[arg_name] = arg_info["default"]

	args["directory"] = directory
	return {"command": command, "args": args}


#sys.argv += "example/libExample init name:Util type:library".split() if len(sys.argv) < 2 else []
#sys.argv += "example/binExample compile cfg:Debi64".split() if len(sys.argv) < 2 else []
sys.argv += "example/binExample clear cfg:Debi64".split() if len(sys.argv) < 2 else []

# parse and execute command		
command = parseCommandLine(sys.argv)
res = commands[command["command"]]["exec"](command["args"]) if command else 0
