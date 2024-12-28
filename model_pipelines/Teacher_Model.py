class TeacherModel:
  def __init__(self):
      self.tasks = {}

  def add_model(self, task, model_name, model_type, value):
      # Dynamically create nested models and tasks
      if task not in self.tasks:
          self.tasks[task] = TeacherTask()  # Create a new Task if it doesn't exist
      self.tasks[task].add_model(model_name, model_type, value)

  def __getattr__(self, task):
      # This method handles dynamic access to models
      if task in self.tasks:
          return self.tasks[task]  # Return the task object if it exists
      raise AttributeError(f"'TeacherModel' object has no attribute '{task}'")


class TeacherTask:
  def __init__(self):
      self.models = {}

  def add_model(self, model_name, model_type, value):
      # Add a model to the task, keyed by model_name
      if model_name not in self.models:
          self.models[model_name] = TeacherTaskModel()
      self.models[model_name].add_values(model_type, value)

  def __getattr__(self, model_name):
      # Allow dynamic access to models by model_name
      if model_name in self.models:
          return self.models[model_name]
      raise AttributeError(f"'Task' object has no attribute '{model_name}'")


class TeacherTaskModel:
  def __init__(self):
      self.tokenizer = None
      self.model = None

  def add_values(self, model_type, value):
      if model_type == "tokenizer":
          self.tokenizer = value
      elif model_type == "model":
          self.model = value
      else:
          raise ValueError(f"Invalid type: {model_type}")