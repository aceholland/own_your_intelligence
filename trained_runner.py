"""Run an exported Own adapter independently; no Own app or paid service needed."""
import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ.update(HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1', TOKENIZERS_PARALLELISM='false')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, default=Path('.'))
    parser.add_argument('--question', required=True)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--base-dir', type=Path, help='Optional local folder for the exact pinned base')
    args = parser.parse_args()
    root = args.bundle.resolve()
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['artifacts'].items():
        if Path(name).name != name or hashlib.sha256((root / 'adapter' / name).read_bytes()).hexdigest() != expected:
            raise SystemExit('A model file changed. Extract the original export again.')
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    torch.set_num_threads(4)
    base = manifest['base']
    location = str(args.base_dir.resolve()) if args.base_dir else base['id']
    if args.base_dir:
        with (args.base_dir / 'model.safetensors').open('rb') as weights:
            if hashlib.file_digest(weights, 'sha256').hexdigest() != base['weights_sha256']:
                raise SystemExit('This local base is different from the model used for training. Use the exact base in manifest.json.')
    settings = {'revision': base['revision'], 'local_files_only': args.offline or bool(args.base_dir),
                'trust_remote_code': False, 'token': False}
    tokenizer = AutoTokenizer.from_pretrained(location, **settings)
    model = AutoModelForCausalLM.from_pretrained(location, **settings, use_safetensors=True,
                                               dtype=torch.float32, attn_implementation='eager')
    model = PeftModel.from_pretrained(model, root / 'adapter', local_files_only=True, is_trainable=False)
    dataset = json.loads((root / 'dataset.json').read_text(encoding='utf-8'))
    system = '\n'.join(filter(None, [dataset['job']['goal'], dataset['job']['instructions']]))
    messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': args.question}]
    inputs = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors='pt')
    if inputs.shape[1] > 2048:
        raise SystemExit('Shorten this request or its instructions to fit the small model.')
    model.eval()
    with torch.inference_mode():
        output = model.generate(inputs, attention_mask=torch.ones_like(inputs), do_sample=False,
            max_new_tokens=manifest['config']['max_new_tokens'], pad_token_id=tokenizer.eos_token_id)
    tokens = output[0, inputs.shape[1]:]
    result = tokenizer.decode(tokens, skip_special_tokens=True).strip()
    if not result or (len(tokens) >= manifest['config']['max_new_tokens'] and tokens[-1].item() != tokenizer.eos_token_id):
        raise SystemExit('The small model did not produce a complete answer. Try a shorter request or improve its training examples.')
    print(result)


if __name__ == '__main__':
    main()
