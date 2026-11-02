import tempfile
import unittest
from pathlib import Path
from own.store import Store, Problem
from own.gpu_setup import GpuSetup
from own.gpu_jobs import GpuJobRepository


class GpuJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name)/'db.sqlite3')
        self.setup=GpuSetup(self.store,self.tmp.name)
        self.repo=GpuJobRepository(self.store,self.setup)
        self.ws=self.store.create_workspace('GPU fictional')['id']
        self.job=self.store.create_job(self.ws,'Replies','Answer briefly')['id']
        for n in range(3):self.store.add_example(self.ws,self.job,'teach',f'Question {n}',f'Answer {n}')
        self.check=self.store.add_example(self.ws,self.job,'check','New question','LOCAL_TARGET')

    def tearDown(self):
        self.setup.close();self.store.close();self.tmp.cleanup()

    def begin(self,**changes):
        args=dict(dataset_hash=self.setup.plan(self.ws,self.job)['dataset_hash'],upload=True,free_only=True,zero_limit=True,credits=True)
        args.update(changes)
        return self.repo.begin(self.ws,self.job,**args)

    def test_every_confirmation_is_required_and_strings_do_not_count(self):
        for key in ('upload','free_only','zero_limit','credits'):
            for value in (False,'true',None):
                with self.assertRaises(Problem):self.begin(**{key:value})
        self.assertEqual(self.repo.list(self.ws,self.job),[])
        self.assertEqual(self.setup.packages(self.ws,self.job),[])

    def test_stale_confirmation_cannot_start_a_job(self):
        old=self.setup.plan(self.ws,self.job)['dataset_hash']
        self.store.add_source(self.ws,'Changed','New facts')
        with self.assertRaises(Problem):self.begin(dataset_hash=old)

    def test_job_keeps_frozen_data_and_cannot_overlap_an_active_run(self):
        run=self.begin()
        self.assertEqual(run['status'],'queued')
        self.assertEqual(run['approval']['out_of_pocket_usd'],0)
        self.assertEqual(run['approval']['billing_source'],'owner-confirmed')
        self.assertNotIn('LOCAL_TARGET',str(run['payload']))
        self.store.add_example(self.ws,self.job,'teach','Later input','Later answer')
        self.assertNotIn('Later answer',str(self.repo.get(self.ws,self.job,run['id'])))
        with self.assertRaises(Problem):self.begin()

    def test_scope_and_failed_candidate_review_are_enforced(self):
        run=self.begin()
        other=self.store.create_workspace('Other')['id']
        with self.assertRaises(Problem):self.repo.get(other,self.job,run['id'])
        with self.assertRaises(Problem):self.repo.review(self.ws,self.job,run['id'],self.check['id'],'pass')
        self.repo.update(self.ws,self.job,run['id'],status='complete',results=[dict(check_id=self.check['id'],after='',error='Model failed',review='pending')])
        with self.assertRaises(Problem):self.repo.review(self.ws,self.job,run['id'],self.check['id'],'pass')

    def test_completed_comparison_is_reviewed_without_changing_local_live_model(self):
        run=self.begin()
        self.repo.update(self.ws,self.job,run['id'],status='complete',results=[dict(check_id=self.check['id'],after='A real answer',error=None,review='pending')])
        self.repo.review(self.ws,self.job,run['id'],self.check['id'],'pass')
        self.assertEqual(self.repo.get(self.ws,self.job,run['id'])['results'][0]['review'],'pass')
        self.assertEqual(self.store.job(self.ws,self.job)['model'],'')


if __name__=='__main__':unittest.main()
