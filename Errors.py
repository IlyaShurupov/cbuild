
global_verbose_level = 3


class CBuildError(Exception):
	def __init__(self, message):
		super().__init__(message)


def log(message, verbose_level: int = 0):
	if verbose_level < global_verbose_level:
		print(message)


def warn(message):
	print(f"\033[33mWARNING {message}\033[0m")


def err(message):
	print(f"\033[31mERROR {message}\033[0m")
