from pathlib import Path
import torch

def ties_merge_models(model_a, model_b, threshold=1e-5):
  """
  Perform TIES merging on two Hugging Face models.

  Args:
      model_a: Model A (e.g., BioGPT).
      model_b: Model B (e.g., BioBERT).
      threshold: Threshold to consider marginal parameter changes.
  Returns:
      A merged Hugging Face model.
  """
  state_dict_a = model_a.state_dict()
  state_dict_b = model_b.state_dict()
  merged_state_dict = {}

  for key in state_dict_a.keys():
      if key in state_dict_b:
          param_a = state_dict_a[key]
          param_b = state_dict_b[key]

          # Reset marginal changes
          if torch.abs(param_a - param_b).mean() < threshold:
              merged_state_dict[key] = param_a
              continue

          # Resolve sign conflicts
          sign_mask = torch.sign(param_a) == torch.sign(param_b)
          resolved_param = torch.where(sign_mask, (param_a + param_b) / 2, param_a.abs().max(param_b.abs()))

          # Selective merging based on resolved sign
          merged_state_dict[key] = resolved_param
      else:
          merged_state_dict[key] = state_dict_a[key]  # Default to model A's parameters

  # Load the merged state dict into model A's architecture
  model_a.load_state_dict(merged_state_dict)

  return model_a

def merge_tokenizer_vocabularies(tokenizer_a, tokenizer_b):
  """
  Merge the vocabularies of two tokenizers.

  Args:
      tokenizer_a: first tokenizer
      tokenizer_b: second tokenizer
  """

  # Extract vocabularies
  vocab_a = set(tokenizer_a.get_vocab().keys())
  vocab_b = set(tokenizer_b.get_vocab().keys())

  # Merge vocabularies
  merged_vocab = vocab_a.union(vocab_b)

  # Update tokenizer A's vocabulary (base tokenizer)
  current_vocab = tokenizer_a.get_vocab()
  added_tokens = [token for token in merged_vocab if token not in current_vocab]
  tokenizer_a.add_tokens(added_tokens)

  return tokenizer_a


def save_merged_tokenizer(tokenizer, save_dir):
    """Save Hugging Face tokenizer to a directory."""
    # Save the updated tokenizer
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    tokenizer.save_pretrained(save_dir)
    print(f"Merged tokenizer saved at {save_dir}")

def save_huggingface_model(model, save_dir):
    """Save Hugging Face model to a directory."""
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(save_dir)
    print(f"Merged model saved at {save_dir}")