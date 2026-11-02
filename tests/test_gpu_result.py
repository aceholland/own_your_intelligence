import copy
import hashlib
import io
import json
import math
import struct
import unittest
import zipfile
from own.store import Problem
from own.gpu_setup import GPU_BASE,GPU_CONFIG
from own.training_data import digest
from own.gpu_result import validate_result


def fixture(manifest_changes=None,extra=None,tensor_value=.125):
    payload={'base':GPU_BASE,'config':GPU_CONFIG,'dataset_hash':'frozen-dataset','job':{'goal':'Reply','instructions':'Be concise'},
             'training_rows':[{'messages':[]} for _ in range(3)],'checks':[{'id':'check1','input':'New request'}]}
    config={'peft_type':'LORA','task_type':'CAUSAL_LM','base_model_name_or_path':GPU_BASE['id'],'revision':GPU_BASE['revision'],
            'r':GPU_CONFIG['rank'],'lora_alpha':GPU_CONFIG['alpha'],'target_modules':GPU_CONFIG['target_modules'],'bias':'none'}
    header={};offset=0
    for module in ('q_proj','v_proj'):
        for letter,shape in (('A',[8,1]),('B',[1,8])):
            header[f'base_model.model.model.layers.0.self_attn.{module}.lora_{letter}.weight']={'dtype':'F32','shape':shape,'data_offsets':[offset,offset+32]};offset+=32
    encoded=json.dumps(header).encode()
    encoded+=b' '*((-len(encoded))%8)
    weights=struct.pack('<Q',len(encoded))+encoded+struct.pack('<32f',*[tensor_value]*32)
    files={'adapter_model.safetensors':weights,'adapter_config.json':json.dumps(config).encode()}
    manifest={'format':'own-gpu-result-v1','training_performed':True,'base_weights_included':False,'base':GPU_BASE,'config':GPU_CONFIG,
        'job':payload['job'],'dataset_hash':payload['dataset_hash'],'request_hash':digest(payload),'steps':9,'changed_parameters':16,
        'first_loss':2.,'last_loss':1.,'artifacts':{n:hashlib.sha256(v).hexdigest() for n,v in files.items()},
        'results':[dict(check_id='check1',input='New request',before='Before',before_error=None,after='After',error=None,review='pass')]}
    if manifest_changes:manifest.update(manifest_changes)
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json',json.dumps(manifest))
        for name,value in files.items():archive.writestr('adapter/'+name,value)
        if extra:
            for name,value in extra.items():archive.writestr(name,value)
    return output.getvalue(),payload


class GpuResultTests(unittest.TestCase):
    def test_real_weight_format_and_exact_snapshot_are_required(self):
        data,payload=fixture()
        manifest,files=validate_result(data,payload)
        self.assertGreater(manifest['changed_parameters'],0)
        self.assertIn('adapter_model.safetensors',files)
        self.assertEqual(manifest['results'][0]['review'],'pending')

    def test_fake_success_wrong_identity_and_check_mismatch_are_rejected(self):
        for change in ({'training_performed':False},{'changed_parameters':0},{'steps':8},{'dataset_hash':'different'},
                       {'request_hash':'wrong'},{'base':dict(GPU_BASE,revision='wrong')},{'results':[]},
                       {'last_loss':float('nan')}):
            data,payload=fixture(change)
            with self.assertRaises(Problem):validate_result(data,payload)

    def test_traversal_executable_pickle_and_unlisted_files_are_rejected(self):
        for name in ('../escape.txt','adapter/evil.py','adapter/model.bin','unexpected.json'):
            data,payload=fixture(extra={name:b'untrusted'})
            with self.assertRaises(Problem):validate_result(data,payload)

    def test_nonfinite_or_all_zero_model_weights_are_rejected(self):
        for value in (float('nan'),float('inf'),0.):
            data,payload=fixture(tensor_value=value)
            with self.assertRaises(Problem):validate_result(data,payload)

    def test_size_limits_reject_before_parsing(self):
        with self.assertRaises(Problem):validate_result(b'x'*(65*1024*1024),{})


if __name__=='__main__':unittest.main()
