# Project Rules and Guidelines

Agent 代码生成、命令执行的严格约束。所有 Agent 必须遵循。

## 规则文件

| 文件 | 内容 |
|------|------|
| [coding-guidelines.md](coding-guidelines.md) | 编码规范，包含命名规范、import 规则、trailing comma、字符串引号、shebang、match-case、Schema、异常、async、repr、传参等 |
| [type-annotations.md](type-annotations.md) | 类型批注完整规范：Optional、Annotated、接口、@overload、args/kwds |

## 规则优先级

所有规则文件同等优先，互为补充，完整参考以 [guides/development-bible.md](../guides/development-bible.md) 为准。

## 如何编写新规则

使用 [templates/rule-template.md](../templates/rule-template.md)，包含：目的和适用范围、术语定义、流程/检查清单、DO/DON'T。
