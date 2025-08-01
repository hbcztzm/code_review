#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
代码评审脚本
使用OpenAI API对Git提交的代码变更进行评审
"""

import os
import re
import sys
import argparse
import requests
import configparser
import logging
from pathlib import Path
from typing import Tuple

# 初始化日志系统
def setup_logging():
    log_dir = Path(".git/logs")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "code_review.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
    except Exception as e:
        print(f"初始化日志失败: {e}", file=sys.stderr)
        sys.exit(1)

setup_logging()

# 默认的OpenAI API配置
DEFAULT_API_URL = "https://api.hunyuan.cloud.tencent.com/v1/chat/completions"
DEFAULT_MODEL = "hunyuan-turbos-latest"
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TEMPERATURE = 0.1

# 默认配置文件路径
DEFAULT_CONFIG_FILE = os.path.expanduser("~/.code_review_config.ini")

def parse_arguments(config):
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='使用OpenAI API进行代码评审')
    parser.add_argument('--diff', type=str, help='Git diff内容')
    parser.add_argument('--diff-file', type=str, help='包含Git diff内容的文件路径')
    parser.add_argument('--staged', action='store_true', help='评审暂存区的变更 (git diff --cached)')
    parser.add_argument('--branch', type=str, help='评审与指定分支的差异 (git diff <branch>)')
    parser.add_argument('--commit', type=str, help='评审指定提交的变更 (git diff <commit>)')
    parser.add_argument('--config', type=str, default=DEFAULT_CONFIG_FILE, help=f'配置文件路径 (默认: {DEFAULT_CONFIG_FILE})')
    parser.add_argument('--api-key', type=str, help='OpenAI API密钥')
    parser.add_argument('--api-url', type=str, help='OpenAI API URL')
    parser.add_argument('--model', type=str, help='OpenAI模型名称')
    parser.add_argument('--max-tokens', type=int, help='最大生成令牌数')
    parser.add_argument('--temperature', type=float, help='生成温度')
    parser.add_argument('--verbose', action='store_true', help='显示详细日志信息')
    parser.add_argument('--working-tree', action='store_true', default=True, help='评审工作区的变更 (git diff) - 默认行为')
    parser.add_argument('--context', '-c', type=int, default=config['context_lines'], help=f'显示的上下文行数 (默认: {config["context_lines"]})')
    parser.add_argument('--commit-msg', type=str, help='提交消息内容')

    return parser.parse_args()

def filter_diff_by_extensions(diff_content: str, extensions: list) -> str:
    """根据文件后缀过滤diff内容"""
    if not extensions:
        return diff_content
    
    filtered_diff = []
    current_block = []
    in_block = False
    include_block = False
    
    for line in diff_content.split('\n'):
        if line.startswith('diff --git'):
            # 处理前一个块
            if in_block and include_block:
                filtered_diff.extend(current_block)
            # 开始新块
            in_block = True
            include_block = False
            current_block = [line]
        elif in_block:
            current_block.append(line)
            if line.startswith('+++ b/'):
                current_file = line[6:]  # 去掉 "+++ b/" 前缀
                include_block = any(current_file.endswith(ext) for ext in extensions)
        else:
            if include_block:
                filtered_diff.append(line)
    
    # 处理最后一个块
    if in_block and include_block:
        filtered_diff.extend(current_block)
    logging.info(filtered_diff)
    return '\n'.join(filtered_diff)

def optimize_diff_content(diff_content: str, config: dict) -> str:
    """优化差异内容以减少token消耗"""
    if not diff_content:
        return diff_content
    
    # 按文件分割差异内容
    diff_blocks = []
    current_block = []
    is_new_file = False
    
    for line in diff_content.split('\n'):
        if line.startswith('diff --git'):
            if current_block:
                diff_blocks.append((is_new_file, '\n'.join(current_block)))
            current_block = [line]
            is_new_file = False
        elif line.startswith('+++ b/') and not any(l.startswith('--- a/') for l in current_block):
            is_new_file = True
            current_block.append(line)
        else:
            current_block.append(line)
    if current_block:
        diff_blocks.append((is_new_file, '\n'.join(current_block)))
    
    optimized_blocks = []
    
    for is_new, block in diff_blocks:
        lines = block.split('\n')
        max_lines = config.get('max_new_file_lines', 200) if is_new else config.get('max_diff_lines', 500)
        
        if len(lines) > max_lines:
            # 优先保留关键内容
            important_lines = []
            other_lines = []
            for line in lines:
                if any(re.search(pattern, line) for pattern in config.get('priority_patterns', [])):
                    important_lines.append(line)
                elif is_new and line.startswith('+') and not line.startswith('++'):
                    # 对于新增文件，也保留部分新增内容
                    other_lines.append(line)
                elif not is_new:
                    other_lines.append(line)
            
            # 保留所有关键内容+部分其他内容
            keep_lines = important_lines + other_lines[:max_lines - len(important_lines)]
            optimized_block = '\n'.join(keep_lines)
            trunc_msg = f"\n... (truncated {len(lines) - len(keep_lines)} lines, {'new file' if is_new else 'modified file'})"
            optimized_blocks.append(optimized_block + trunc_msg)
        else:
            optimized_blocks.append(block)
    
    return '\n'.join(optimized_blocks)

def compress_content(content: str, config: dict) -> str:
    """压缩内容以减少token使用"""
    if not content or not config.get('enable_compression', True):
        return content
    
    # 移除多余空白行
    lines = [line for line in content.split('\n') if line.strip() != '']
    
    # 简化常见模式
    compressed = []
    for line in lines:
        # 简化import语句
        if line.startswith('import ') or line.startswith('from '):
            line = line.replace(' ', '')
        # 移除行尾注释
        line = line.split('#')[0].rstrip()
        compressed.append(line)
    
    # 合并短行
    merged = []
    current_line = ''
    for line in compressed:
        if len(line) < 20 and len(current_line) + len(line) < 80:
            current_line += '; ' + line if current_line else line
        else:
            if current_line:
                merged.append(current_line)
            current_line = line
    if current_line:
        merged.append(current_line)
    
    return '\n'.join(merged)

def get_diff_content(args, config) -> str:
    """获取Git diff内容"""
    # 如果提供了直接的diff内容，优先使用
    if args.diff:
        diff_content = args.diff
        filtered = filter_diff_by_extensions(diff_content, config['file_extensions'])
        optimized = optimize_diff_content(filtered, config)
        return compress_content(optimized, config)
    
    # 如果提供了diff文件路径，从文件读取
    elif args.diff_file:
        try:
            with open(args.diff_file, 'r', encoding='utf-8') as f:
                diff_content = f.read()
                filtered = filter_diff_by_extensions(diff_content, config['file_extensions'])
                optimized = optimize_diff_content(filtered, config)
                return compress_content(optimized, config)
        except Exception as e:
            logging.error(f"读取diff文件失败: {e}")
            sys.exit(1)
    
    # 否则，尝试自动调用git diff
    else:
        import subprocess
        
        try:
            # 检查是否在Git仓库中
            subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'],
                          check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            git_cmd = ['git', 'diff', f'-U{args.context}']  # 使用用户指定的上下文行数
            
            # 根据参数构建git diff命令
            if args.staged:
                git_cmd.append('--cached')
                args.working_tree = False  # 如果指定了--staged，则禁用工作区检查
            elif args.branch:
                git_cmd.append(args.branch)
                args.working_tree = False  # 如果指定了--branch，则禁用工作区检查
            elif args.commit:
                git_cmd.append(args.commit)
                args.working_tree = False  # 如果指定了--commit，则禁用工作区检查
            # 默认检查工作区变更
            
            # 执行git diff命令
            result = subprocess.run(git_cmd, check=True, capture_output=True, text=True)
            diff_content = result.stdout
            
            # 如果没有差异，提示用户
            if not diff_content.strip():
                if args.staged:
                    logging.error("没有暂存的变更。请使用 'git add' 添加要评审的文件。")
                elif args.working_tree:
                    logging.error("工作区没有未提交的变更。如果你已经暂存了变更，请使用 --staged 参数。")
                else:
                    logging.error("没有检测到代码变更。")
                sys.exit(0)
            
            # 过滤diff内容
            return filter_diff_by_extensions(diff_content, config['file_extensions'])
            
        except subprocess.CalledProcessError as e:
            logging.error(f"执行git命令失败: {e}")
            logging.error("请确保你在Git仓库中运行此脚本，或者使用--diff或--diff-file参数提供差异内容。")
            sys.exit(1)
        except Exception as e:
            logging.error(f"获取Git差异失败: {e}")
            logging.error("请使用--diff或--diff-file参数手动提供差异内容。")
            sys.exit(1)

def load_config(config_path=None):
    """加载配置文件"""
    config = {
        'api_key': None,
        'api_url': DEFAULT_API_URL,
        'model': DEFAULT_MODEL,
        'max_tokens': DEFAULT_MAX_TOKENS,
        'temperature': DEFAULT_TEMPERATURE,
        'verbose': False,
        'context_lines': 10,  # 默认显示10行上下文
        'file_extensions': [],  # 默认扫描所有文件
        'max_diff_lines': 500,  # 默认最大差异行数
        'priority_patterns': [  # 优先保留的模式
            r'^\s*def\s+\w+\(',  # 函数定义
            r'^\s*class\s+\w+',  # 类定义
            r'^\s*@\w+'  # 装饰器
        ]
    }
    
    # 如果未指定配置文件路径，使用默认路径
    if not config_path:
        config_path = DEFAULT_CONFIG_FILE
    
    # 检查配置文件是否存在
    config_file = Path(config_path)
    if not config_file.exists():
        # 创建示例配置文件
        try:
            config_file.parent.mkdir(parents=True, exist_ok=True)
            parser = configparser.ConfigParser()
            parser['openai'] = {
                'api_key': 'your-api-key-here',
                'api_url': DEFAULT_API_URL,
                'model': DEFAULT_MODEL,
                'max_tokens': str(DEFAULT_MAX_TOKENS),
                'temperature': str(DEFAULT_TEMPERATURE)
            }
            parser['settings'] = {
                'verbose': 'false'
            }
            with open(config_file, 'w', encoding='utf-8') as f:
                parser.write(f)
            logging.info(f"已创建示例配置文件 {config_file}，请编辑它并添加你的API密钥")
        except Exception as e:
            logging.warning(f"创建示例配置文件时出错: {e}")
        return config
    
    try:
        parser = configparser.ConfigParser()
        parser.read(config_file)
        
        if 'openai' in parser:
            section = parser['openai']
            if 'api_key' in section:
                config['api_key'] = section['api_key']
            if 'api_url' in section:
                config['api_url'] = section['api_url']
            if 'model' in section:
                config['model'] = section['model']
            if 'max_tokens' in section and section['max_tokens']:
                config['max_tokens'] = int(section['max_tokens'])
            if 'temperature' in section and section['temperature']:
                config['temperature'] = float(section['temperature'])
        
        if 'settings' in parser:
            section = parser['settings']
            if 'verbose' in section:
                config['verbose'] = section['verbose'].lower() in ('true', 'yes', '1', 'on')
        
        if 'git' in parser:
            section = parser['git']
            if 'context_lines' in section and section['context_lines']:
                config['context_lines'] = int(section['context_lines'])
            if 'file_extensions' in section and section['file_extensions']:
                config['file_extensions'] = [
                    ext.strip() for ext in section['file_extensions'].split(',') 
                    if ext.strip()
                ]
    except Exception as e:
        logging.error(f"警告: 读取配置文件时出错: {e}")
    
    return config

def get_api_key(args, config) -> str:
    """获取OpenAI API密钥"""
    # 优先级: 命令行参数 > 配置文件 > 环境变量
    if args.api_key:
        return args.api_key
    
    if config['api_key'] and config['api_key'] != 'your-api-key-here':
        return config['api_key']

    # 其次使用环境变量中的API密钥
    api_key = os.environ.get('OPENAI_API_KEY')
    if api_key:
        return api_key

    logging.error("错误: 未提供OpenAI API密钥。请通过以下方式之一提供:")
    logging.error(f"1. 编辑配置文件 {args.config} 并添加你的API密钥")
    logging.error("2. 使用命令行参数: --api-key YOUR_API_KEY")
    logging.error("3. 设置环境变量: export OPENAI_API_KEY=YOUR_API_KEY")
    sys.exit(1)
def get_commit_message(commit_msg: str = None) -> str:
    """获取当前提交消息
    Args:
        commit_msg: 提交消息内容，由pre-commit钩子传入
    """
    if commit_msg:
        return commit_msg.strip()
    return ""

def review_code(diff_content: str, api_key: str, api_url: str, model: str,
                max_tokens: int, temperature: float, verbose: bool,
                commit_msg: str = None) -> Tuple[bool, str]:
    """
    使用OpenAI API对代码进行评审

    返回:
        (通过评审?, 评审意见)
    """
    # 检查提交消息中是否包含确认提交标记
    if len(diff_content)==0:
        if verbose:
            logging.info("没有代码变更，自动通过评审")
        return True, "没有代码变更，自动通过评审\n评审结果: 通过"


    commit_msg = get_commit_message(commit_msg)
    logging.info(f"提交消息: {commit_msg}\n")
    if "confirm commit" in commit_msg.lower():
        if verbose:
            logging.info("检测到确认提交标记，自动通过评审")
        return True, "检测到确认提交标记，自动通过代码评审\n评审结果: 通过"
    
    if verbose:
        logging.info("正在发送代码评审请求...")

    # 构建评审提示
    prompt = f"""
你是一位经验丰富的高级软件工程师，负责代码评审。请评审以下Git diff中的代码变更:

```diff
{diff_content}
```

评审标准说明：
1. 代码质量：仅否决存在严重混淆或无法运行的结构性问题
2. 潜在问题：仅否决会导致系统崩溃/数据损坏的安全漏洞
3. 最佳实践：接受基本功能实现，不强制高级设计模式
4. 可维护性：接受需简单注释即可理解的代码

强制通过条件：
1. 代码实现基本功能且无严重缺陷
2. 代码没有安全问题
3. 对测试类和测试代码执行宽松校验


强制否决条件（满足任一即否决）：
1. 代码无法编译/运行
2. 存在安全漏洞
3. 严重性能问题（响应时间>1秒）

评审结论必须明确包含以下内容：
### 评审结论 [通过/不通过] 

### 详细说明
1. 是否符合强制通过条件
2. 是否存在强制否决条件
3. 其他改进建议（非强制）

请严格按此格式返回评审结果。
"""

    # 构建API请求
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一位经验丰富的高级软件工程师，负责进行严格的代码评审。"},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": temperature
    }

    try:
        
        response = requests.post(api_url, headers=headers, json=payload, timeout=600)
        response.raise_for_status()  # 如果请求失败，抛出异常

        result = response.json()
        if verbose:
            logging.info("收到API响应")

        # 提取评审意见
        review_content = result["choices"][0]["message"]["content"].strip()

        # 判断评审结果 - 根据新的标准格式
        passed = False
        if "### 评审结论 [通过]" in review_content:
            passed = True
        elif "### 评审结论 [不通过]" in review_content:
            passed = False
        else:
            # 如果没有明确结论，默认不通过并要求人工审核
            review_content += "\n⚠️ 警告：无法确定评审结论，请人工审核"
            passed = False

        return passed, review_content

    except Exception as e:
        logging.error(f"API请求失败: {e}")
        if verbose and 'response' in locals():
            logging.error(f"响应内容: {response.text}",)
        sys.exit(1)

def main():
    """主函数"""
    # 先解析--config参数
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--config', type=str, default=DEFAULT_CONFIG_FILE)
    config_args, _ = parser.parse_known_args()
    
    # 加载配置文件
    config = load_config(config_args.config)
    
    # 解析所有参数
    args = parse_arguments(config)
    
    # 优先级: 命令行参数 > 配置文件 > 默认值
    verbose = args.verbose if args.verbose else config.get('verbose', False)

    logging.info(f"verbose:{verbose}")
    # 获取diff内容
    diff_content = get_diff_content(args, config)
    if verbose:
        logging.info(f"获取到{len(diff_content)}字节的diff内容")

    # 获取API密钥
    api_key = get_api_key(args, config)
    
    # 优先级: 命令行参数 > 配置文件 > 默认值
    api_url = args.api_url or config['api_url']
    model = args.model or config['model']
    max_tokens = args.max_tokens or config['max_tokens']
    temperature = args.temperature or config['temperature']
    
    if verbose:
        logging.info(f"使用API URL: {api_url}")
        logging.info(f"使用模型: {model}")
        logging.info(f"最大令牌数: {max_tokens}")
        logging.info(f"温度: {temperature}")

    # 进行代码评审
    passed, review_content = review_code(
        diff_content=diff_content,
        api_key=api_key,
        api_url=api_url,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        verbose=verbose,
        commit_msg=args.commit_msg
    )

    # 输出评审结果
    logging.info("\n===== 代码评审结果 =====")
    logging.info(review_content)
    logging.info("=======================\n")

    # 根据评审结果决定是否允许提交
    if passed:
        logging.info("✅ 代码评审通过，允许提交")
        sys.exit(0)
    else:
        logging.info("❌ 代码评审不通过，请修复问题后再次提交")
        sys.exit(1)

if __name__ == "__main__":
    main()
