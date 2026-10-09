#!/usr/bin/env -S pixi run -e opencv -- test

r"""
基于计算机视觉的图像相似度计算模块。

该模块提供了基于 SIFT 特征匹配的图像相似度计算算法，支持特征提取、
几何一致性验证和相似度评分功能。

主要组件:
    - SiftScoreResult: SIFT 相似度计算结果的数据类
    - CvSimilarityBase: CV 相似度算法的抽象基类
    - SiftSimilarity: 基于 SIFT 特征的图像相似度计算类

算法流程:
    1. 提取图像的 SIFT 特征（支持多通道独立处理）
    2. 使用 BFMatcher 进行特征匹配
    3. 通过交叉检查筛选优质匹配
    4. 使用基础矩阵估计进行几何一致性验证
    5. 综合匹配率、内点率和极线误差计算相似度分数

Attributes:
    -
"""

from __future__ import absolute_import, annotations

import abc, dataclasses as dc, typing as tp

import cv2
import numpy as np


@dc.dataclass(frozen=True, slots=True)
class SiftScoreResult:
    r"""
    SIFT 相似度计算结果。

    Attributes:
        score: 综合相似度分数，越低表示越相似
        match_ratio: 匹配点比例
        inlier_ratio: 几何内点比例
        epipolar_error: 极线误差
        num_matches: 匹配点数量
        num_inliers: 内点数量
    """

    score: float  # Lower score indicates higher similarity
    match_ratio: float
    inlier_ratio: float
    epipolar_error: float
    num_matches: int
    num_inliers: int


class CvSimilarityBase(abc.ABC):
    r"""
    CV 图像相似度算法的抽象基类。

    提供算法注册机制和抽象计算接口，子类需要实现 compute 方法。

    Attributes:
        Registry: 算法注册表，存储所有已注册的相似度算法类
    """

    Registry: tp.ClassVar[dict[str, tp.Type[CvSimilarityBase]]] = {}

    def __init_subclass__(cls, registry_name: tp.Optional[str] = None, **kwargs: tp.Any):
        super().__init_subclass__(**kwargs)
        name = registry_name or cls.__name__
        cls.Registry[name] = cls

    @abc.abstractmethod
    def compute(self, images: tp.Sequence[np.ndarray]) -> np.ndarray:
        r"""
        计算图像间的相似度分数。

        Args:
            images: 图像序列，OpenCV BGR 格式

        Returns:
            相似度分数数组，形状为 (num_images, 2)
            - [:, 0]: 与基准图像（索引 0）的相似度
            - [:, 1]: 与特征图像（索引 -1）的相似度
            值域为 [0, 1]，1 表示完全相同
        """

        raise NotImplementedError


class SiftSimilarity(CvSimilarityBase, registry_name="SIFT"):
    r"""
    基于 SIFT 特征的图像相似度计算类。

    使用 SIFT 特征匹配和几何验证计算图像相似度。
    内部分数越低表示越相似，输出相似度归一化到 [0, 1]，1 表示完全相同。

    Attributes:
        w1: 匹配率权重，默认 0.3
        w2: 内点率权重，默认 0.4
        w3: 极线误差权重，默认 0.3
    """

    def __init__(
        self,
        w1: float = 0.3,  # Weight for match ratio
        w2: float = 0.4,  # Weight for inlier ratio
        w3: float = 0.3,  # Weight for epipolar error
    ):
        self.w1 = w1
        self.w2 = w2
        self.w3 = w3

    def extract_features(self, img: np.ndarray) -> tuple[list[tp.Any], np.ndarray]:
        r"""
        从图像中提取 SIFT 特征，保留颜色信息。

        独立处理每个颜色通道以保留色度梯度信息。
        使用确定性提取和排序输出以获得稳定结果。

        Args:
            img: 输入图像，OpenCV BGR 格式

        Returns:
            包含关键点和描述符的元组
            - 关键点列表，每个元素为 ``(keypoint, channel_idx)`` 元组
            - 描述符数组，形状为 ``(N, 128)``

        Examples:
            >>> import numpy as np
            >>> sift = SiftSimilarity()
            >>> img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            >>> kp, des = sift.extract_features(img)
            >>> isinstance(kp, list)
            True
            >>> isinstance(des, np.ndarray)
            True
        """

        sift = cv2.SIFT_create(  # type: ignore[attr-defined]
            nfeatures=0,  # Keep all features
            nOctaveLayers=3,
            contrastThreshold=0.04,
            edgeThreshold=10,
            sigma=1.6,
        )

        # Process each channel (B, G, R) independently
        all_keypoints = []
        all_descriptors = []

        num_channels = img.shape[2] if len(img.shape) == 3 else 1
        for channel_idx in range(num_channels):
            if len(img.shape) == 3:
                channel = img[:, :, channel_idx]
            else:
                channel = img
            keypoints, descriptors = sift.detectAndCompute(channel, None)

            if descriptors is not None and len(keypoints) > 0:
                for kp, des in zip(keypoints, descriptors):
                    all_keypoints.append((kp, channel_idx))
                    all_descriptors.append(des)

        if not all_descriptors:
            return [], np.array([])

        # Sort by (channel, y, x) for deterministic ordering
        kp_des_pairs = list(zip(all_keypoints, all_descriptors))
        kp_des_pairs.sort(key=lambda x: (x[0][1], x[0][0].pt[1], x[0][0].pt[0]))

        sorted_kp = [p[0][0] for p in kp_des_pairs]
        sorted_des = np.vstack([p[1] for p in kp_des_pairs])

        return sorted_kp, sorted_des

    def compute_epipolar_error(self, F: np.ndarray, pts1: np.ndarray, pts2: np.ndarray) -> float:
        r"""
        计算匹配点的对称极线误差。

        Args:
            F: 基础矩阵，形状为 ``(3, 3)``
            pts1: 第一组点坐标，形状为 ``(N, 2)``
            pts2: 第二组点坐标，形状为 ``(N, 2)``

        Returns:
            平均对称极线误差

        Examples:
            >>> import numpy as np
            >>> sift = SiftSimilarity()
            >>> F = np.eye(3)
            >>> pts = np.array([[1.0, 2.0], [3.0, 4.0]])
            >>> error = sift.compute_epipolar_error(F, pts, pts)
            >>> isinstance(error, float)
            True
            >>> error >= 0
            True
        """

        # Convert to homogeneous coordinates
        pts1_h = np.concatenate([pts1, np.ones((pts1.shape[0], 1))], axis=1)
        pts2_h = np.concatenate([pts2, np.ones((pts2.shape[0], 1))], axis=1)

        # Epipolar lines
        lines2 = pts1_h @ F.T
        lines1 = pts2_h @ F

        # Distance from points to lines
        dist2 = np.abs(np.sum(lines2 * pts2_h, axis=1)) / np.sqrt(
            lines2[:, 0] ** 2 + lines2[:, 1] ** 2 + 1e-8
        )
        dist1 = np.abs(np.sum(lines1 * pts1_h, axis=1)) / np.sqrt(
            lines1[:, 0] ** 2 + lines1[:, 1] ** 2 + 1e-8
        )

        error = (dist1 + dist2) / 2
        return float(np.mean(error))

    def compute_score_from_features(
        self,
        features1: tuple[list[tp.Any], np.ndarray],
        features2: tuple[list[tp.Any], np.ndarray],
    ) -> SiftScoreResult:
        r"""
        从预提取的 SIFT 特征计算相似度分数。

        Args:
            features1: 第一组特征，包含关键点列表和描述符数组
            features2: 第二组特征，包含关键点列表和描述符数组

        Returns:
            ``SiftScoreResult`` 对象，包含相似度分数和各项指标

        Examples:
            >>> import numpy as np
            >>> sift = SiftSimilarity()
            >>> img1 = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            >>> img2 = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            >>> f1 = sift.extract_features(img1)
            >>> f2 = sift.extract_features(img2)
            >>> result = sift.compute_score_from_features(f1, f2)
            >>> 0 <= result.score <= 1
            True
            >>> 0 <= result.match_ratio <= 1
            True
        """

        kp1, des1 = features1
        kp2, des2 = features2

        # Check for empty features
        if des1.size == 0 or des2.size == 0 or len(kp1) == 0 or len(kp2) == 0:
            return SiftScoreResult(
                score=1.0,
                match_ratio=0.0,
                inlier_ratio=0.0,
                epipolar_error=float("inf"),
                num_matches=0,
                num_inliers=0,
            )

        # Detect self-match scenario
        is_self_match = des1 is des2 or (
            des1.shape == des2.shape and des1.size > 0 and np.array_equal(des1, des2)
        )

        matcher = cv2.BFMatcher(cv2.NORM_L2)

        if is_self_match:
            return self._compute_self_match_score(kp1, des1, kp2, des2, matcher)
        else:
            return self._compute_cross_match_score(kp1, des1, kp2, des2, matcher)

    def _compute_self_match_score(
        self,
        kp1: list[tp.Any],
        des1: np.ndarray,
        kp2: list[tp.Any],
        des2: np.ndarray,
        matcher: cv2.BFMatcher,
    ) -> SiftScoreResult:
        r"""
        使用交叉检查计算自匹配场景的分数。

        Args:
            kp1: 第一组关键点
            des1: 第一组描述符
            kp2: 第二组关键点
            des2: 第二组描述符
            matcher: OpenCV ``BFMatcher`` 对象

        Returns:
            ``SiftScoreResult`` 对象
        """

        matches1to2 = matcher.knnMatch(des1, des2, k=1)
        matches2to1 = matcher.knnMatch(des2, des1, k=1)

        good = []
        for i, m_pair in enumerate(matches1to2):
            if len(m_pair) == 1:
                m = m_pair[0]
                j = m.trainIdx
                if j < len(matches2to1) and len(matches2to1[j]) == 1:
                    m_reverse = matches2to1[j][0]
                    if m_reverse.trainIdx == m.queryIdx:
                        good.append(m)

        match_ratio = len(good) / max(len(kp1), len(kp2), 1)
        inlier_ratio = 1.0 if len(good) > 0 else 0.0
        error = 0.0 if len(good) > 0 else float("inf")
        num_inliers = len(good)

        # Geometric verification for self-match
        if len(good) >= 8:
            pts1, pts2 = self._extract_points(kp1, kp2, good)
            if pts1.shape[0] >= 8:
                try:
                    F, mask = cv2.findFundamentalMat(pts1, pts2, cv2.RANSAC, 3.0, 0.99)
                    if F is not None and mask is not None:
                        num_inliers = int(mask.sum())
                        inlier_ratio = num_inliers / len(good)
                        if num_inliers >= 8:
                            pts1_inliers = pts1[mask.ravel().astype(bool)]
                            pts2_inliers = pts2[mask.ravel().astype(bool)]
                            error = self.compute_epipolar_error(F, pts1_inliers, pts2_inliers)
                except cv2.error:
                    pass

        normalized_error = min(error / 100.0, 1.0)
        score = (
            self.w1 * (1 - match_ratio) + self.w2 * (1 - inlier_ratio) + self.w3 * normalized_error
        )

        return SiftScoreResult(
            score=score,
            match_ratio=match_ratio,
            inlier_ratio=inlier_ratio,
            epipolar_error=error,
            num_matches=len(good),
            num_inliers=num_inliers,
        )

    def _compute_cross_match_score(
        self,
        kp1: list[tp.Any],
        des1: np.ndarray,
        kp2: list[tp.Any],
        des2: np.ndarray,
        matcher: cv2.BFMatcher,
    ) -> SiftScoreResult:
        r"""
        使用交叉检查计算交叉匹配场景的分数。

        Args:
            kp1: 第一组关键点
            des1: 第一组描述符
            kp2: 第二组关键点
            des2: 第二组描述符
            matcher: OpenCV ``BFMatcher`` 对象

        Returns:
            ``SiftScoreResult`` 对象
        """

        matches1to2 = matcher.knnMatch(des1, des2, k=1)
        matches2to1 = matcher.knnMatch(des2, des1, k=1)

        good = []
        for i, m_pair in enumerate(matches1to2):
            if len(m_pair) == 1:
                m = m_pair[0]
                j = m.trainIdx
                if j < len(matches2to1) and len(matches2to1[j]) == 1:
                    m_reverse = matches2to1[j][0]
                    if m_reverse.trainIdx == m.queryIdx:
                        good.append(m)

        match_ratio = len(good) / max(len(kp1), len(kp2), 1)

        inlier_ratio = 0.0
        error = float("inf")
        num_inliers = 0

        if len(good) >= 8:
            pts1, pts2 = self._extract_points(kp1, kp2, good)
            if pts1.shape[0] >= 8:
                inlier_ratio, error, num_inliers = self._compute_geometric_consistency(
                    pts1, pts2, len(good)
                )

        normalized_error = min(error / 100.0, 1.0)
        score = (
            self.w1 * (1 - match_ratio) + self.w2 * (1 - inlier_ratio) + self.w3 * normalized_error
        )

        return SiftScoreResult(
            score=score,
            match_ratio=match_ratio,
            inlier_ratio=inlier_ratio,
            epipolar_error=error,
            num_matches=len(good),
            num_inliers=num_inliers,
        )

    def _extract_points(
        self,
        kp1: list[tp.Any],
        kp2: list[tp.Any],
        matches: list[tp.Any],
    ) -> tuple[np.ndarray, np.ndarray]:
        r"""
        从匹配中提取点坐标，包含边界检查。

        Args:
            kp1: 第一组关键点
            kp2: 第二组关键点
            matches: 匹配列表

        Returns:
            包含两组点坐标的元组，形状均为 ``(N, 2)``
        """

        pts1_list = []
        pts2_list = []
        for m in matches:
            if m.queryIdx < len(kp1) and m.trainIdx < len(kp2):
                pts1_list.append(kp1[m.queryIdx].pt)
                pts2_list.append(kp2[m.trainIdx].pt)
        return np.array(pts1_list, dtype=np.float32), np.array(pts2_list, dtype=np.float32)

    def _compute_geometric_consistency(
        self, pts1: np.ndarray, pts2: np.ndarray, num_matches: int
    ) -> tuple[float, float, int]:
        r"""
        使用基础矩阵估计计算几何一致性。

        Args:
            pts1: 第一组点坐标，形状为 ``(N, 2)``
            pts2: 第二组点坐标，形状为 ``(N, 2)``
            num_matches: 匹配点数量

        Returns:
            包含内点率、误差和内点数量的元组
        """

        inlier_ratio = 0.0
        error = float("inf")
        num_inliers = 0

        if (
            pts1.ndim == 2
            and pts2.ndim == 2
            and pts1.shape[1] == 2
            and pts2.shape[1] == 2
            and pts1.shape[0] == pts2.shape[0]
            and pts1.shape[0] >= 8
        ):
            try:
                F, mask = cv2.findFundamentalMat(
                    pts1, pts2, cv2.RANSAC, ransacReprojThreshold=3.0, confidence=0.99
                )
            except cv2.error:
                try:
                    F, mask = cv2.findFundamentalMat(pts1, pts2, cv2.LMEDS)
                except cv2.error:
                    F, mask = None, None

            if F is not None and mask is not None and mask.size > 0:
                inlier_mask = mask.ravel().astype(bool)
                if inlier_mask.shape[0] == pts1.shape[0]:
                    num_inliers = int(inlier_mask.sum())
                    inlier_ratio = num_inliers / num_matches
                    if num_inliers >= 8:
                        pts1_inliers = pts1[inlier_mask]
                        pts2_inliers = pts2[inlier_mask]
                        if pts1_inliers.shape[0] > 0 and pts2_inliers.shape[0] > 0:
                            error = self.compute_epipolar_error(F, pts1_inliers, pts2_inliers)

        return inlier_ratio, error, num_inliers

    def compute(self, images: tp.Sequence[np.ndarray]) -> np.ndarray:
        r"""
        计算基于 SIFT 的图像相似度。

        Args:
            images: 图像序列，OpenCV BGR 格式

        Returns:
            相似度分数数组，形状为 (num_images, 2)
            - [:, 0]: 与基准图像（索引 0）的相似度，1 表示完全相同
            - [:, 1]: 与特征图像（索引 -1）的相似度，1 表示完全相同

        Examples:
            >>> import numpy as np
            >>> sift = SiftSimilarity()
            >>> img1 = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            >>> img2 = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            >>> scores = sift.compute([img1, img2])
            >>> scores.shape
            (2, 2)
            >>> bool(0 <= scores[0, 0] <= 1)
            True
            >>> bool(scores[0, 0] == 1.0)  # 与自身相似度为 1
            True
        """

        num_images = len(images)
        scores = np.zeros((num_images, 2))

        # Pre-extract features for all images
        all_features = [self.extract_features(img) for img in images]

        base_features = all_features[0]
        feature_features = all_features[-1]

        # Base reference: first image compared with all images
        for i in range(num_images):
            result = self.compute_score_from_features(base_features, all_features[i])
            scores[i, 0] = 1.0 - result.score  # Convert to similarity (1 = identical)

        # Feature reference: last image compared with all images
        for i in range(num_images):
            result = self.compute_score_from_features(feature_features, all_features[i])
            scores[i, 1] = 1.0 - result.score  # Convert to similarity (1 = identical)

        return scores
