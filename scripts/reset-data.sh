#!/bin/sh
# 重置数据：清空 private-data/bilibili-tag-group/ 下的所有业务数据文件，
# 让项目回到初始状态（类似数据库 truncate）。
#
# 删除范围：
#   - 7 个业务数据 JSON（creators / tags / creator_tags / videos /
#     video_statuses / sync_tasks / tag_sync_configs）
#   - 所有 *.bak-* 备份文件
#   - 所有 *.lock 锁文件
#   - .DS_Store
# 保留：cookies.json（B 站登录态，删了要重新登录；如需清理手动 rm 即可）
#
# 运行前请先执行 stop.sh 停止服务，避免后端写盘与清理冲突。
# 数据目录由 app/config.py 的 DEFAULT_DATA_DIR 决定，默认 ../private-data/bilibili-tag-group。

set -e

cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)
DATA_DIR="$PROJECT_ROOT/../private-data/bilibili-tag-group"

if [ ! -d "$DATA_DIR" ]; then
    echo "[ERROR] 数据目录不存在: $DATA_DIR"
    exit 1
fi
DATA_DIR=$(cd "$DATA_DIR" && pwd)

echo "即将清空数据目录: $DATA_DIR"
echo
echo "将删除："
echo "  - 7 个业务数据 JSON（creators / tags / creator_tags / videos /"
echo "    video_statuses / sync_tasks / tag_sync_configs）"
echo "  - 所有 *.bak-* 备份"
echo "  - 所有 *.lock 锁文件"
echo "  - .DS_Store"
echo "保留：cookies.json（B 站登录态）"
echo
printf "确认继续？[y/N] "
read -r answer
case "$answer" in
    y|Y|yes|YES) ;;
    *) echo "已取消"; exit 0 ;;
esac

echo
for f in creators.json tags.json creator_tags.json videos.json video_statuses.json sync_tasks.json tag_sync_configs.json; do
    if [ -f "$DATA_DIR/$f" ]; then
        rm -f "$DATA_DIR/$f"
        echo "已删除 $f"
    fi
done

# 备份 / 锁文件 / .DS_Store（无匹配时 rm -f 忽略）
rm -f "$DATA_DIR"/*.bak-* "$DATA_DIR"/*.lock "$DATA_DIR"/.DS_Store 2>/dev/null || true
echo "已清理 *.bak-* / *.lock / .DS_Store"

echo
echo
echo "完成。数据已清空，API 将返回空列表；"
echo "数据文件在首次写入时由 JsonRepo 重建。"
