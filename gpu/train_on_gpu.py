"""Explicitly approved portable Modal job. Importing this module never launches work."""
import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ.update(HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1', TOKENIZERS_PARALLELISM='false')
BASE_ID = 'Qwen/Qwen3-4B-Instruct-2507'
BASE_REVISION = 'cdbee75f17c01a7cc42f958dc650907174af0554'


def validate_request(payload, manifest, approve_spend, approve_upload, spend_limit_set):
    if not all(value is True for value in (approve_spend,approve_upload,spend_limit_set)):
        raise ValueError('Separate spending, business-data upload and provider spend-limit approvals are required. Preparing a package authorizes none of these.')
    digest = hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    if digest != manifest['request_hash'] or payload['base']['id'] != BASE_ID or payload['base']['revision'] != BASE_REVISION:
        raise ValueError('This request changed or uses an unsupported base. Prepare a fresh package in Own.')
    quote = payload['quote']
    if not 300 <= quote['timeout_seconds'] <= 1800 or quote['hard_invoice_cap'] is not False:
        raise ValueError('The planning quote is invalid. Prepare again in Own.')
    if quote.get('region') != 'us' or quote.get('region_multiplier') != 1.15:
        raise ValueError('This launcher requires the disclosed US execution region. Prepare a fresh package.')
    if not payload['training_rows'] or not payload['checks']:
        raise ValueError('Teaching examples and separate checks are required.')
    if any('output' in c or 'expected' in c for c in payload['checks']):
        raise ValueError('Expected check answers must remain local.')


def gpu_train(payload, progress_queue=None):
    from training_core import train
    def progress(**event):
        if progress_queue is not None:
            try:
                progress_queue.put(event, block=False)
            except Exception:
                pass
    return train(payload, progress=progress)


def build_app(timeout_seconds=1800, run_name='own-business-gpu-training'):
    import modal
    image = modal.Image.debian_slim(python_version='3.11').pip_install(
        'torch==2.9.1','transformers==4.57.6','peft==0.18.1','accelerate==1.12.0',
        'huggingface-hub==0.36.0','safetensors==0.7.0').add_local_file(
            Path(__file__).with_name('training_core.py'),'/root/training_core.py')
    app = modal.App(run_name)
    learn=app.function(image=image,gpu='L4',cpu=2,memory=16384,timeout=timeout_seconds,startup_timeout=300,region='us',
                       retries=0,max_containers=1,scaledown_window=2)(gpu_train)
    return app,learn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package',type=Path,default=Path('.'))
    parser.add_argument('--output',type=Path,default=Path('trained-gpu-model.zip'))
    parser.add_argument('--approve-spend',action='store_true')
    parser.add_argument('--approve-upload',action='store_true')
    parser.add_argument('--provider-spend-limit-set',action='store_true')
    args = parser.parse_args()
    payload = json.loads((args.package/'request.json').read_text(encoding='utf-8'))
    manifest = json.loads((args.package/'manifest.json').read_text(encoding='utf-8'))
    for name,expected in manifest['source_hashes'].items():
        if Path(name).name!=name or hashlib.sha256((args.package/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('A packaged source file changed. Extract the original package again.')
    validate_request(payload,manifest,args.approve_spend,args.approve_upload,args.provider_spend_limit_set)
    app,learn = build_app(payload['quote']['timeout_seconds'])
    with app.run():
        result = learn.remote(payload)
    args.output.write_bytes(result)
    print('Saved actual trained adapter. Review its comparison before deployment.')


if __name__ == '__main__':
    main()
