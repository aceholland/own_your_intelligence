"""Actual adapter optimization and comparison. Imported only inside the GPU worker."""
import gc
import hashlib
import io
import json
from pathlib import Path
import random
import tempfile
import zipfile


def encode(tokenizer, messages, limit):
    prompt = tokenizer.apply_chat_template(messages[:-1], tokenize=True, add_generation_prompt=True)
    full = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False)
    if len(full) > limit or full[:len(prompt)] != prompt or len(full) <= len(prompt):
        raise ValueError('An example is too long or its answer cannot be separated. Shorten instructions/examples and prepare again.')
    return {'input_ids':full, 'labels':[-100]*len(prompt)+full[len(prompt):]}


def messages_for(payload, request):
    job = payload['job']
    return [{'role':'system','content':'\n'.join(filter(None,[job['goal'],job['instructions']]))},
            {'role':'user','content':request}]


def generate(model, tokenizer, messages, device, limit):
    import torch
    inputs = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors='pt').to(device)
    if inputs.shape[1] > 4096:
        raise ValueError('This check request is too long.')
    model.eval()
    with torch.inference_mode():
        output = model.generate(inputs, attention_mask=torch.ones_like(inputs), do_sample=False,
            max_new_tokens=limit, pad_token_id=tokenizer.eos_token_id, use_cache=True)
    tokens = output[0,inputs.shape[1]:]
    answer = tokenizer.decode(tokens, skip_special_tokens=True).strip()
    if not answer or len(tokens) >= limit and tokens[-1].item() != tokenizer.eos_token_id:
        raise ValueError('No complete answer within the response limit.')
    return answer


def train(payload, base_dir=None, device='cuda', progress=None):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import LoraConfig, PeftModel, get_peft_model, TaskType
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('A supported CUDA GPU is required. No CPU fallback will be launched.')
    torch.manual_seed(payload['config']['seed'])
    if device == 'cpu':
        torch.set_num_threads(4)
    config, base = payload['config'], payload['base']
    def report(phase, **fields):
        if progress:
            progress(phase=phase, **fields)
    if base_dir is None:
        report('Downloading the public model')
        from huggingface_hub import snapshot_download
        base_dir = Path(snapshot_download(base['id'], revision=base['revision'], token=False,
            allow_patterns=['*.json','*.safetensors','*.txt','*.jinja','LICENSE','README.md']))
        for name, expected in base['weights_sha256'].items():
            with (base_dir/name).open('rb') as source:
                if hashlib.file_digest(source,'sha256').hexdigest() != expected:
                    raise ValueError('The public model download did not match the pinned base.')
    dtype = torch.float32
    if device == 'cuda':
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported(including_emulation=False) else torch.float16
    report('Loading the model')
    def load():
        return AutoModelForCausalLM.from_pretrained(base_dir, local_files_only=True, trust_remote_code=False,
            use_safetensors=True, dtype=dtype, low_cpu_mem_usage=True).to(device)
    tokenizer = AutoTokenizer.from_pretrained(base_dir, local_files_only=True, trust_remote_code=False)
    rows = [encode(tokenizer,r['messages'],config['max_tokens']) for r in payload['training_rows']]
    model = get_peft_model(load(), LoraConfig(task_type=TaskType.CAUSAL_LM, r=config['rank'],
        lora_alpha=config['alpha'], target_modules=config['target_modules'], lora_dropout=0., bias='none'))
    if device == 'cuda':
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
    model.config.use_cache = False
    parameters = {n:p for n,p in model.named_parameters() if p.requires_grad}
    original = {n:p.detach().cpu().clone() for n,p in parameters.items()}
    optimizer = torch.optim.AdamW(parameters.values(),lr=config['learning_rate'],weight_decay=0.)
    order = list(range(len(rows)))
    rng = random.Random(config['seed'])
    losses = []
    model.train()
    report('Learning your examples',step=0,total_steps=len(rows)*config['epochs'])
    for _ in range(config['epochs']):
        rng.shuffle(order)
        for index in order:
            row = rows[index]
            ids = torch.tensor([row['input_ids']],dtype=torch.long,device=device)
            labels = torch.tensor([row['labels']],dtype=torch.long,device=device)
            optimizer.zero_grad(set_to_none=True)
            loss = model(input_ids=ids,attention_mask=torch.ones_like(ids),labels=labels).loss
            if not torch.isfinite(loss):
                raise ValueError('Training became unstable; no successful adapter is available.')
            loss.backward()
            torch.nn.utils.clip_grad_norm_(parameters.values(),1.)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
            report('Learning your examples',step=len(losses),total_steps=len(rows)*config['epochs'],loss=losses[-1])
    changed = sum(torch.count_nonzero(p.detach().cpu()!=original[n]).item() for n,p in parameters.items())
    if not changed or any(not torch.isfinite(p).all() for p in parameters.values()):
        raise ValueError('No valid changed model weights were produced.')
    with tempfile.TemporaryDirectory() as scratch:
        report('Saving the trained model',step=len(losses),total_steps=len(rows)*config['epochs'])
        adapter = Path(scratch)/'adapter'
        model.peft_config['default'].base_model_name_or_path = base['id']
        model.peft_config['default'].revision = base['revision']
        model.save_pretrained(adapter,safe_serialization=True,save_embedding_layers=False)
        tokenizer.save_pretrained(adapter)
        del model, parameters, original, optimizer, loss, ids, labels
        gc.collect()
        if device == 'cuda':
            torch.cuda.empty_cache()
        model = PeftModel.from_pretrained(load(),adapter,local_files_only=True,is_trainable=False)
        model.config.use_cache = True
        results = []
        report('Comparing answers',step=len(losses),total_steps=len(rows)*config['epochs'])
        for check in payload['checks']:
            messages = messages_for(payload,check['input'])
            result = dict(check_id=check['id'],input=check['input'],before='',before_error=None,after='',error=None,review='pending')
            try:
                with model.disable_adapter():
                    result['before'] = generate(model,tokenizer,messages,device,config['max_new_tokens'])
            except ValueError as error:
                result['before_error'] = str(error)
            try:
                result['after'] = generate(model,tokenizer,messages,device,config['max_new_tokens'])
            except ValueError as error:
                result['error'] = str(error)
            results.append(result)
        hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in adapter.iterdir() if p.is_file()}
        summary = {'format':'own-gpu-result-v1','training_performed':True,'base_weights_included':False,
            'base':base,'config':config,'job':payload['job'],'dataset_hash':payload['dataset_hash'],'steps':len(losses),
            'request_hash':hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
            'first_loss':losses[0],'last_loss':losses[-1],'changed_parameters':changed,'artifacts':hashes,'results':results}
        output = io.BytesIO()
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json',json.dumps(summary,indent=2))
            for name in hashes:
                archive.write(adapter/name,'adapter/'+name)
        return output.getvalue()
