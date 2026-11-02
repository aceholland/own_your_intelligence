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


if __name__=='__main__':
    unittest.main()
