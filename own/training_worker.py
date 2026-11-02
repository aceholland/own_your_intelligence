"""Actual CPU LoRA training and inference, isolated from the web process."""
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import threading
import time
import traceback

from .training_data import BASE, CONFIG, encode_example, instruction_messages
from .training_setup import write_json

os.environ.update(HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1', TOKENIZERS_PARALLELISM='false')


def download(root):
    from huggingface_hub import snapshot_download
    snapshot_download(BASE['id'], revision=BASE['revision'], local_dir=root / 'base', token=False,
        allow_patterns=['config.json', 'generation_config.json', 'model.safetensors', 'tokenizer.json',
                        'tokenizer_config.json', 'special_tokens_map.json', 'LICENSE', 'README.md'])
    load_model(root)  # Ready means the pinned weights/tokenizer can actually load.


def load_model(root):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(CONFIG['threads'])
    torch.manual_seed(CONFIG['seed'])
    with (root / 'base/model.safetensors').open('rb') as weights:
        if hashlib.file_digest(weights, 'sha256').hexdigest() != BASE['weights_sha256']:
            raise ValueError('The shared base model files changed. Set up local training again before using them.')
    tokenizer = AutoTokenizer.from_pretrained(root / 'base', local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(root / 'base', local_files_only=True,
        trust_remote_code=False, use_safetensors=True, dtype=torch.float32, attn_implementation='eager')
    return model, tokenizer


def answer(model, tokenizer, messages):
    import torch
    inputs = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors='pt')
    if inputs.shape[1] > 2048:
        raise ValueError('This request and its context are too long for the small trained model. Shorten the request or job instructions.')
    model.eval()
    with torch.inference_mode():
        result = model.generate(inputs, attention_mask=torch.ones_like(inputs), do_sample=False,
            max_new_tokens=CONFIG['max_new_tokens'], pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id, use_cache=True)
    tokens = result[0, inputs.shape[1]:]
    output = tokenizer.decode(tokens, skip_special_tokens=True).strip()
    if not output:
        raise ValueError('The small model returned no answer. Add clearer examples and train again.')
    if len(tokens) >= CONFIG['max_new_tokens'] and tokens[-1].item() != tokenizer.eos_token_id:
        raise ValueError('The small model reached its answer limit. Teach shorter answers and try again.')
    return output


def start_guard(folder):
    def guard():
        while True:
            time.sleep(3)
            try:
                if (folder / 'cancel').exists() or time.time() - (folder / 'heartbeat').stat().st_mtime > 30:
                    os._exit(2)
            except OSError:
                os._exit(2)
    threading.Thread(target=guard, daemon=True).start()


def compare_check(model, tokenizer, dataset, check):
    messages = instruction_messages(dataset, check['input'])
    row = dict(check_id=check['id'], input=check['input'], expected=check['output'],
               before='', before_error=None, after='', review='pending', error=None)
    try:
        with model.disable_adapter():
            row['before'] = answer(model, tokenizer, messages)
    except ValueError as error:
        row['before_error'] = str(error)
    try:
        row['after'] = answer(model, tokenizer, messages)
    except ValueError as error:
        row['error'] = str(error)
    return row


def train(root, folder):
    import torch
    from peft import LoraConfig, TaskType, get_peft_model, PeftModel
    start_guard(folder)
    task = json.loads((folder / 'task.json').read_text(encoding='utf-8'))
    dataset, config = task['dataset'], task['config']
    progress = {'status': 'running', 'phase': 'Loading the shared model', 'step': 0,
                'total_steps': len(dataset['training_rows']) * config['epochs'], 'results': []}
    def update(**changes):
        progress.update(changes)
        write_json(folder / 'progress.json', progress)
    try:
        update()
        model, tokenizer = load_model(root)
        rows = []
        for index, row in enumerate(dataset['training_rows']):
            try:
                rows.append(encode_example(tokenizer, row['messages'], config['max_tokens']))
            except ValueError as error:
                raise ValueError(f'Teaching example {index + 1}: {error}') from error
        # Validate held-out prompts too; none of their target tokens enter the optimizer.
        for check in dataset['checks']:
            ids = tokenizer.apply_chat_template(instruction_messages(dataset, check['input']), tokenize=True, add_generation_prompt=True)
            if len(ids) > 2048:
                raise ValueError('A check request is too long. Shorten it and train again.')
        model = get_peft_model(model, LoraConfig(task_type=TaskType.CAUSAL_LM, r=config['rank'],
            lora_alpha=config['alpha'], target_modules=config['target_modules'], lora_dropout=0.0, bias='none'))
        trainable = {name: parameter for name, parameter in model.named_parameters() if parameter.requires_grad}
        initial = {name: parameter.detach().clone() for name, parameter in trainable.items()}
        optimizer = torch.optim.AdamW(trainable.values(), lr=config['learning_rate'], weight_decay=0.0)
        model.config.use_cache = False
        generator = random.Random(config['seed'])
        losses = []
        started = time.monotonic()
        model.train()
        for epoch in range(config['epochs']):
            order = list(range(len(rows)))
            generator.shuffle(order)
            for index in order:
                if (folder / 'cancel').exists():
                    update(status='cancelled', phase='Training stopped')
                    return
                if time.monotonic() - started > 7200:
                    raise ValueError('Training reached the two-hour laptop limit. Use shorter examples or a GPU for this dataset.')
                row = rows[index]
                ids = torch.tensor([row['input_ids']], dtype=torch.long)
                labels = torch.tensor([row['labels']], dtype=torch.long)
                optimizer.zero_grad(set_to_none=True)
                loss = model(input_ids=ids, attention_mask=torch.ones_like(ids), labels=labels).loss
                if not torch.isfinite(loss):
                    raise ValueError('Training became unstable. Review the examples and try a new training.')
                loss.backward()
                torch.nn.utils.clip_grad_norm_(trainable.values(), 1.0)
                optimizer.step()
                losses.append(float(loss.detach()))
                update(phase='Learning from your examples', step=len(losses), loss=round(losses[-1], 5),
                       elapsed_seconds=round(time.monotonic() - started))
        changed = sum(torch.count_nonzero(p.detach() != initial[name]).item() for name, p in trainable.items())
        parameter_count = sum(p.numel() for p in trainable.values())
        if not changed or any(not torch.isfinite(p).all() for p in trainable.values()):
            raise ValueError('No valid model update was produced. Start a new training.')
        adapter = folder / 'adapter'
        model.peft_config['default'].base_model_name_or_path = BASE['id']
        model.peft_config['default'].revision = BASE['revision']
        model.save_pretrained(adapter, safe_serialization=True)
        tokenizer.save_pretrained(adapter)
        del optimizer, initial, trainable, model
        import gc
        gc.collect()
        update(status='comparing', phase='Reloading the saved training', changed_parameters=changed,
               trainable_parameters=parameter_count, first_loss=round(losses[0], 5), last_loss=round(losses[-1], 5))
        model, tokenizer = load_model(root)
        model = PeftModel.from_pretrained(model, adapter, local_files_only=True, is_trainable=False)
        results = []
        for index, check in enumerate(dataset['checks']):
            update(phase=f'Comparing check {index + 1} of {len(dataset["checks"])}')
            results.append(compare_check(model, tokenizer, dataset, check))
            update(results=results)
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in adapter.iterdir() if p.is_file()}
        update(status='complete', phase='Training finished · review the comparison', artifacts=hashes,
               elapsed_seconds=round(time.monotonic() - started))
    except Exception as error:
        update(status='failed', phase='Training could not finish', error=str(error) if isinstance(error, ValueError) else
               'The local training engine stopped. Check free memory and data/training logs, then try again.')
        traceback.print_exc()
        raise


def infer(root, request_file):
    task = json.loads(request_file.read_text(encoding='utf-8'))
    model, tokenizer = load_model(root)
    if task.get('adapter'):
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, task['adapter'], local_files_only=True, is_trainable=False)
    output = answer(model, tokenizer, task['messages'])
    write_json(request_file.with_suffix('.result.json'), {'output': output})


if __name__ == '__main__':
    operation, root = sys.argv[1], Path(sys.argv[2]).resolve()
    if operation == 'download':
        download(root)
    elif operation == 'train':
        train(root, Path(sys.argv[3]).resolve())
    elif operation == 'answer':
        infer(root, Path(sys.argv[3]).resolve())
    else:
        raise SystemExit('Unknown training operation')
