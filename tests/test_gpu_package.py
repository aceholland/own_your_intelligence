import importlib.util
import json
import unittest
from pathlib import Path
from own.gpu_setup import GPU_BASE, GPU_CONFIG, GpuSetup
from own.training_data import digest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('train_on_gpu',ROOT/'gpu/train_on_gpu.py')
launcher=importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class GpuPackageTests(unittest.TestCase):
    def payload(self):
        return {'base':GPU_BASE,'config':GPU_CONFIG,'quote':GpuSetup.quote(2.),
                'training_rows':[{'messages':[]}],'checks':[{'id':'check','input':'An unseen request'}]}

    def test_launch_requires_three_independent_approvals(self):
        payload=self.payload()
        manifest={'request_hash':digest(payload)}
        for approvals in ((False,True,True),(True,False,True),(True,True,False)):
            with self.assertRaises(ValueError):
                launcher.validate_request(payload,manifest,*approvals)
        launcher.validate_request(payload,manifest,True,True,True)

    def test_changed_request_or_check_target_cannot_enter_upload(self):
        payload=self.payload()
        manifest={'request_hash':digest(payload)}
        payload['job']='changed'
        with self.assertRaises(ValueError):
            launcher.validate_request(payload,manifest,True,True,True)
        payload=self.payload()
        payload['checks'][0]['expected']='Never upload this answer'
        with self.assertRaises(ValueError):
            launcher.validate_request(payload,{'request_hash':digest(payload)},True,True,True)

    def test_gpu_function_is_global_for_the_real_sdk(self):
        self.assertTrue(callable(getattr(launcher,'gpu_train',None)))
        self.assertNotIn('<locals>',launcher.gpu_train.__qualname__)

    def test_fixed_execution_region_is_part_of_the_quote(self):
        quote=GpuSetup.quote(2.)
        self.assertEqual(quote['region'],'us')
        self.assertEqual(quote['region_multiplier'],1.15)
        payload=self.payload()
        payload['quote']['region']='anywhere'
        with self.assertRaises(ValueError):
            launcher.validate_request(payload,{'request_hash':digest(payload)},True,True,True)

    def test_remote_progress_is_sent_without_expected_answers(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from queue import Queue
        queue=Queue()
        seen=[]
        def train(payload,progress=None):
            seen.append(payload)
            progress(phase='Learning your examples',step=1,total_steps=3,loss=1.5)
            return b'adapter'
        with patch.dict('sys.modules',{'training_core':SimpleNamespace(train=train)}):
            result=launcher.gpu_train({'teaching':'only'},queue)
        self.assertEqual(result,b'adapter')
        self.assertEqual(queue.get_nowait()['step'],1)
        self.assertEqual(seen,[{'teaching':'only'}])


if __name__=='__main__':
    unittest.main()
