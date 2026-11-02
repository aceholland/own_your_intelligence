"""Bounded, dependency-free validation of a remote adapter. Never execute archive code."""
import hashlib
import io
import json
import math
import re
import stat
import struct
import zipfile
import zlib

from .store import Problem
from .training_data import digest
from .model_topology import lora_shapes

MAX_BYTES = 64 * 1024 * 1024
ARTIFACTS = frozenset(('adapter_config.json', 'adapter_model.safetensors', 'tokenizer.json',
    'tokenizer_config.json', 'special_tokens_map.json', 'chat_template.jinja', 'vocab.json',
    'merges.txt', 'README.md'))


def _json(data):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Repeated JSON key')
            value[key] = item
        return value
    return json.loads(data, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def _weights(data, config, base):
    """Check safetensors layout, LoRA pairs and finite numeric values without torch/pickle."""
    if len(data) < 9:
        raise ValueError('Missing weights')
    size = struct.unpack_from('<Q', data)[0]
    if not 2 <= size <= min(4 * 1024 * 1024, len(data) - 8):
        raise ValueError('Invalid weight header')
    header = _json(data[8:8 + size])
    if not isinstance(header, dict):
        raise ValueError('Invalid weight header structure')
    expected_shapes = lora_shapes(base, config['rank'])
    if set(header) - {'__metadata__'} != expected_shapes.keys():
        raise ValueError('Missing or unexpected model layers/modules')
    values = memoryview(data)[8 + size:]
    offset = count = 0
    nonzero = False
    pairs = {}
    pattern = re.compile(r'base_model\.model\.model\.layers\.([0-9]+)\.self_attn\.(q_proj|v_proj)\.lora_([AB])\.weight')
    tensors = []
    for name, item in header.items():
        if name == '__metadata__':
            if not isinstance(item, dict) or any(not isinstance(v, str) for v in item.values()):
                raise ValueError('Invalid tensor metadata')
            continue
        match = pattern.fullmatch(name)
        if not match or not isinstance(item, dict):
            raise ValueError('Unexpected tensor')
        shape, dtype, bounds = item['shape'], item['dtype'], item['data_offsets']
        if not isinstance(shape, list) or len(shape) != 2 or any(type(n) is not int or not 0 < n <= 65536 for n in shape):
            raise ValueError('Invalid tensor shape')
        if shape != expected_shapes[name]:
            raise ValueError('Adapter dimensions do not match the pinned model')
        if shape[0 if match[3] == 'A' else 1] != config['rank'] or dtype not in ('F32', 'F16', 'BF16'):
            raise ValueError('Unexpected adapter dimensions or precision')
        width = 4 if dtype == 'F32' else 2
        if not isinstance(bounds, list) or len(bounds) != 2 or any(type(n) is not int for n in bounds):
            raise ValueError('Invalid tensor offsets')
        if bounds[1] - bounds[0] != math.prod(shape) * width:
            raise ValueError('Wrong tensor size')
        pair = pairs.setdefault((match[1], match[2]), set())
        pair.add(match[3])
        tensors.append((bounds[0], bounds[1], dtype, math.prod(shape)))
    if not tensors or any(pair != {'A', 'B'} for pair in pairs.values()):
        raise ValueError('Incomplete adapter pairs')
    for start, end, dtype, elements in sorted(tensors):
        if start != offset or end > len(values):
            raise ValueError('Overlapping or missing tensor data')
        chunk = values[start:end]
        if dtype == 'BF16':
            for (bits,) in struct.iter_unpack('<H', chunk):
                if bits & 0x7f80 == 0x7f80:
                    raise ValueError('Nonfinite weights')
                nonzero = nonzero or bool(bits & 0x7fff)
        else:
            for (value,) in struct.iter_unpack('<f' if dtype == 'F32' else '<e', chunk):
                if not math.isfinite(value):
                    raise ValueError('Nonfinite weights')
                nonzero = nonzero or value != 0
        offset, count = end, count + elements
    if offset != len(values) or not nonzero:
        raise ValueError('Empty or trailing tensor data')
    return count


def validate_result(data, payload):
    """Return sanitized manifest and filename->bytes, or one safe user-facing error."""
    try:
        if not isinstance(data, bytes) or not 0 < len(data) <= MAX_BYTES:
            raise ValueError('Result exceeds size limit')
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            allowed = {'manifest.json'} | {'adapter/' + name for name in ARTIFACTS}
            if len(names) != len(set(names)) or not set(names) <= allowed or 'manifest.json' not in names:
                raise ValueError('Unexpected archive entries')
            if sum(item.file_size for item in infos) > MAX_BYTES or any(item.flag_bits & 1 or stat.S_ISLNK(item.external_attr >> 16) for item in infos):
                raise ValueError('Unsupported archive')
            if archive.getinfo('manifest.json').file_size > 2 * 1024 * 1024:
                raise ValueError('Oversized manifest')
            manifest = _json(archive.read('manifest.json'))
            files = {name[8:]: archive.read(name) for name in names if name.startswith('adapter/')}
        hashes = {name: hashlib.sha256(value).hexdigest() for name, value in files.items()}
        if not {'adapter_config.json', 'adapter_model.safetensors'} <= files.keys() or hashes != manifest['artifacts']:
            raise ValueError('Adapter files do not match')
        if manifest['format'] != 'own-gpu-result-v1' or manifest['training_performed'] is not True or manifest['base_weights_included'] is not False:
            raise ValueError('No actual training result')
        if any(manifest[key] != payload[key] for key in ('base', 'config', 'job', 'dataset_hash')) or manifest['request_hash'] != digest(payload):
            raise ValueError('Different frozen request')
        steps, changed = manifest['steps'], manifest['changed_parameters']
        if type(steps) is not int or steps != len(payload['training_rows']) * payload['config']['epochs'] or type(changed) is not int or changed <= 0:
            raise ValueError('Training did not finish')
        if any(type(manifest[key]) not in (int, float) or not math.isfinite(manifest[key]) or manifest[key] < 0 for key in ('first_loss', 'last_loss')):
            raise ValueError('Invalid training measurements')
        adapter = _json(files['adapter_config.json'])
        if not isinstance(adapter, dict):
            raise ValueError('Invalid adapter configuration structure')
        expected = {'peft_type': 'LORA', 'task_type': 'CAUSAL_LM', 'base_model_name_or_path': payload['base']['id'],
            'revision': payload['base']['revision'], 'r': payload['config']['rank'], 'lora_alpha': payload['config']['alpha'], 'bias': 'none'}
        if any(adapter.get(key) != value for key, value in expected.items()) or set(adapter['target_modules']) != set(payload['config']['target_modules']):
            raise ValueError('Different adapter configuration')
        if any(adapter.get(key) for key in ('modules_to_save', 'rank_pattern', 'alpha_pattern', 'use_dora', 'use_rslora')):
            raise ValueError('Unsupported adapter configuration')
        if changed > _weights(files['adapter_model.safetensors'], payload['config'], payload['base']):
            raise ValueError('Invalid changed parameter count')
        checks = {c['id']: c['input'] for c in payload['checks']}
        results = manifest['results']
        if not isinstance(results, list) or len(results) != len(checks) or {r['check_id'] for r in results} != checks.keys():
            raise ValueError('Missing or duplicated comparisons')
        sanitized = []
        for row in results:
            if row['input'] != checks[row['check_id']]:
                raise ValueError('Different check request')
            clean = {key: row.get(key) for key in ('check_id', 'input', 'before', 'before_error', 'after', 'error')}
            if any(not isinstance(clean[key], str) or len(clean[key]) > 60000 for key in ('before', 'after')):
                raise ValueError('Invalid answer')
            if any(clean[key] is not None and (not isinstance(clean[key], str) or not 0 < len(clean[key]) <= 4000) for key in ('before_error', 'error')):
                raise ValueError('Invalid comparison error')
            if not (clean['before'] or clean['before_error']) or not (clean['after'] or clean['error']):
                raise ValueError('Unfinished comparison')
            sanitized.append(dict(clean, review='pending'))
        clean_manifest = {key: manifest[key] for key in ('format', 'training_performed', 'base_weights_included', 'base',
            'config', 'job', 'dataset_hash', 'request_hash', 'steps', 'changed_parameters', 'first_loss', 'last_loss', 'artifacts')}
        return dict(clean_manifest, results=sanitized), files
    except (ValueError, TypeError, KeyError, IndexError, UnicodeError, OverflowError, struct.error, zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, EOFError, zlib.error) as error:
        raise Problem('The GPU result could not be verified. No model was imported. Keep the job details and try again after checking the provider run.', 422) from error
