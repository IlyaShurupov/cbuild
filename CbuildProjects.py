import os
import shutil
import importlib.util
from pathlib import Path
import Toolchain

global_project_directory = None


class BaseProject:
	def __init__(self):
		# project configuration
		self.name = "Temp"
		self.public_directories = ["public", "inc", "include"]
		self.ignore_directories = ["tmp", "temp", "ignore"]
		self.output_directory = "bin"
		self.library_output_directory = "lib"
		self.temp_directory = os.path.join(self.library_output_directory, "tmp")
		self.sources = []
		self.headers = []
		self.dependencies = []
		self.preprocessor_definitions = []
		self.additional_include_dirs = []
		self.additional_lib_dirs = []
		self.additional_libraries = []
		self.project_path = global_project_directory

		self.add_files_from_directory()

	def add_files_from_directory(self):
		wd = self.push_wd()
		for root, dirs, files in os.walk("."):
			for filename in files:
				if filename.endswith(".cpp") or filename.endswith(".c"):
					if not any(d in root for d in self.ignore_directories):
						self.sources.append(os.path.normpath(os.path.join(root, filename)))
				elif filename.endswith(".h") or filename.endswith(".hpp"):
					if not any(d in root for d in self.ignore_directories):
						self.headers.append(os.path.normpath(os.path.join(root, filename)))
		self.pop_wd(wd)

	def load_dependencies(self, module_self):
		wd = self.push_wd()
		dependencies = []
		for dep in self.dependencies:
			# Load module
			path = os.path.abspath(os.path.join(dep, "cproj.py"))
			spec = importlib.util.spec_from_file_location(path, path)
			module = importlib.util.module_from_spec(spec)

			# Pass arguments to the module and execute it
			module.cbuild, module_self.global_project_directory = module_self, os.path.abspath(dep)
			spec.loader.exec_module(module)

			# Initialize project and add it to dependencies
			project = module.Project()
			project.project_load_dependencies(module_self)
			dependencies.append(project)

		self.dependencies = dependencies
		self.pop_wd(wd)

	def absolute_lib_dir(self, config):
		cfg_name = config.config["name"]
		return os.path.join(self.project_path, self.library_output_directory, f"{self.name}_{cfg_name}")

	def absolute_bin_dir(self, config):
		cfg_name = config.config["name"]
		return os.path.join(self.project_path, self.output_directory, f"{self.name}_{cfg_name}")

	def absolute_temp_dir(self, config):
		cfg_name = config.config["name"]
		return os.path.join(self.project_path, self.temp_directory, f"{self.name}_{cfg_name}")

	def available_includes(self) -> list:
		includes = [os.path.join(self.project_path, include_dir) for include_dir in self.public_directories]
		for dep in self.dependencies:
			includes += dep.available_includes()
		return includes

	def available_libraries(self, config) -> (list, list):
		libs = [self.name + ".lib"] + self.additional_libraries
		lib_dirs = [self.absolute_lib_dir(config)] + self.additional_lib_dirs
		for dep in self.dependencies:
			dep_libs, dep_lib_dirs = dep.available_libraries(config)
			libs += dep_libs
			lib_dirs += dep_lib_dirs
		return libs, lib_dirs

	def compile_sources(self, forced, config) -> (bool, bool, list):
		wd = self.push_wd()

		exe_path = os.path.join(self.absolute_bin_dir(config), self.name + ".exe")
		bin_path = os.path.join(self.absolute_bin_dir(config), self.name + ".dll")
		lib_path = os.path.join(self.absolute_lib_dir(config), self.name + ".lib")

		success_time = max([Path(path).stat().st_mtime for path in [exe_path, bin_path, lib_path] if os.path.exists(path)], default=0)
		header_times = [Path(header).stat().st_mtime for header in self.headers]
		source_times = [Path(source).stat().st_mtime for source in self.sources]

		api_changed = any(header > success_time for header in header_times)
		src_changed = any(source > success_time for source in source_times)

		includes = self.available_includes() + self.additional_include_dirs
		outputs = [os.path.join(self.absolute_temp_dir(config), f"{os.path.splitext(src)[0]}.o") for src in self.sources]

		toolchain = Toolchain.get(config)

		for source, output, time in zip(self.sources, outputs, source_times):
			if forced or api_changed or time > success_time:
				toolchain.compile_object(source, output, includes, self.preprocessor_definitions, config)

		self.pop_wd(wd)
		return api_changed, src_changed, outputs

	def clear(self, config):
		wd = self.push_wd()
		dirs = [self.absolute_temp_dir(config), self.absolute_bin_dir(config), self.absolute_lib_dir(config)]
		for directory in dirs:
			if os.path.exists(directory):
				shutil.rmtree(directory)
		self.pop_wd(wd)

	def compile(self, config):
		pass

	def recompile(self, config):
		self.clear(config)
		self.compile(config)

	def push_wd(self) -> str:
		temp_wd = os.getcwd()
		os.chdir(self.project_path)
		return temp_wd

	def pop_wd(self, wd: str):
		os.chdir(wd)


class LibraryProject(BaseProject):
	def __init__(self):
		super().__init__()

	def compile(self, config):
		wd = self.push_wd()

		dep_api_changed = False
		dep_lib_changed = False
		
		for dep in self.dependencies:
			api_change, lib_change = dep.ProjectCompile(config)
			dep_api_changed |= api_change
			dep_lib_changed |= lib_change

		self_api_changed, self_lib_changed, objects = self.compile_sources(dep_api_changed, config)

		if self_lib_changed or self_api_changed or dep_api_changed or dep_lib_changed:
			toolchain = Toolchain.get(config)
			library_file = os.path.join(self.absolute_lib_dir(config), self.name + ".lib")
			toolchain.package_objects(objects, library_file, config)

		self.pop_wd(wd)
		return self_api_changed, self_lib_changed or dep_lib_changed


class BinaryProject(BaseProject):
	def __init__(self):
		super().__init__()

	def output_file(self, config):
		return os.path.join(self.absolute_bin_dir(config), self.name + ".exe")

	def compile(self, config):
		wd = self.push_wd()

		dep_api_changed = False
		dep_lib_changed = False
		for dep in self.dependencies:
			api_change, lib_change = dep.ProjectCompile(config)
			dep_api_changed |= api_change
			dep_lib_changed |= lib_change

		self_api_changed, self_lib_changed, objects = self.compile_sources(dep_api_changed, config)

		if self_lib_changed or dep_lib_changed or dep_api_changed or self_api_changed:
			toolchain = Toolchain.get(config)

			# create static library
			toolchain.package_objects(objects, os.path.join(self.absolute_lib_dir(config), self.name + ".lib"), config)
			# create executable
			libraries, library_search_directories = self.available_libraries(config)
			toolchain.link_objects(objects, self.output_file(config), libraries, library_search_directories, config)

		self.pop_wd(wd)

	def run(self, config):
		wd = self.push_wd()
		Toolchain.get(config).run(self.output_file(config))
		self.pop_wd(wd)
