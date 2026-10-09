#!/usr/bin/env -S pixi run -e vllm -- python

r"""VL Embedding Text Conditionality 实验。

验证 VL embedding 模型对 text prompt 的条件响应方向性：
  1. 确定性：相同输入 → 相同输出
  2. 敏感性：不同 text → 不同 embedding
  3. 方向性：图像信号 > text 信号 > 随机

Usage:
    pixi run -e vllm -- python experiments/vl-conditionality/test_vl_conditionality.py
"""

from __future__ import annotations

import os

import PIL.Image
import torch
import torch.nn.functional as F

from lib.algorithms.embedding_extractor import VLEmbeddingExtractor


def main() -> None:
    models_dir = f'{os.environ["MODELSCOPE_CACHE"]}/models'

    for model_id in [
        'Qwen/Qwen3-VL-Embedding-8B',
    ]:
        print(f'test {model_id=}')

        model_path = f'{models_dir}/{model_id}'
        extractor = VLEmbeddingExtractor(model_path, trust_remote_code=True)

        # Solid-color test images: red, green, blue
        color_rgb: dict[str, tuple[int, int, int]] = {
            'red': (255, 0, 0),
            'green': (0, 255, 0),
            'blue': (0, 0, 255),
        }
        color_images: dict[str, PIL.Image.Image] = {
            name: PIL.Image.new('RGB', (224, 224), rgb)
            for name, rgb in color_rgb.items()
        }
        all_images: list[PIL.Image.Image] = list(color_images.values())
        color_names: list[str] = list(color_images.keys())

        # Extract embeddings: 3 images × 3 text queries + 1 repeat for determinism
        e_red_nc: torch.Tensor = extractor.extract(all_images, text='red')
        e_green_nc: torch.Tensor = extractor.extract(all_images, text='green')
        e_blue_nc: torch.Tensor = extractor.extract(all_images, text='blue')
        e_red2_nc: torch.Tensor = extractor.extract(all_images, text='red')  # determinism

        # --- Test 1: Determinism ---
        sim_det_n: torch.Tensor = F.cosine_similarity(e_red_nc, e_red2_nc)
        print(f'determinism sim: {sim_det_n}')
        assert (sim_det_n > 0.99).all(), f'determinism failed: {sim_det_n}'

        # --- Test 2: Sensitivity ---
        sim_red_vs_blue_n: torch.Tensor = F.cosine_similarity(e_red_nc, e_blue_nc)
        sim_red_vs_green_n: torch.Tensor = F.cosine_similarity(e_red_nc, e_green_nc)
        print(f'sensitivity (red vs blue text): {sim_red_vs_blue_n}')
        print(f'sensitivity (red vs green text): {sim_red_vs_green_n}')
        assert (sim_red_vs_blue_n < 0.99).all(), f'sensitivity failed: {sim_red_vs_blue_n}'
        assert (sim_red_vs_green_n < 0.99).all(), f'sensitivity failed: {sim_red_vs_green_n}'

        # --- Test 3: Directionality ---
        all_e_nc: torch.Tensor = torch.cat([e_red_nc, e_green_nc, e_blue_nc])
        all_e_norm_nc: torch.Tensor = F.normalize(all_e_nc, p=2, dim=-1)
        sim_99: torch.Tensor = all_e_norm_nc @ all_e_norm_nc.T

        labels: list[str] = [
            f'{img}+{txt}'
            for txt in color_names
            for img in color_names
        ]
        print('Cosine similarity matrix (9×9):')
        for i, label in enumerate(labels):
            row = ', '.join(f'{sim_99[i, j].item():.3f}' for j in range(9))
            print(f'  {label:15s}: [{row}]')

        intra_image_sims: list[float] = []
        intra_text_sims: list[float] = []
        cross_sims: list[float] = []
        for i in range(9):
            img_i: str = labels[i].split('+')[0]
            txt_i: str = labels[i].split('+')[1]
            for j in range(i + 1, 9):
                img_j: str = labels[j].split('+')[0]
                txt_j: str = labels[j].split('+')[1]
                s: float = sim_99[i, j].item()
                same_img: bool = img_i == img_j
                same_txt: bool = txt_i == txt_j
                if same_img and not same_txt:
                    intra_image_sims.append(s)
                elif same_txt and not same_img:
                    intra_text_sims.append(s)
                elif not same_img and not same_txt:
                    cross_sims.append(s)

        avg_intra_image: float = sum(intra_image_sims) / len(intra_image_sims)
        avg_intra_text: float = sum(intra_text_sims) / len(intra_text_sims)
        avg_cross: float = sum(cross_sims) / len(cross_sims)
        print(f'avg intra-image sim: {avg_intra_image:.4f}  (same image, different text)')
        print(f'avg intra-text sim:  {avg_intra_text:.4f}  (same text, different image)')
        print(f'avg cross sim:       {avg_cross:.4f}  (different image AND text)')

        assert avg_intra_image > avg_intra_text, (
            f'image should dominate: intra_image={avg_intra_image:.4f} > intra_text={avg_intra_text:.4f}'
        )
        assert avg_intra_image > avg_cross, (
            f'shared image should be more similar than fully cross: '
            f'intra_image={avg_intra_image:.4f} > cross={avg_cross:.4f}'
        )

        print('PASSED')


if __name__ == '__main__':
    main()
