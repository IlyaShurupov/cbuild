import os
import shutil
import importlib.util
from pathlib import Path
import Errors
import Toolchain

global_project_path = "."


def file_mod_time(path):
	return Path(path).stat().st_mtime


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
		self.project_path = global_project_path
		self.project_dir = os.path.dirname(global_project_path)

		self.sources = self.find_files(".", [".cpp"])
		self.headers = self.find_files(".", [".hpp", ".h"])

	def find_files(self, relative_directory: str, extensions: list, recursive: bool = True) -> list:
		extensions = ["." + ext if not ext.startswith(".") else ext for ext in extensions]
		file_list = []
		directory = os.path.join(self.project_dir, relative_directory)
		for root, dirs, files in os.walk(directory):
			for file in files:
				if any(file.endswith(ext) for ext in extensions):
					file_path = os.path.join(root, file)
					if recursive or root == directory:
						# Add the file path to the list of found files
						file_list.append(os.path.relpath(file_path, self.project_dir))
		return file_list

	def load_dependencies(self, module_self):
		wd = self.push_wd()
		dependencies = []
		for dep in self.dependencies:

			# Load module
			filename, extension = os.path.splitext(dep)
			if extension == "":
				dep += ".py"
			path = os.path.abspath(dep)

			spec = importlib.util.spec_from_file_location(path, path)
			module = importlib.util.module_from_spec(spec)

			# Pass arguments to the module and execute it
			module.cbuild, module_self.global_project_path = module_self, path
			spec.loader.exec_module(module)

			# Initialize project and add it to dependencies
			project = module.Project()
			project.load_dependencies(module_self)
			dependencies.append(project)

		self.dependencies = dependencies
		self.pop_wd(wd)

	def absolute_lib_dir(self, config):
		return os.path.join(self.project_dir, self.library_output_directory, f"{self.name}-{config.name}")

	def absolute_bin_dir(self, config):
		return os.path.join(self.project_dir, self.output_directory, f"{self.name}-{config.name}")

	def absolute_temp_dir(self, config):
		return os.path.join(self.project_dir, self.temp_directory, f"{self.name}-{config.name}")

	def available_includes(self) -> list:
		includes = [os.path.join(self.project_dir, include_dir) for include_dir in self.public_directories]
		for dep in self.dependencies:
			includes += dep.available_includes()
		return includes

	def available_libraries(self, config) -> (list, list):
		libs = [Toolchain.library_name(self.name)] + self.additional_libraries
		lib_dirs = [self.absolute_lib_dir(config)] + self.additional_lib_dirs
		for dep in self.dependencies:
			dep_libs, dep_lib_dirs = dep.available_libraries(config)
			libs += dep_libs
			lib_dirs += dep_lib_dirs
		return libs, lib_dirs

	def success_time(self, config) -> int:
		return 0

	def compile_sources(self, forced, config) -> (bool, bool, list):
		wd = self.push_wd()

		if self.success_time(config):
			if self.success_time(config) < file_mod_time(self.project_path):
				Errors.log("Forcing rebuild of sources as project file has changed", 0)
				forced = True

		success_time = self.success_time(config)
		header_times = [file_mod_time(header) for header in self.headers]
		source_times = [file_mod_time(source) for source in self.sources]

		api_changed = any(header > success_time for header in header_times)
		src_changed = any(source > success_time for source in source_times)

		includes = self.available_includes() + self.additional_include_dirs
		outputs = [os.path.join(self.absolute_temp_dir(config), f"{os.path.splitext(src)[0]}.o") for src in self.sources]

		toolchain = Toolchain.get(config)

		forced |= api_changed

		for source, output, time in zip(self.sources, outputs, source_times):
			if forced or time > success_time:
				toolchain.compile_object(source, output, includes, self.preprocessor_definitions, config)
				Errors.log(f"{source} -> {os.path.relpath(output, self.project_dir)}", 0)
				src_changed = True

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
		os.chdir(self.project_dir)
		return temp_wd

	def pop_wd(self, wd: str):
		os.chdir(wd)


class LibraryProject(BaseProject):
	def __init__(self):
		super().__init__()

	def output_file(self, config):
		return os.path.join(self.absolute_lib_dir(config), Toolchain.library_name(self.name))

	def success_time(self, config):
		lib_path = self.output_file(config)
		return file_mod_time(lib_path) if os.path.exists(lib_path) else 0

	def compile(self, config, forced=False):
		wd = self.push_wd()
		Errors.log(f" == Building \'{self.name}\' == ", 0)

		dep_api_changed = False
		dep_lib_changed = False
		
		for dep in self.dependencies:
			api_change, lib_change = dep.ProjectCompile(config, forced)
			dep_api_changed |= api_change
			dep_lib_changed |= lib_change

		self_api_changed, self_lib_changed, objects = self.compile_sources(dep_api_changed, config)

		if self_lib_changed or self_api_changed or dep_api_changed or dep_lib_changed:
			toolchain = Toolchain.get(config)
			library_file = self.output_file(config)
			toolchain.package_objects(objects, library_file, config)
			Errors.log(f"{os.path.relpath(library_file, self.project_dir)}", 0)

		self.pop_wd(wd)
		return self_api_changed, (self_lib_changed or dep_lib_changed)


class BinaryProject(BaseProject):
	def __init__(self):
		super().__init__()

	def output_file(self, config):
		return os.path.join(self.absolute_bin_dir(config), Toolchain.executable_name(self.name))

	def success_time(self, config):
		path = self.output_file(config)
		return file_mod_time(path) if os.path.exists(path) else 0

	def compile(self, config, forced=False):
		wd = self.push_wd()
		Errors.log(f" == Building \'{self.name}\' == ", 0)

		if self.success_time(config):
			if os.path.exists(config.name + ".json") and self.success_time(config) < file_mod_time(config.name + ".json"):
				Errors.log("Forcing recursive rebuild as configuration has changed since last successful run", 0)
				forced = True

		dep_api_changed = False
		dep_lib_changed = False

		if len(self.dependencies):
			Errors.log("Building dependencies", 1)
			for dep in self.dependencies:
				api_change, lib_change = dep.compile(config, forced)
				dep_api_changed |= api_change
				dep_lib_changed |= lib_change
			Errors.log("Done building dependencies", 1)

		if dep_api_changed:
			Errors.log(f"Forcing rebuild of \'{self.name}\' as api of dependencies has changed", 1)
			forced = True

		self_api_changed, self_lib_changed, objects = self.compile_sources(forced, config)

		if self_lib_changed or dep_lib_changed or dep_api_changed or self_api_changed or forced:
			toolchain = Toolchain.get(config)

			# create static library
			library_output = os.path.join(self.absolute_lib_dir(config), Toolchain.library_name(self.name))
			toolchain.package_objects(objects, library_output, config)
			Errors.log(f"{os.path.relpath(library_output, self.project_dir)}", 0)

			# create executable
			libraries, library_search_directories = self.available_libraries(config)
			libraries.remove(Toolchain.library_name(self.name))
			library_search_directories.remove(self.absolute_lib_dir(config))
			toolchain.link_objects(objects, self.output_file(config), libraries, library_search_directories, config)
			Errors.log(f"{os.path.relpath(self.output_file(config), self.project_dir)}", 0)

		self.pop_wd(wd)

	def run(self, config):
		wd = self.push_wd()
		Toolchain.get(config).run(self.output_file(config))
		self.pop_wd(wd)

	def debug(self, config):
		wd = self.push_wd()
		Toolchain.get(config).debug(self.output_file(config))
		self.pop_wd(wd)
