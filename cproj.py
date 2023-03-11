class Project(cbuild.{}):
	def __init__(self):
		super().__init__()
		self.name = "{}"
		self.dependencies = {}

	def compile(self, config):
		self.ProjectCompile(config)

	def clear(self, config):
		self.ProjectClear(config)

	def recompile(self, config):
		self.ProjectRecompile(config)
