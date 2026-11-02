"""Dependency-free dataset contracts shared by the app and training worker."""
import hashlib
import json

BASE = {
    'id': 'HuggingFaceTB/SmolLM2-135M-Instruct',
    'revision': '12fd25f77366fa6b3b4b768ec3050bf629380bac',
    'license': 'apache-2.0',
    'license_url': 'https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct/blob/main/LICENSE',
    'label': 'Small local starter · English · 135M',
}
CONFIG = {'epochs': 8, 'learning_rate': 0.001, 'rank': 8, 'alpha': 16,
          'max_tokens': 384, 'seed': 42, 'threads': 4,
          'target_modules': ['q_proj', 'v_proj'], 'max_new_tokens': 100}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def dataset_hash(snapshot):
    # Choosing a different inference engine does not change the teaching data.
    return digest(dict(snapshot, job={k: v for k, v in snapshot['job'].items() if k != 'model'}))


def instruction_messages(snapshot, request):
    job = snapshot['job']
    system = '\n'.join(filter(None, [job['goal'], job['instructions']]))
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': request}]


def freeze_dataset(snapshot):
    rows = []
    for example in snapshot['examples']:
        rows.append({'example_id': example['id'],
            'provenance': {'source_run_id': example.get('source_run_id'), 'created_at': example['created_at'],
                           'edited_at': example.get('edited_at')},
            'messages': instruction_messages(snapshot, example['input']) +
                        [{'role': 'assistant', 'content': example['output']}]})
    return dict(snapshot, training_rows=rows)


def encode_example(tokenizer, messages, max_tokens):
    """Mask every prompt token; reject long examples rather than silently trimming."""
    prompt = tokenizer.apply_chat_template(messages[:-1], tokenize=True, add_generation_prompt=True)
    full = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False)
    if len(full) > max_tokens:
        raise ValueError(f'An example uses {len(full)} tokens; this laptop training supports {max_tokens}. Shorten the job instructions or this example, then train again.')
    if full[:len(prompt)] != prompt or len(full) <= len(prompt):
        raise ValueError('The model template could not separate the request from its answer.')
    return {'input_ids': full, 'labels': [-100] * len(prompt) + full[len(prompt):]}
