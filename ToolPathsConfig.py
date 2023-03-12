import os
import json

global_toolchains = None


def load():
	global global_toolchains
	file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paths.json")
	with open(file) as f:
		global_toolchains = json.load(f)

	# check if exists
	for key, toolchain in global_toolchains:
		for tool in toolchain.keys():
			if not os.path.exists(toolchain[tool]):
				if not ("unresolved" in toolchain):
					toolchain["unresolved"] = []
				toolchain["unresolved"].append(tool)


load()
