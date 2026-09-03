# 展示类工具：整体进度、集数进度、设定/大纲的格式化打印
from typing import Dict, List


def print_process_progress(current_stage: str, detail: str = "") -> None:
    """打印整体流程进度，让用户直观了解当前执行阶段"""
    stage_map = {
        "需求收集": "1/4",
        "设定生成": "2/4",
        "大纲生成": "3/4",
        "剧本生成": "4/4",
    }
    progress = stage_map.get(current_stage, "未知阶段")
    print(f"\n🔄 【整体进度 {progress}】- {current_stage} {detail}")


def print_episode_progress(generated: int, total: int) -> None:
    """打印剧本生成进度（百分比）"""
    percentage = (generated / total) * 100 if total > 0 else 0
    print(f"\n📖 【集数进度】已完成 {generated}/{total} 集 ({percentage:.1f}%)")


def print_basic_setting(
    novel_title, main_characters: List[Dict[str, str]], plot_overview
) -> None:
    """展示短剧基础设定（生成后/修改后共用）"""
    print("\n===== 短剧基础设定 =====")
    print(f"剧名：{novel_title or '（未解析到，可输入 n 重新生成）'}")
    print("主要角色：")
    for char in main_characters or []:
        print(f"- {char['姓名']}：{char['性格描述']}")
    print(f"情节概述：{plot_overview or '（未解析到）'}")


def print_outline(
    novel_outline,
    act_structure: List[Dict[str, str]],
    episode_structure: List[Dict[str, str]],
) -> None:
    """展示总纲/幕表/分集大纲（生成后/修改后共用）。
    分集大纲每集一行紧凑展示——审核的就是爽点/钩子排布，必须全量可见。"""
    print("\n===== 全剧总纲 =====")
    print(novel_outline or "（未解析到）")
    print("\n===== 分幕结构 =====")
    for act in act_structure or []:
        print(f"- {act['幕名']}（{act['集数范围']}）：{act['主线目标']}｜幕末爽点：{act['幕末爽点']}")
    print(f"\n===== 分集大纲（共{len(episode_structure or [])}集）=====")
    for ep in episode_structure or []:
        print(f"- 集{ep['集数']}《{ep['标题']}》爽点：{ep['爽点']}｜钩子：{ep['钩子']}")
