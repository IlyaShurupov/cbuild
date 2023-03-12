class Project(cbuild.{}):
	def __init__(self):
		super().__init__()
		self.name = "{}"
		self.dependencies = {}

	def compile(self, config):
		super().compile(config)

	def clear(self, config):
		super().clear(config)

	def recompile(self, config):
		super().recompile(config)
