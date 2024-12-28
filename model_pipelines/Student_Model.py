from language_model_utils.utils import merge_tokenizer_vocabularies, ties_merge_models

class StudentModel:
  def __init__(self):
      self.tasks = {}

  def add_model(self, task, model_type, value):
      # Dynamically create nested models and tasks
      if task not in self.tasks:
          self.tasks[task] = StudentTask()  # Create a new Task if it doesn't exist
      self.tasks[task].add_values(model_type, value)

  def __getattr__(self, task):
      # This method handles dynamic access to models
      if task in self.tasks:
          return self.tasks[task]  # Return the task object if it exists
      raise AttributeError(f"'StudentModel' object has no attribute '{task}'")


class StudentTask:
  def __init__(self):
      self.tokenizer = None
      self.model = None

  def add_values(self, model_type, value):
      
      if model_type == "tokenizer" and self.tokenizer:
          # Merge tokenizers if already present
          self.tokenizer = merge_tokenizer_vocabularies(value, self.tokenizer)

      elif model_type == "tokenizer" and not self.tokenizer:
          # Set the tokenizer if not present
          self.tokenizer = value

      elif model_type == "model" and self.model:
          # Merge models if already present
          self.model = ties_merge_models(value, self.model)
      else:
          # Set the model if not present
          self.model = value

      if self.model and self.tokenizer:
          # Manually resize the model's embedding layer to the new vocabulary size
        new_vocab_size = len(self.tokenizer.get_vocab())  # Get the new vocabulary size
        self.model.resize_token_embeddings(new_vocab_size)