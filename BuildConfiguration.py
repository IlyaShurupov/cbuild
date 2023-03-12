import json
import os
import Errors


class CompilationProperties:

	interface = {
		"toolchain": ["llvm"],
		"std": ["11", "17", "20", "latest"],
		"arch": ["intel", "arm"],
		"register": ["64", "32"],
		"debug": ["True", "False"],
		"optimization": ["0", "1", "2", "3", "size", "speed"],
		"additional_compile": [],
		"additional_link": [],
	}

	def __init__(self):
		self.name = "Intel-64-Release"
		"""Configuration ID"""
		self.toolchain = "llvm"
		"""Tools to use when compiling, linking and debugging"""
		self.std = "latest"
		"""C++ language standard"""
		self.arch = "intel"
		"""Instruction set"""
		self.register = "64"
		"""Register size"""
		self.debug = "False"
		"""Produce debug information"""
		self.optimization = "speed"
		"""Desired optimization"""
		self.additional_compile = []
		"""Additional object compilation flags"""
		self.additional_link = []
		"""Additional object linking flags"""

	def load(self, absolute_directory_path, name):
		# Load configuration file into json
		config_path = os.path.join(absolute_directory_path, name + ".json")
		if not os.path.exists(config_path):
			raise Errors.CBuildError("Configuration file does not exists")
		with open(config_path) as f:
			config = json.load(f)

		# Validate required options
		for option in self.interface.keys() - {"additional_compile", "additional_link"}:
			value = config[option]
			if not value:
				raise Errors.CBuildError(f"Missing required option '{option}' in '{config_path}'")
			if value not in self.interface[option]:
				raise Errors.CBuildError(f"Invalid value '{value}' for option '{option}' in '{config_path}'")

		# Validate additional compile and link flags
		for flag_name in ["additional_compile", "additional_link"]:
			flags = config[flag_name]
			if flags and not isinstance(flags, list):
				raise Errors.CBuildError(f"Invalid value for {flag_name} flags - must be a list")

		config["name"] = name

		self.name = config["name"]
		self.toolchain = config["toolchain"]
		self.std = config["std"]
		self.arch = config["arch"]
		self.register = config["register"]
		self.debug = config["debug"]
		self.optimization = config["optimization"]
		self.additional_compile = config["additional_compile"]
		self.additional_link = config["additional_link"]

		return True

	def read(self):
		for option in self.interface:
			if option in ["additional_compile", "additional_link"]:
				setattr(self, option, [])
				continue
			valid_values = self.interface[option]
			value = input(f"{option} ({', '.join(valid_values)}, default {getattr(self, option)}): ")
			while value not in valid_values:
				value = input(f"Invalid value for {option}. Please enter a valid value : ")
			setattr(self, option, value)

	def save(self, absolute_directory_path, config_name):
		file_path = os.path.join(absolute_directory_path, config_name + ".json")
		with open(file_path, 'w') as file:
			json.dump(vars(self), file, indent=2)
