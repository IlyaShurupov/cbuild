class Project(cbuild.LibraryProject):
	def __init__(self):
		super().__init__()
		self.name = "Lib"

	def compile(self, config, forced=False) -> (bool, bool):
		return super().compile(config, forced)

	def clear(self, config):
		super().clear(config)

	def recompile(self, config):
		super().recompile(config)
