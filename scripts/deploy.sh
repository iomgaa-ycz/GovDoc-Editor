#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# GovDoc Auditor 双环境部署脚本
#
# 用法：
#   bash scripts/deploy.sh --target testing          # 部署前后端 testing
#   bash scripts/deploy.sh --target stable           # 部署前后端 stable
#   bash scripts/deploy.sh --target backend-testing  # 仅后端 testing
#   bash scripts/deploy.sh --target backend-stable   # 仅后端 stable
#   bash scripts/deploy.sh --target frontend-testing # 仅前端 testing
#   bash scripts/deploy.sh --target frontend-stable  # 仅前端 stable
#
# 环境：
#   testing = master 分支，端口 8001/8080，工程师验证
#   stable  = stable 分支，端口 8000/1181，律师正式使用
#
# 服务器：
#   后端: yuchengzhang@100.82.33.121 (4090 Server, Tailscale)
#   前端: ubuntu@100.70.102.30 (律师服务器, Tailscale / 公网 175.178.131.134)
# ─────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")/.."

# ── 配置 ──
BACKEND_HOST="pci@100.82.33.121"
FRONTEND_HOST="ubuntu@100.70.102.30"
FRONTEND_PUBLIC_IP="175.178.131.134"

STABLE_BACKEND_PORT=8000
TESTING_BACKEND_PORT=8001
STABLE_FRONTEND_PORT=1181
TESTING_FRONTEND_PORT=8080

STABLE_DIR="GovDoc-Editor"
TESTING_DIR="GovDoc-Editor-testing"
STABLE_BRANCH="stable"
TESTING_BRANCH="master"

# 后端服务器代理（仅在代理可用时设置，否则跳过）
PROXY_ENV='if curl -sf --connect-timeout 1 http://127.0.0.1:7890 >/dev/null 2>&1; then export http_proxy=http://127.0.0.1:7890 https_proxy=http://127.0.0.1:7890; fi; export no_proxy=110.42.53.85,100.81.95.44,localhost,127.0.0.1 NO_PROXY=110.42.53.85,100.81.95.44,localhost,127.0.0.1'
CONDA_INIT='eval "$($HOME/miniconda3/bin/conda shell.bash hook)" && conda activate govdoc-auditor-v3'

# ── 参数解析 ──
TARGET=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --target) TARGET="$2"; shift 2 ;;
        *) echo "未知参数: $1"; echo "用法: bash scripts/deploy.sh --target <testing|stable|backend-testing|backend-stable|frontend-testing|frontend-stable>"; exit 1 ;;
    esac
done

[ -z "$TARGET" ] && { echo "错误: 请指定 --target"; exit 1; }

LOG_DIR="results/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/deploy_${TARGET}_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# ── 后端部署函数 ──
deploy_backend() {
    local env="$1"    # testing or stable
    local dir port branch tmux_name
    if [ "$env" = "testing" ]; then
        dir="$TESTING_DIR"; port="$TESTING_BACKEND_PORT"; branch="$TESTING_BRANCH"; tmux_name="govdoc-testing"
    else
        dir="$STABLE_DIR"; port="$STABLE_BACKEND_PORT"; branch="$STABLE_BRANCH"; tmux_name="govdoc-stable"
    fi

    log ">>> 后端 $env: 开始部署 (4090:$port, 分支 $branch)"

    # 1. Git 拉取
    log "  [1/6] git pull ($branch)..."
    ssh "$BACKEND_HOST" "
        ${PROXY_ENV} && \
        cd ~/Project/${dir} && \
        git fetch origin && \
        git checkout ${branch} && \
        git reset --hard origin/${branch}
    " >> "$LOG_FILE" 2>&1
    log "  ✓ 代码已同步"

    # 2. 同步 .env
    log "  [2/6] 同步 .env..."
    scp .env "${BACKEND_HOST}:~/Project/${dir}/.env" >> "$LOG_FILE" 2>&1
    log "  ✓ .env 已同步"

    # 3. 安装依赖
    log "  [3/6] pip install..."
    ssh "$BACKEND_HOST" "
        ${PROXY_ENV} && \
        ${CONDA_INIT} && \
        cd ~/Project/${dir} && pip install -e . --quiet
    " >> "$LOG_FILE" 2>&1
    log "  ✓ 依赖已安装"

    # 4. 数据库迁移
    log "  [4/6] alembic upgrade..."
    ssh "$BACKEND_HOST" "
        ${CONDA_INIT} && \
        cd ~/Project/${dir} && alembic upgrade head
    " >> "$LOG_FILE" 2>&1
    log "  ✓ 数据库已迁移"

    # 5. 重启 uvicorn
    log "  [5/7] 停止旧进程..."
    ssh "$BACKEND_HOST" "
        tmux kill-session -t ${tmux_name} 2>/dev/null || true
    " >> "$LOG_FILE" 2>&1

    # 等待端口释放
    log "  [6/7] 等待端口 ${port} 释放..."
    local port_free=false
    for i in $(seq 1 15); do
        if ! ssh "$BACKEND_HOST" "ss -tlnp | grep -q ':${port} '" 2>/dev/null; then
            port_free=true; break
        fi
        sleep 2
    done
    if [ "$port_free" != true ]; then
        log "  ⚠ 端口 ${port} 未释放，强制杀占用进程..."
        ssh "$BACKEND_HOST" "fuser -k ${port}/tcp 2>/dev/null || true" >> "$LOG_FILE" 2>&1
        sleep 3
    fi

    # 启动新进程（日志写文件，方便排查）
    local log_path="~/Project/${dir}/logs/uvicorn.log"
    ssh "$BACKEND_HOST" "mkdir -p ~/Project/${dir}/logs" >> "$LOG_FILE" 2>&1
    ssh "$BACKEND_HOST" "
        tmux new-session -d -s ${tmux_name} \"
            eval \\\"\\\$(\\\$HOME/miniconda3/bin/conda shell.bash hook)\\\" && conda activate govdoc-auditor-v3 && \
            export no_proxy=110.42.53.85,100.81.95.44,localhost,127.0.0.1 && export NO_PROXY=\\\$no_proxy && \
            export CUDA_VISIBLE_DEVICES=0 && \
            cd ~/Project/${dir} && \
            uvicorn govdoc.api.main:app --host 0.0.0.0 --port ${port} 2>&1 | tee ${log_path}; \
            echo === ${tmux_name} STOPPED ===; sleep 86400
        \"
    " >> "$LOG_FILE" 2>&1
    log "  ✓ uvicorn 已启动 (tmux: ${tmux_name}, 日志: ${log_path})"

    # 7. 健康检查（等待更久，mineru 首次加载模型较慢）
    log "  [7/7] 等待健康检查（最长 120s）..."
    local ok=false
    for i in $(seq 1 60); do
        if ssh "$BACKEND_HOST" "curl -sf http://localhost:${port}/healthz" > /dev/null 2>&1; then
            ok=true; break
        fi
        sleep 2
    done
    if [ "$ok" = true ]; then
        log "  ✓ 后端 $env 健康检查通过 (http://100.82.33.121:${port})"
    else
        log "  ✗ 后端 $env 健康检查失败！最近日志："
        ssh "$BACKEND_HOST" "tail -20 ~/Project/${dir}/logs/uvicorn.log 2>/dev/null" 2>&1 | tee -a "$LOG_FILE"
        ssh "$BACKEND_HOST" "tmux capture-pane -t ${tmux_name} -p | tail -10" 2>&1 | tee -a "$LOG_FILE"
        return 1
    fi
}

# ── 前端部署函数 ──
deploy_frontend() {
    local env="$1"    # testing or stable
    local port dist_dir
    if [ "$env" = "testing" ]; then
        port="$TESTING_FRONTEND_PORT"; dist_dir="testing"
    else
        port="$STABLE_FRONTEND_PORT"; dist_dir="stable"
    fi

    log ">>> 前端 $env: 开始部署 (nginx:$port)"

    # 1. 本地构建
    log "  [1/3] npm run build..."
    (cd frontend && npm run build) >> "$LOG_FILE" 2>&1
    log "  ✓ 前端构建完成"

    # 2. rsync 到律师服务器
    log "  [2/3] rsync dist/..."
    rsync -avz --delete frontend/dist/ "${FRONTEND_HOST}:~/govdoc/${dist_dir}/dist/" >> "$LOG_FILE" 2>&1
    log "  ✓ 文件已同步到律师服务器"

    # 3. 验证
    log "  [3/3] 验证页面..."
    local status
    status=$(ssh "$FRONTEND_HOST" "curl -s -o /dev/null -w '%{http_code}' http://localhost:${port}/" 2>/dev/null)
    if [ "$status" = "200" ]; then
        log "  ✓ 前端 $env 验证通过 (http://${FRONTEND_PUBLIC_IP}:${port})"
    else
        log "  ✗ 前端 $env 验证失败 (HTTP ${status})"
        return 1
    fi
}

# ── 执行 ──
echo "=========================================" | tee "$LOG_FILE"
log "GovDoc 部署: ${TARGET}"
log "开始时间: $(date)"
echo "=========================================" | tee -a "$LOG_FILE"

case "$TARGET" in
    backend-testing)  deploy_backend testing ;;
    backend-stable)   deploy_backend stable ;;
    frontend-testing) deploy_frontend testing ;;
    frontend-stable)  deploy_frontend stable ;;
    testing)          deploy_backend testing && deploy_frontend testing ;;
    stable)           deploy_backend stable && deploy_frontend stable ;;
    *)
        log "错误: 无效的 target '${TARGET}'"
        log "可选: testing | stable | backend-testing | backend-stable | frontend-testing | frontend-stable"
        exit 1
        ;;
esac

echo "" | tee -a "$LOG_FILE"
echo "=========================================" | tee -a "$LOG_FILE"
log "✓ 部署完成"
log "日志: $LOG_FILE"
echo "=========================================" | tee -a "$LOG_FILE"
