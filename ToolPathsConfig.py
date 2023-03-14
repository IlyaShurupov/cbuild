import os
import json
import subprocess

global_toolchains = None


def is_program_valid(program_name):
	try:
		with open(os.devnull, 'w') as devnull:
			return subprocess.call(["which", program_name], stdout=devnull, stderr=devnull) == 0
	except OSError:
		return False


def load():
	global global_toolchains
	file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paths.json")
	with open(file) as f:
		global_toolchains = json.load(f)

	# check if exists
	for key, toolchain in global_toolchains.items():
		for tool_name, tool_path in toolchain.items():
			if not is_program_valid(tool_path):
				if not ("unresolved" in toolchain):
					toolchain["unresolved"] = []
				toolchain["unresolved"].append(tool_name)


load()
