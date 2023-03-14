import os
import subprocess
import ToolPathsConfig as ToolPath
from BuildConfiguration import CompilationProperties
import Errors
import platform

if platform.system() == 'Windows':
	LIB_EXT = '.lib'
	LIB_PREFIX = ''

	SLIB_EXT = '.dll'
	EXE_EXT = '.exe'
elif platform.system() == 'Darwin' or platform.system() == 'Linux':
	LIB_EXT = '.a'
	LIB_PREFIX = 'lib'

	SLIB_EXT = '.so'
	EXE_EXT = ''
else:
	raise OSError('Unsupported operating system')


def library_name(name) -> str:
	return LIB_PREFIX + name + LIB_EXT


def executable_name(name) -> str:
	return name + EXE_EXT


def shared_object_name(name) -> str:
	return name + SLIB_EXT


class ToolchainError(Exception):
	def __init__(self, message):
		super().__init__(message)


def clear_output(output):
	if os.path.exists(output):
		os.remove(output)


def check_output(output):
	if not os.path.exists(output):
		raise ToolchainError("Build terminated because of compilation errors")


def run_command(command: list) -> None:
	result = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	Errors.log(result.stdout.decode()) if len(result.stdout) > 0 else None
	Errors.log(result.stderr.decode()) if len(result.stderr) > 0 else None


class Toolchain:
	def __init__(self):
		self.name = None

	def check_tools(self):
		if "unresolved" in ToolPath.global_toolchains[self.name]:
			raise ToolchainError("Unresolved paths for {name} toolset : " + str(ToolPath.global_toolchains[self.name]["unresolved"]))

	def tool_path(self, tool_name):
		self.check_tools()
		return ToolPath.global_toolchains[self.name][tool_name]

	def compile_object(self, source, output, includes, definitions, config):
		pass

	def package_objects(self, objects, output, config):
		pass

	def link_objects(self, objects, output, libraries, library_directories, config):
		pass

	def run(self, executable_file):
		pass

	def debug(self, executable_file):
		pass


class LLVMToolchain(Toolchain):

	def __init__(self):
		super().__init__()
		self.name = "llvm"
		self.options_map = {
				"optimization": {"0": "-O0", "1": "-O1", "2": "-O2", "3": "-O3", "fast": "-Ofast", "size": "-Os"},
				"debug": {"True": "-g"},
				"std": {"11": "-std=c++11", "17": "-std=c++17", "20": "-std=c++20", "latest": "-std=c++20"},
				"arch": {"intel": "-march=native", "arm": "-march=armv7-a"},
				"register": {"64": "-m64", "32": "-m32"},
		}

	def option(self, name: str, config: CompilationProperties) -> str:
		if getattr(config, name) in self.options_map[name]:
			return self.options_map[name][getattr(config, name)]
		return ""

	def compile_object(self, source, output, includes, definitions, config: CompilationProperties):
		self.check_tools()
		clear_output(output)

		command = [self.tool_path("clang++"), source, "-c", "-o", output]
		for include in includes:
			command.append("-I")
			command.append(include)
		for define in definitions:
			command.append("-D")
			command.append(define)
		command.append(self.option("debug", config))
		command.append(self.option("optimization", config))
		command.append(self.option("std", config))
		command.append(self.option("arch", config))
		command.append(self.option("register", config))

		if not os.path.exists(os.path.dirname(output)):
			os.makedirs(os.path.dirname(output))

		run_command(command)
		check_output(output)

	def package_objects(self, objects, output, config: CompilationProperties):
		self.check_tools()
		clear_output(output)

		command = [self.tool_path("llvm-ar"), "rcs", output]
		command.extend(objects)

		if not os.path.exists(os.path.dirname(output)):
			os.makedirs(os.path.dirname(output))

		run_command(command)
		check_output(output)

	def link_objects(self, objects, output, libraries, library_directories, config: CompilationProperties):
		clear_output(output)
		self.check_tools()

		command = [self.tool_path("clang++")]
		command.extend(objects)
		for library_directory in library_directories:
			command.append("-L" + library_directory)
		for library in libraries:

			if library.startswith("lib") and library.endswith(".a"):
				library_striped = library[len("lib"):-len(".a")]
			else:
				library_striped = library

			command.append("-l" + library_striped)

		command.append("-o")
		command.append(output)
		command.append(self.option("debug", config))
		command.append(self.option("optimization", config))
		command.append(self.option("std", config))
		command.append(self.option("arch", config))
		command.append(self.option("register", config))

		if not os.path.exists(os.path.dirname(output)):
			os.makedirs(os.path.dirname(output))

		run_command(command)
		check_output(output)

	def run(self, executable_file):
		self.check_tools()
		check_output(executable_file)
		run_command([executable_file])

	def debug(self, executable_file):
		self.check_tools()
		cmd = [self.tool_path("lldb"), executable_file]
		subprocess.call(['gnome-terminal', '--', 'bash', '-c', ' '.join(cmd) + '; exec bash'])


global_toolchains = [LLVMToolchain()]


def get(config) -> Toolchain:
	for toolchain in global_toolchains:
		if toolchain.name == config.toolchain:
			return toolchain
	raise ToolchainError("Specified toolchain is not recognized")