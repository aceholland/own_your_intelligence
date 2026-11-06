"""Build a self-contained Colab notebook from a frozen training request."""
import json


INSTRUCTIONS = """# Train your business AI in Colab

1. In **Runtime → Change runtime type**, choose **T4 GPU** and save. Stay on the free plan. If a free GPU is unavailable, try again later.
2. Choose **Runtime → Run all**. Wait for **Training finished**. The first run also downloads the public base model.
3. Save **acewyn-colab-adapter.zip** and return to **Train it** in Acewyn AI to import it and compare answers. If the download does not start, run the last cell again or use Colab's **Files** panel.

This notebook contains your job instructions, teaching examples and check questions. Google Colab processes that data when you upload and run the notebook. Keep the notebook and result ZIP private.
"""

SETUP = """#@title Get the free GPU ready
import os
import subprocess
import sys
import torch

training_finished = False
if not torch.cuda.is_available():
    raise RuntimeError("Choose T4 GPU in Runtime → Change runtime type, then run all cells again.")

print("GPU:", torch.cuda.get_device_name(0), flush=True)
os.environ.update(HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1", TOKENIZERS_PARALLELISM="false")
subprocess.run(
    [sys.executable, "-m", "pip", "install", "-q",
     "transformers==4.57.6", "peft==0.18.1", "accelerate==1.12.0",
     "huggingface-hub==0.36.0", "safetensors==0.7.0"],
    check=True,
)
"""

TRAIN = """training_finished = False

def show_progress(phase, step=None, total_steps=None, **details):
    progress = f" ({step} of {total_steps} steps)" if step is not None else ""
    print(phase + progress, flush=True)

output = Path("acewyn-colab-adapter.zip")
output.write_bytes(train(payload, progress=show_progress))
training_finished = True
print("Training finished. Import acewyn-colab-adapter.zip in Acewyn AI to compare answers.")
"""

DOWNLOAD = """#@title Download the result ZIP
from google.colab import files

if not globals().get("training_finished"):
    raise RuntimeError("Finish training before downloading a result.")
files.download(str(output))
"""


def _code(source):
    return {
        'cell_type': 'code', 'source': source, 'metadata': {'cellView': 'form'},
        'execution_count': None, 'outputs': [],
    }


def render_notebook(payload, training_source):
    # Quote the entire JSON document as a single literal, including any user text.
    request_line = f"payload = json.loads({json.dumps(payload)!r})\n"
    notebook = {
        'nbformat': 4,
        'nbformat_minor': 4,
        'metadata': {
            'accelerator': 'GPU',
            'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
            'language_info': {'name': 'python'},
        },
        'cells': [
            {'cell_type': 'markdown', 'metadata': {}, 'source': INSTRUCTIONS},
            _code(SETUP),
            _code('#@title Load the training tools\n' + training_source),
            _code('#@title Train and compare answers\n' + request_line + TRAIN),
            _code(DOWNLOAD),
        ],
    }
    return json.dumps(notebook, ensure_ascii=False, indent=2).encode('utf-8')
