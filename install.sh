#!/bin/bash
# 安装脚本 - 设置Git代码评审钩子

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认目标目录
DEFAULT_TARGET="$PWD"

# 解析参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --target-dir)
            PROJECT_ROOT="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}错误: 未知参数: $1${NC}" >&2
            exit 1
            ;;
    esac
done

# 如果没有指定目标目录，使用默认值
if [ -z "$PROJECT_ROOT" ]; then
    PROJECT_ROOT="$DEFAULT_TARGET"
fi

echo -e "${BLUE}[安装]${NC} 开始安装Git代码评审钩子到: $PROJECT_ROOT"

# 检查目标目录是否为Git仓库
if [ ! -d "$PROJECT_ROOT/.git" ]; then
    echo -e "${RED}错误: 目标目录不是Git仓库: $PROJECT_ROOT${NC}" >&2
    exit 1
fi
# 钩子源文件和目标文件
HOOK_SOURCE="$PWD/hooks/commit-msg"
HOOK_TARGET="${PROJECT_ROOT}/.git/hooks/commit-msg"

# 检查钩子源文件是否存在
if [ ! -f "$HOOK_SOURCE" ]; then
    echo -e "${RED}错误: 未找到钩子源文件: ${HOOK_SOURCE}${NC}" >&2
    echo -e "${YELLOW}提示: 请确保hooks/commit-msg文件与install.sh在同一目录${NC}"
    exit 1
fi

# 检查钩子源文件是否可执行
if [ ! -x "$HOOK_SOURCE" ]; then
    echo -e "${YELLOW}警告: 钩子源文件不可执行，正在添加执行权限...${NC}"
    chmod +x "$HOOK_SOURCE"
fi

# 检查评审脚本是否存在并可执行
REVIEW_SCRIPT="$PWD/code_review.py"
if [ ! -f "$REVIEW_SCRIPT" ]; then
    echo -e "${RED}错误: 未找到代码评审脚本: ${REVIEW_SCRIPT}${NC}" >&2
    echo -e "${YELLOW}提示: 请确保code_review.py文件与install.sh在同一目录${NC}"
    exit 1
fi
if [ ! -x "$REVIEW_SCRIPT" ]; then
    echo -e "${YELLOW}警告: 代码评审脚本不可执行，正在添加执行权限...${NC}"
    chmod +x "$REVIEW_SCRIPT"
fi

# 安装Python依赖
echo -e "${BLUE}[安装]${NC} 正在安装Python依赖..."
if ! pip install -r "${DEFAULT_TARGET}/requirements.txt"; then
    echo -e "${YELLOW}警告: 安装Python依赖失败，请手动安装${NC}"
    echo -e "${YELLOW}运行: pip install -r ${DEFAULT_TARGET}/requirements.txt${NC}"
fi

# 创建钩子目录（如果不存在）
mkdir -p "$(dirname "$HOOK_TARGET")"

# 备份现有钩子（如果存在）
if [ -f "$HOOK_TARGET" ]; then
    BACKUP_FILE="${HOOK_TARGET}.backup.$(date +%Y%m%d%H%M%S)"
    echo -e "${YELLOW}警告: 已存在commit-msg钩子，正在备份到 ${BACKUP_FILE}${NC}"
    mv "$HOOK_TARGET" "$BACKUP_FILE"
fi

# 创建符号链接
echo -e "${BLUE}[安装]${NC} 正在安装commit-msg钩子..."
ln -sf "$HOOK_SOURCE" "$HOOK_TARGET"

# 检查OpenAI API密钥是否设置
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${YELLOW}警告: 未设置OPENAI_API_KEY环境变量${NC}"
    echo -e "${YELLOW}您可以通过以下方式提供API密钥:${NC}"
    echo -e "${YELLOW}  1. 设置环境变量: export OPENAI_API_KEY='your-api-key'${NC}"
    echo -e "${YELLOW}  2. 创建配置文件: ~/.code_review_config.ini${NC}"
    echo -e "${YELLOW}     配置文件示例可在 ${DEFAULT_TARGET}/config_example.ini 中找到${NC}"
    
    # 复制配置示例文件
    CONFIG_EXAMPLE="${DEFAULT_TARGET}/config_example.ini"
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
echo -e "${GREEN}[安装]${NC} 评审脚本位置: $PWD/code_review.py"
echo -e "${GREEN}[安装]${NC} 钩子安装位置: ${PROJECT_ROOT}/.git/hooks/commit-msg"
echo -e "${GREEN}[安装]${NC} 现在每次git commit前都会进行代码评审"
