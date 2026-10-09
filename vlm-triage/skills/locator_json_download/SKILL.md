# Locator JSON 文件下载技能

## 名称和简介
**Act 类** - 自动化执行 S3 文件搜索和下载操作

## 何时使用
- 当您需要根据 `locator_id` 快速找到并下载对应的评估结果 JSON 文件时
- 避免手动执行复杂的 S3 CLI 命令和管道操作
- 批量处理多个 locator_id 的文件下载需求

## 核心概念
- **locator_id**: 定位器ID，用于唯一标识一个CR定位评估任务
- **S3 存储结构**: 文件存储在 `luonairui/data/visual-cr-locator-fe/` 路径下，按日期组织
- **自动化搜索**: 使用 `pixi run s3-cli ls --recursive` 配合 `grep` 过滤
- **一键下载**: 自动提取完整路径并执行下载命令

## 快速开始
```bash
# 1. 激活 pixi 环境
pixi shell

# 2. 执行下载命令（替换实际的locator_id）
./skills/locator_json_download/locator_json_download.sh 4551211
```

## 高级用法
### DO
- ✅ 在项目根目录下运行脚本
- ✅ 使用真实的 locator_id（如 4551211）
- ✅ 检查下载后的文件内容是否完整

### DON'T  
- ❌ 不要在其他目录运行（会找不到 pixi 环境）
- ❌ 不要传入非数字的 locator_id
- ❌ 不要同时运行多个实例（可能造成文件覆盖）

## 最佳实践
### DO
- ✅ 先用小的 locator_id 测试脚本功能
- ✅ 下载后立即检查文件内容
- ✅ 将下载的文件重命名为有意义的名称以便管理

### DON'T
- ❌ 不要删除或修改脚本中的错误处理逻辑
- ❌ 不要在没有网络连接的环境下运行

## 故障排除
### 常见问题
1. **"未找到文件" 错误**
   - 原因：locator_id 不存在或文件尚未上传到 S3
   - 解决：使用提供的手动搜索命令确认文件是否存在

2. **"权限错误" 或 "命令未找到"**
   - 原因：未激活 pixi 环境
   - 解决：先运行 `pixi shell` 激活环境

3. **下载的文件为空**
   - 原因：S3 网络问题或文件损坏
   - 解决：重新运行命令，或手动使用 s3-cli 下载

### 调试命令
```bash
# 手动搜索文件
pixi run s3-cli ls --recursive "luonairui/data/visual-cr-locator-fe" | grep "locator_id=4551211"

# 手动下载文件
pixi run s3-cli get "luonairui/data/visual-cr-locator-fe/202604/locator_id=4551211-scenario_id=22549553.f6383cad9cae.json" "output.json"
```