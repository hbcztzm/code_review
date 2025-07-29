# Git代码评审助手

这个项目提供了一个Git pre-commit钩子，可以在提交代码前自动使用OpenAI API进行代码评审。如果评审通过，允许提交；如果评审不通过，则阻止提交并显示需要修复的问题。

## 功能特点

- 自动获取git diff内容（即将要提交的更改）
- 调用OpenAI API进行代码评审
- 根据评审结果决定是否允许提交
- 提供详细的评审意见和改进建议

## 系统要求

- Git
- Python 3.6+
- OpenAI API密钥

## 安装步骤

1. 克隆或下载此仓库到本地

2. 设置OpenAI API密钥
   ```bash
   export OPENAI_API_KEY='your-api-key'
   ```
   
   为了持久化设置，可以将上述命令添加到你的shell配置文件（如`~/.bashrc`、`~/.zshrc`等）

3. 运行安装脚本
   ```bash
   ./install.sh
   ```
   
   这个脚本会：
   - 安装必要的Python依赖
   - 设置Git pre-commit钩子
   - 检查环境配置

## 使用方法

安装完成后，每次执行`git commit`命令时，系统会自动：

1. 获取暂存区的代码变更
2. 将变更发送给OpenAI进行评审
3. 显示评审结果
4. 根据评审结果决定是否允许提交

如果评审通过，提交将正常进行；如果评审不通过，提交将被阻止，并显示需要修复的问题。

## 配置选项

### 配置文件

你可以创建一个配置文件来设置API密钥、API URL、模型名称等参数，而不必每次都通过命令行参数或环境变量提供。默认配置文件路径为`~/.code_review_config.ini`。

配置文件示例（`config_example.ini`）：
```ini
[openai]
# OpenAI API密钥
api_key = your_api_key_here

# API请求地址 (默认: https://api.openai.com/v1/chat/completions)
api_url = https://api.openai.com/v1/chat/completions

# 模型名称 (默认: gpt-4)
model = gpt-4

# 最大生成令牌数 (默认: 1000)
max_tokens = 1000

# 生成温度 (默认: 0.1)
temperature = 0.1
```

使用自定义配置文件：
```bash
./code_review.py --config /path/to/your/config.ini --diff-file changes.diff
```

### 增加日志配置 
日志保存路径为 .git/logs/code_review.log

### 跳过代码审核
在提交时，提交的msg中包含confirm commit 则跳过代码审核


### 命令行参数

你可以通过命令行参数覆盖配置文件中的设置：

```bash
./code_review.py --api-key "your-api-key" --model "gpt-3.5-turbo" --max-tokens 2000 --temperature 0.2
```

参数优先级：命令行参数 > 配置文件 > 环境变量 > 默认值

### 自定义OpenAI模型

默认使用`gpt-4`模型进行代码评审。你可以通过配置文件或命令行参数指定其他模型。

### 调整评审严格程度

可以通过修改`code_review.py`中的评审提示来调整评审的严格程度和关注点。

### 跳过代码评审

#### 基本用法
在特殊情况下，可以使用`--no-verify`参数跳过代码评审：
```bash
git commit --no-verify -m "紧急修复：跳过代码评审"
```

#### 高级选项
1. **临时环境变量**（仅当前终端会话有效）：
   ```bash
   export GIT_NO_VERIFY=1
   git commit -m "临时提交"
   ```

2. **全局配置**（不推荐）：
   ```bash
   git config --global hooks.no-verify true
   ```

#### 注意事项
⚠️ **重要安全提示**：
- 所有跳过操作都会记录在`.git/logs/code_review_skip.log`
- 生产环境代码强烈不建议跳过评审
- 频繁跳过会触发警告通知

#### 重新启用评审
```bash
unset GIT_NO_VERIFY
git config --global --unset hooks.no-verify
```

## 故障排除

### API密钥问题

如果遇到API密钥相关的错误，请确保：
- 已正确设置`OPENAI_API_KEY`环境变量
- API密钥有效且未过期
- 账户余额充足

### 网络问题

如果遇到网络连接问题，请检查：
- 网络连接是否正常
- 是否需要配置代理
- OpenAI API服务是否可用

## 许可证

MIT

## 贡献指南

欢迎提交Issue和Pull Request来改进这个项目。