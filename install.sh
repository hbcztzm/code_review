#!/bin/bash
# 安装脚本 - 设置Git代码评审钩子

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}[安装]${NC} 开始安装Git代码评审钩子..."

# 检查是否在Git仓库中
if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    echo -e "${RED}错误: 当前目录不是Git仓库${NC}" >&2
    exit 1
fi

# 获取项目根目录
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
# 钩子源文件和目标文件
HOOK_SOURCE="${PROJECT_ROOT}/hooks/pre-commit"
HOOK_TARGET="${PROJECT_ROOT}/.git/hooks/pre-commit"

# 检查钩子源文件是否存在
if [ ! -f "$HOOK_SOURCE" ]; then
    echo -e "${RED}错误: 未找到钩子源文件: ${HOOK_SOURCE}${NC}" >&2
    exit 1
fi

# 检查钩子源文件是否可执行
if [ ! -x "$HOOK_SOURCE" ]; then
    echo -e "${YELLOW}警告: 钩子源文件不可执行，正在添加执行权限...${NC}"
    chmod +x "$HOOK_SOURCE"
fi

# 检查评审脚本是否存在并可执行
REVIEW_SCRIPT="${PROJECT_ROOT}/code_review.py"
if [ ! -f "$REVIEW_SCRIPT" ]; then
    echo -e "${RED}错误: 未找到代码评审脚本: ${REVIEW_SCRIPT}${NC}" >&2
    exit 1
fi
if [ ! -x "$REVIEW_SCRIPT" ]; then
    echo -e "${YELLOW}警告: 代码评审脚本不可执行，正在添加执行权限...${NC}"
    chmod +x "$REVIEW_SCRIPT"
fi

# 安装Python依赖
echo -e "${BLUE}[安装]${NC} 正在安装Python依赖..."
if ! pip install -r "${PROJECT_ROOT}/requirements.txt"; then
    echo -e "${YELLOW}警告: 安装Python依赖失败，请手动安装${NC}"
    echo -e "${YELLOW}运行: pip install -r ${PROJECT_ROOT}/requirements.txt${NC}"
fi

# 创建钩子目录（如果不存在）
mkdir -p "$(dirname "$HOOK_TARGET")"

# 备份现有钩子（如果存在）
if [ -f "$HOOK_TARGET" ]; then
    BACKUP_FILE="${HOOK_TARGET}.backup.$(date +%Y%m%d%H%M%S)"
    echo -e "${YELLOW}警告: 已存在pre-commit钩子，正在备份到 ${BACKUP_FILE}${NC}"
    mv "$HOOK_TARGET" "$BACKUP_FILE"
fi

# 创建符号链接
echo -e "${BLUE}[安装]${NC} 正在安装pre-commit钩子..."
ln -sf "$HOOK_SOURCE" "$HOOK_TARGET"

# 检查OpenAI API密钥是否设置
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${YELLOW}警告: 未设置OPENAI_API_KEY环境变量${NC}"
    echo -e "${YELLOW}您可以通过以下方式提供API密钥:${NC}"
    echo -e "${YELLOW}  1. 设置环境变量: export OPENAI_API_KEY='your-api-key'${NC}"
    echo -e "${YELLOW}  2. 创建配置文件: ~/.code_review_config.ini${NC}"
    echo -e "${YELLOW}     配置文件示例可在 ${PROJECT_ROOT}/config_example.ini 中找到${NC}"
    
    # 复制配置示例文件
    CONFIG_EXAMPLE="${PROJECT_ROOT}/config_example.ini"
    if [ -f "$CONFIG_EXAMPLE" ]; then
        echo -e "${BLUE}[安装]${NC} 是否要创建配置文件? [y/N] "
        read -r CREATE_CONFIG
        if [[ "$CREATE_CONFIG" =~ ^[Yy]$ ]]; then
            CONFIG_DIR="$HOME"
            CONFIG_FILE="$CONFIG_DIR/.code_review_config.ini"
            cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
            echo -e "${GREEN}[安装]${NC} 配置文件已创建: $CONFIG_FILE"
            echo -e "${YELLOW}请编辑配置文件并添加您的API密钥${NC}"
        fi
    fi
fi

echo -e "${GREEN}[安装]${NC} 安装完成！"
echo -e "${GREEN}[安装]${NC} 现在每次git commit前都会进行代码评审"
