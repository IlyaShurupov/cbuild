import CbuildProjects as cbiuld


class Project(cbiuld.BinaryProject):
	def __init__(self):
		super().__init__()
		self.name = "App"
		self.sources = ["private/Entry.cpp"]
		self.dependencies = ["./../Lib/Lib"]

	def compile(self, config, forced=False) -> (bool, bool):
		return super().compile(config, forced)

	def clear(self, config):
		super().clear(config)

	def recompile(self, config):
		super().recompile(config)
