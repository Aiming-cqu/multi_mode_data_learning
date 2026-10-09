import os
import unittest

from data_juicer.core.data.ray_dataset import RayDataset
from data_juicer.ops.pipeline.vlm_inference_with_ray_vllm_pipeline import VLMRayVLLMEnginePipeline
from data_juicer.utils.mm_utils import SpecialTokens
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase
from data_juicer.utils.constant import RAY_JOB_ENV_VAR
from data_juicer.utils.unittest_utils import TEST_TAG


class VLMRayVLLMEnginePipelineTest(DataJuicerTestCaseBase):

    data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..',
                             'data')

    img1_path = os.path.join(data_path, 'cat.jpg')
    img2_path = os.path.join(data_path, 'img3.jpg')

    def setUp(self):
        os.environ[RAY_JOB_ENV_VAR] = '1'
        return super().setUp()

    def tearDown(self):
        os.environ[RAY_JOB_ENV_VAR] = '0'
        return super().tearDown()

    @TEST_TAG('ray')
    def test_default(self):
        import ray
        import ray.data

        ds_list = [
            {
            'query': f'{SpecialTokens.image} What does this picture describe?',
            'images': [self.img1_path]
            },
            {
            'query': f'{SpecialTokens.image} What does this picture describe?',
            'images': [self.img2_path]
            }
        ]
        ray_ds = ray.data.from_items(ds_list)
        ds = RayDataset(ray_ds)
        op = VLMRayVLLMEnginePipeline(
            api_or_hf_model='Qwen/Qwen2.5-VL-3B-Instruct',
            num_proc=1
            )
        ds = ds.process([op])
        res = ds.data.take_all()
        self.assertEqual(len(res), len(ds_list))
        for item in res:
            self.assertTrue(len(item['response']) > 0)


if __name__ == '__main__':
    unittest.main()
