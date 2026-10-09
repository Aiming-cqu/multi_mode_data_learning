# 周报归纳

本文件用于记录基于 commit 历史的每周/双周工作总结。

---

## 2026-04-06 ～ 2026-04-22（双周）

- CR 拐点定位应用
	* 评测
		- 开发正向 CR 拐点标注工具
		（标注示意图）
		- 完成 0313 + 0327 release 版本不一致场景 CR 标注，共标注 75 条，无拐点 23，单拐点 21，多拐点 29
		（无效场景细分统计）
		- 完成初版评测工具开发 <https://git.xiaojukeji.com/luonairui/vlm-triage/tree/eval/lib/evaluations>
		- 覆盖 定位任务 & CR 粒度 + dpe & 模型 指标计算
		（指标值图：DPE & 模型，Recall & Precision， Scene & CR）
		（指标定义图，top-N定义可能有偏差）
	* 模型 badcase 抽样分析
		- 采样问题较多，其中感知影响占比大，例：<http://10.190.55.60:8000/pages/crlocator.html?id=4769865>
		- path > 横向动作 > 画面转向 对模型判定 影响较大，脱离 topic，例：<http://10.190.55.60:8000/pages/crlocator.html?id=4769781>
		- 定位到有效但 P2P/F2F 结果，例：<http://10.190.55.60:8000/pages/crlocator.html?id=4788637>
		- 非链路拐点，例： <http://10.190.55.60:8000/pages/crlocator.html?id=4914243#scenario_23892540>
	* 效果提升
		- VL Embedding 模型探索：Qwen3-VL-Embedding-8B 文本引导图像特征生成有效性得到验证（纯色 testcase 相关性影响 ～3%），待验证仿真图像

## 2026-05-08

- CR 拐点定位应用
	* 效果提升
		- 更新定位结果接口，支持零/多拐点正常输出
		- 评测模块合并到 master，进行中，调整多对多准召评价逻辑
		- 开发并验证置换检验在拐点定位的效果，效果不符合预期，反思构造方法 @aiming

- 其他
	* 休假 3.5 天

---

## 2026-05-09 ～ 2026-05-17（单周）

- CR 拐点定位应用
	* 效果提升
		- 多 CR 候选输出支持（`multi cr`）
		- embedding API 支持 VL 模型接入（`embedding_api support vl models`）
		- fix: 修正 API 端点的 query params 问题

- GPU 并发模型推理 & Experiment Framework
	* vLLM PoC 探索完成，合并到 master
		- 完成 vLLM GPU offloading 调度实验（`gpu-offloading vllm scheduling`）
		- 实验管理工具框架：实验目录结构、配置/日志/结果管理
	* 重构实验工具
		- 支持 `PROJECT_ROOT` 环境变量和多候选评估模式（baseline + candidates）
		- 严格 schema 验证和 error-aware 指标评估
	* 使用 vLLM Python API 进行 GPU offloading 的调研文档
	* 调整 GPU memory utilization 参数

- 测试更新
	* 测试矩阵文档 + pytest marker 配置（smoke / functional / coverage）
	* 测试套件分层重构：smoke → functional → coverage
	* coverage 测试更新，冲突合并

- 文档 & 配置
	* vLLM / Pixi 排障止损规则加入 copilot-instructions
	* 项目配置更新适配 pixi 0.68
	* 关闭 MTP 后恢复（`enable MTP`）
	* S3 key 脱敏处理
	* 更新 agent hooks 和 clinerules

- SOTA 模型调研
	* 排查 FlashInfer JIT 编译失败问题：Python 3.12 vs 3.13 头文件路径不匹配
	* 清理 JIT 缓存（`~/.cache/flashinfer/0.6.6/90a`）后恢复

- 新规划
	* 【缓存系统】（Feature, High）— 缓存系统架构设计，L1/L2 缓存分层
	* 【Resource 模块测试覆盖】（Task, High）— 7 个生命周期 + 12 个 Repository 测试用例
