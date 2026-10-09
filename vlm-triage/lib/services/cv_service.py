#!/bin/sh
""":"
exec pixi run -e opencv -- test "$0" "$@"
"""
#!/usr/bin/env -S pixi run -e opencv -- test

from __future__ import absolute_import, annotations

import os, threading, typing as tp
import cv2
import logfire
import numpy as np

from ..algorithms.cv_similarity import CvSimilarityBase


class CvService:
    r"""
    Service for computer vision-based image similarity computation.

    Supports multiple CV algorithms (SIFT, etc.) for computing image similarities.
    Similar to EmbeddingService but uses traditional CV methods instead of deep learning.
    """

    semaphore: tp.ClassVar = threading.Semaphore(value=int(os.getenv("TRIAGE_CV_API_CONCURRENCY", 4)))

    @classmethod
    @logfire.instrument(extract_args=False)
    def decode_image(cls, image_data: bytes) -> np.ndarray:
        r"""
        Decode image bytes to OpenCV BGR format.

        Args:
            image_data: Raw image bytes (PNG, JPEG, etc.).

        Returns:
            Decoded image in OpenCV BGR format.

        Raises:
            AssertionError: If image decoding fails.
        """
        ret = cv2.imdecode(np.frombuffer(image_data, dtype=np.uint8), cv2.IMREAD_COLOR)
        assert ret is not None
        return ret

    @logfire.instrument(extract_args=["algorithm_names"])
    def compute_images_similarity(
        self,
        images_data: tp.Sequence[bytes],
        algorithm_names: tp.Sequence[str] = ("SIFT",),
    ) -> np.ndarray:
        r"""
        Compute image similarities using specified CV algorithms.

        Args:
            images_data: Sequence of image bytes.
            algorithm_names: Sequence of algorithm names to use (e.g., "SIFT").

        Returns:
            CvSimilarityResult containing similarity scores.
            Shape: (num_images, num_algorithms, num_metrics, 2)
            - [:, :, :, 0]: similarities with base image (index 0)
            - [:, :, :, 1]: similarities with feature image (index -1)
        """

        with self.semaphore:
            # Decode all images
            images = [self.decode_image(img_data) for img_data in images_data]

            # Compute similarities for each algorithm
            # Each algorithm produces scores of shape (num_images, 2)
            scores_list = []
            for algo_name in algorithm_names:
                op = CvSimilarityBase.Registry[algo_name]()
                # Compute similarities: base vs all, feature vs all
                scores_n2 = op.compute(images)  # shape: (num_images, 2)
                scores_list.append(scores_n2)

        # Stack scores: (num_algorithms, num_images, 2)
        scores_an2 = np.stack(scores_list, axis=0)

        # Transpose to (num_images, num_algorithms, 2)
        scores_na2 = scores_an2.transpose(1, 0, 2)

        # Add metric dimension: (num_images, num_algorithms, num_metrics, 2)
        scores_nam2 = scores_na2[:, :, np.newaxis, :]

        return scores_nam2


def test_cv_service():
    r"""
    测试 CvService 与简单彩色图像。

    创建带有渐变模式和几何形状的测试图像，
    然后验证相似度计算产生预期结果。

    验证:
        - 服务成功创建
        - 相似度分数形状正确
        - 基准与基准、特征与特征的相似度约为 1

    Parameters:
        -
    """
    try:
        service = CvService()

        # Create test images using OpenCV with some texture for SIFT to detect
        images_data = []
        for i, color in enumerate(
            ((255, 0, 0), (255, 255, 0), (0, 255, 0))
        ):  # red, yellow, green in BGR
            # Create image with gradient pattern for SIFT features
            img = np.zeros((224, 224, 3), dtype=np.uint8)
            # Add gradient pattern
            for j in range(224):
                intensity = int(255 * j / 224)
                img[j, :, :] = [min(c + intensity // 4, 255) for c in color]
            # Add some corners/edges for SIFT detection
            cv2.rectangle(img, (50, 50), (100, 100), (255, 255, 255), -1)
            cv2.circle(img, (150, 150), 30, (0, 0, 0), -1)

            # Encode to PNG bytes
            success, buf = cv2.imencode(".png", img)
            assert success, "Failed to encode image"
            images_data.append(buf.tobytes())

        scores_nam2 = service.compute_images_similarity(
            images_data,
            algorithm_names=["SIFT"],
        )

        assert scores_nam2.shape == (3, 1, 1, 2), scores_nam2.shape

        # Base-to-base and feature-to-feature should be ~1 (perfect similarity)
        # todo: fix when extra metrics are added
        b2b_score = scores_nam2[0, 0, 0, 0]
        assert np.isclose(b2b_score, 1.0, atol=0.1), f"Base-to-base score: {b2b_score}"

        f2f_score = scores_nam2[-1, 0, 0, 1]
        assert np.isclose(f2f_score, 1.0, atol=0.1), f"Feature-to-feature score: {f2f_score}"

        print("CvService test passed!")

    finally:
        if __name__ == "__main__":
            globals().update(locals())


if __name__ == "__main__":
    from conflog import configure_logging, configure_auto_tracing

    configure_logging(env="test")
    configure_auto_tracing(env="test")

    test_cv_service()
