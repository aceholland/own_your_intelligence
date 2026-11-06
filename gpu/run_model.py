"""Independent CUDA runner for the future verified GPU result, not a hosted service."""
import argparse
import hashlib
import json
from pathlib import Path
import os
os.environ.update(HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',type=Path,required=True,help='Extracted result folder')
    parser.add_argument('--question',required=True)
    args=parser.parse_args()
    manifest=json.loads((args.model/'manifest.json').read_text())
    for name,expected in manifest['artifacts'].items():
        if Path(name).name!=name or hashlib.sha256((args.model/'adapter'/name).read_bytes()).hexdigest()!=expected:
            raise SystemExit('A saved adapter file changed. Extract the original result again.')
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from peft import PeftModel
    if not torch.cuda.is_available():
        raise SystemExit('This larger model runner requires a supported CUDA GPU.')
    base=manifest['base']
    dtype=torch.bfloat16 if torch.cuda.is_bf16_supported(including_emulation=False) else torch.float16
    tokenizer=AutoTokenizer.from_pretrained(base['id'],revision=base['revision'],token=False,trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(base['id'],revision=base['revision'],token=False,trust_remote_code=False,
        use_safetensors=True,dtype=dtype,low_cpu_mem_usage=True).to('cuda')
    model=PeftModel.from_pretrained(model,args.model/'adapter',local_files_only=True,is_trainable=False)
    from training_core import generate,messages_for
    print(generate(model,tokenizer,messages_for(manifest,args.question),'cuda',manifest['config']['max_new_tokens']))


if __name__=='__main__':
    main()
