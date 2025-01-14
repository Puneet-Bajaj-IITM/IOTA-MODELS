from language_model_utils.utils import merge_tokenizer_vocabularies, ties_merge_models

class GlobalModel:
  def __init__(self):
      self.tokenizer = None
      self.model = None

  def add_model(self, model_type, value):
      
      if model_type == "tokenizer" and self.tokenizer:
          # Merge tokenizers if already present
          self.tokenizer = merge_tokenizer_vocabularies(self.tokenizer, value)

      elif model_type == "tokenizer" and not self.tokenizer:
          # Set the tokenizer if not present
          self.tokenizer = value

      elif model_type == "model" and self.model:
          # Merge models if already present
          self.model = ties_merge_models(self.model, value)
      else:
          # Set the model if not present
          self.model = value

      if self.model and self.tokenizer:
          # Manually resize the model's embedding layer to the new vocabulary size
        new_vocab_size = len(self.tokenizer.get_vocab())  # Get the new vocabulary size
        self.model.resize_token_embeddings(new_vocab_size)