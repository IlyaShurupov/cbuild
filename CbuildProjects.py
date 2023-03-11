from argparse import ArgumentError
import os
import subprocess
import shutil
import importlib.util
from pathlib import Path
import json

project_directory = None

class BuildConfiguration():
	def __init__(self):

		self.descriptions = {
			"arch" : "Instruction set",
			"register" : "Register size",
			"debug" : "Produce debug information",
			"optimization" : "Desired optimization",
			"additional_compile" : "Additional object compilation flags",
			"additional_link" : "Additional object linking flags",
		}

		self.interface = {
			"arch" : [ "intel", "arm" ],
			"register" : [ "64", "32" ],
			"debug" : [ "True", "False" ],
			"optimization" : [ "0", "1", "2", "3", "size", "speed" ],
			"additional_compile" : [],
			"additional_link" : [],
		}

		self.default = {
			"name" : "Reli64",
			"arch" : "intel",
			"register" : "64",
			"debug" : "False",
			"optimization" : "speed",
			"additional_compile" : [],
			"additional_link" : [],
		}

		self.config = self.default

	def getOptimization(self):
		opt = self.config["optimization"]
		if opt == "size" or opt == "speed":
			return "-Os" if opt == "size" else "-Ofast"
		else:
			return "-O" + opt

	def getDebugOption(self):
		return "-g" if self.config["debug"] == "True" else ""


	def load(self, absolute_directory_path, name):
		absolute_path = os.path.join(absolute_directory_path, name + ".json")

		if not os.path.exists(absolute_path):
			return None

		with open(absolute_path, "r") as f:
			self.config = json.load(f)
				
		# Check if all required options are present and have valid values
		for option, value in self.interface.items():
			if option != "additional_compile" and option != "additional_link":
				if option not in self.config:
					print(f"Missing required option '{option}' in '{absolute_path}'")
					return None
				if self.config[option] not in value:
					print(f"Invalid value '{self.config[option]}' for option '{option}' in '{absolute_path}'")
					return None
	
		if "additional_compile" in self.config and not (self.config["additional_compile"] is list):
			print(f"Invalid value for additional compile flags - must be a list")
			return None
		if "additional_link" in self.config and not (self.config["additional_link"]["link"] is list):
			print(f"Invalid value for additional link flags - must be a list")
			return None

		self.config["name"] = name
		return True

	def read_from_comsole(self):
		self.config = {}
		for option in self.interface:
			while True:
				value = input(f"{option} ({', '.join(self.interface[option])}, default {self.default[option]}): ")
				if not value:
					value = self.default[option]
				if value in self.interface[option]:
					self.config[option] = value
					break
				else:
					print(f"Invalid value for {option}. Please enter a valid value.")
				
		if "additional_flags" in self.config:
			for flags in self.config["additional_flags"]:
				while True:
					value = input(f"{flags} (default is blank): ")
					if value:
						self.config["additional_flags"][flags] = value.split()
						break
					else:
						break

	def save(self, absolute_directory_path, config_name):
		file_path = os.path.join(absolute_directory_path, config_name + ".json")
		with open(file_path, 'w') as file:
				json.dump(self.config, file, indent=2)


class BaseProject():
	def __init__(self):

		# project configuration
		self.name = "Temp"
		self.public_directories = [ "public", "inc", "include" ]
		self.ignore_directories = [ "tmp", "temp", "ignore" ]
		self.output_directory = "bin"
		self.library_output_directory = "lib"
		self.temp_directory = os.path.join(self.library_output_directory, "tmp")
		self.sources = []
		self.headers = []
		self.dependencies = []
		self.preprocessor_definitions = []
		self.additional_include_dirs = []
		self.additional_compile_flags = []
		self.additional_lib_dirs = []
		self.additional_libraries = []
		self.project_path = project_directory
		
		# init project configuration with defaults
		self.ProjectInitDefault()

	def ProjectInitDefault(self):
		wd = self.pushWD()
		for root, dirs, files in os.walk("."):
			for filename in files:
				if filename.endswith(".cpp") or filename.endswith(".c"):
					if not any(d in root for d in self.ignore_directories):
						self.sources.append(os.path.normpath(os.path.join(root, filename)))
				elif filename.endswith(".h") or filename.endswith(".hpp"):
					if not any(d in root for d in self.ignore_directories):
						self.headers.append(os.path.normpath(os.path.join(root, filename)))
		self.popWD(wd)

	def ProjectLoadDependencies(self, cbuild):
		wd = self.pushWD()

		dependencies = []
		for dep in self.dependencies:

			# load module
			path = os.path.abspath(os.path.join(dep, "cproj.py"))
			spec = importlib.util.spec_from_file_location(path, path)
			module = importlib.util.module_from_spec(spec)

			# pass arguments to the module
			module.cbuild = cbuild
			cbuild.project_directory = os.path.abspath(dep)

			# execute module
			spec.loader.exec_module(module)

			# initialize project
			project = module.Project()
			project.ProjectLoadDependencies(cbuild)

			dependencies.append(project)

		self.popWD(wd)

		self.dependencies = dependencies

	def getDepPublicIncludes(self):
		includes = []
		for include_dir in self.public_directories:
			includes.append(os.path.join(self.project_path, include_dir))

		for dep in self.dependencies:
			includes += dep.getDepPublicIncludes()

		return includes

	def getDepPublicLibraries(self, config):
		libs = [ self.name + ".lib" ] + self.additional_libraries
		lib_dirs = [ self.getAbsoluteLibDir(config) ] + self.additional_lib_dirs

		for dep in self.dependencies:
			lib, dirs = dep.getDepPublicLibraries(config)
			libs += lib
			lib_dirs += dirs

		return libs, lib_dirs

	def getAbsoluteLibDir(self, config):
		cfg_name = config.config["name"]
		return os.path.join(self.project_path, self.library_output_directory, f"{self.name}_{cfg_name}")

	def getAbsoluteBinDir(self, config):
		cfg_name = config.config["name"]
		return os.path.join(self.project_path, self.output_directory, f"{self.name}_{cfg_name}")

	def getAbsoluteTempDir(self, config):
		cfg_name = config.config["name"]
		return os.path.join(self.project_path, self.temp_directory, f"{self.name}_{cfg_name}")

	def ProjectCompileObjects(self, foresed, config):
		
		def lastBuildTime(config):
			exe_path = os.path.join(self.getAbsoluteBinDir(config), self.name + ".exe")
			bin_path = os.path.join(self.getAbsoluteBinDir(config), self.name + ".dll")
			lib_path = os.path.join(self.getAbsoluteLibDir(config), self.name + ".lib")

			if os.path.exists(exe_path):
				return Path(exe_path).stat().st_mtime
			if os.path.exists(bin_path):
				return Path(bin_path).stat().st_mtime
			if os.path.exists(lib_path):
				return Path(lib_path).stat().st_mtime

			return 0
		
		def compileObject(source, obj, project_args, config):
			compile_command = ["clang++", "-c"]
			compile_command.append(config.getDebugOption())
			compile_command.append(config.getOptimization())
			compile_command += project_args + [source, "-o", obj]

			# Check if the directory exists
			dir_path = os.path.dirname(obj)
			if not os.path.exists(dir_path):
					os.makedirs(dir_path)
		
			if os.path.exists(obj):
					os.remove(obj)

			self.runCmd(compile_command)
			print(source)

		wd = self.pushWD()

		last_time = lastBuildTime(config)

		api_changed = False

		for header in self.headers:
			header_time = Path(header).stat().st_mtime
			if header_time > last_time:
				api_changed = True
				break

		src_changed = False
		for source in self.sources:
			src_time = Path(source).stat().st_mtime
			if  src_time > last_time:
				src_changed = True
				break


		# Compile the sources
		compile_command = []
		if foresed or api_changed or src_changed:
			# Add preprocessor definitions to the compile command
			for define in self.preprocessor_definitions:
				compile_command.append("-D" + define)

			# Add additional include directories to the compile command	
			for include_dir in self.getDepPublicIncludes():
				compile_command.append("-I" + include_dir)

			for dep in self.dependencies:
				for include_dir in dep.getDepPublicIncludes():
					compile_command.append("-I" + include_dir)

			for include_dir in self.additional_include_dirs:
				compile_command.append("-I" + include_dir)

			# Add additional compile flags to the compile command
			compile_command.extend(self.additional_compile_flags)

		objects = []
		for source in self.sources:
			object_file = os.path.join(self.getAbsoluteTempDir(config),  os.path.splitext(source)[0] + ".o")
			objects.append(object_file)

		for source, obj in zip(self.sources, objects):
			if foresed or api_changed or Path(source).stat().st_mtime > last_time:
				compileObject(source, obj, compile_command, config)

		self.popWD(wd)
		return api_changed, src_changed, objects


	def ProjectClear(self, config):
		wd = self.pushWD()
		dirs = [ self.getAbsoluteTempDir(config), self.getAbsoluteBinDir(config), self.getAbsoluteLibDir(config) ]
		for directory in dirs:
			if os.path.exists(directory):
				shutil.rmtree(directory)
		self.popWD(wd)

	def ProjectRecompile(self, config):
		wd = self.pushWD()
		self.ProjectClear(config)
		self.ProjectCompile(config)
		self.popWD(wd)

	def pushWD(self):
		temp_wd = os.getcwd()
		os.chdir(self.project_path)
		return temp_wd

	def popWD(self, wd):
		os.chdir(wd)

	def runCmd(self, cmd):
		result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		# Print the output to the console
		if len(result.stdout) > 0:
				print(result.stdout.decode())
		if len(result.stderr) > 0:
				print(result.stderr.decode())

class LibraryProject(BaseProject):
	def __init__(self):
		super().__init__()

	def ProjectCompile(self, config):
		wd = self.pushWD()

		dep_api_changed = False
		dep_lib_changed = False
		
		for dep in self.dependencies:
			api_change, lib_change = dep.ProjectCompile(config)
			dep_api_changed |= api_change
			dep_lib_changed |= lib_change

		self_api_changed, self_lib_changed, objects = self.ProjectCompileObjects(dep_api_changed, config)

		if self_lib_changed or self_api_changed or dep_api_changed or dep_lib_changed:
			# Link the object files into a library
			lib_dir = self.getAbsoluteLibDir(config)
			library_file = os.path.join(lib_dir, self.name + ".lib")
			if not os.path.exists(lib_dir):
				os.makedirs(lib_dir)

			link_cmd = ' '.join(map(str, ["llvm-ar", "rcs", library_file] + objects))
			self.runCmd(link_cmd)
			print(os.path.relpath(library_file, self.project_path))

		self.popWD(wd)

		return self_api_changed, self_lib_changed or dep_lib_changed


class BinaryProject(BaseProject):
	def __init__(self):
		super().__init__()

	def ProjectCompile(self, config):
		wd = self.pushWD()

		dep_api_changed = False
		dep_lib_changed = False
		
		for dep in self.dependencies:
			api_change, lib_change = dep.ProjectCompile(config)
			dep_api_changed |= api_change
			dep_lib_changed |= lib_change

		self_api_changed, self_lib_changed, objects = self.ProjectCompileObjects(dep_api_changed, config)

		outdir = self.getAbsoluteBinDir(config)

		if self_lib_changed or dep_lib_changed or dep_api_changed or self_api_changed:
			# Create the output directory if it doesn't exist
			if not os.path.exists(outdir):
				os.makedirs(outdir)

			# Link the object files into a library
			lib_dir = self.getAbsoluteLibDir(config)
			if not os.path.exists(lib_dir):
				os.makedirs(lib_dir)
			library_file = os.path.join(lib_dir, f"{self.name}.lib")
			link_cmd = ' '.join(map(str, ["llvm-ar", "rcs", library_file] + objects))
			self.runCmd(link_cmd)
			print(os.path.relpath(library_file, self.project_path))

			# Link the objects to create the binary
			binary_file = os.path.join(outdir, self.name + ".exe")
			link_command = ["clang++"]
			link_command.append(config.getDebugOption())
			link_command.append(config.getOptimization())
			link_command += ["-o", binary_file] + objects

			libs, lib_dirs = [] + self.additional_libraries, [] + self.additional_lib_dirs
			for dep in self.dependencies: 
				dep_libs, dep_lib_dirs = dep.getDepPublicLibraries(config)
				libs += dep_libs
				lib_dirs += dep_lib_dirs

			# Add additional library directories to the link command
			for lib_dir in lib_dirs:
				link_command.append("-L" + lib_dir)

			# Add additional libraries to the link command
			for lib in libs:
				link_command.append("-l" + lib)

			self.runCmd(link_command)
			print(os.path.relpath(binary_file, self.project_path))

		self.popWD(wd)

	def ProjectRun(self, config):
		wd = self.pushWD()
		filepath = os.path.join(self.getAbsoluteBinDir(config), self.name + ".exe")
		process = subprocess.Popen(filepath, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		while True:
				output = process.stdout.readline()
				if output == b'' and process.poll() is not None:
						break
				if output:
						print(output.decode().strip())
		return_code = process.wait()
		print("Process exited with return code:", return_code)
		self.popWD(wd)
