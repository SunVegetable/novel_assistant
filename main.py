# 运行入口（对应教材 7.4.5 案例的运行部分，短剧版）
# 核心是"中断-恢复"循环：
#   invoke(initial_state) → 跑到第一个 interrupt_before 停住返回
#   循环检查 get_state(config).next → 还有待执行节点 = 处于中断 → invoke(None) 恢复
#   next 为空 = 流程走完
# 剧本自循环不设中断，90集一口气跑完；中途 Ctrl-C 的话同 thread 重跑可从断点续。
import os
import time

from config import OUTPUT_DIR
from graph import build_novel_creation_graph

if __name__ == "__main__":
    novel_graph = build_novel_creation_graph()

    # thread_id 用于区分不同的创作流程，每个线程在 checkpointer 里状态独立
    config = {"configurable": {"thread_id": "novel_creation_001"}}
    initial_state = {
        "user_requirement": "",
        "current_stage": "初始",
        "episode_generated_count": 0,
    }

    print("🚀 短剧创作助手启动")
    print("==============================================")

    # 第一段：从入口跑到第一个中断点（confirm_basic_setting 之前）
    novel_graph.invoke(initial_state, config=config)

    # 中断-恢复循环：所有人工审核环节都在这里被接管
    while True:
        state_snapshot = novel_graph.get_state(config)
        if not state_snapshot.next:
            print("\n🎉 所有流程已完成！")
            break

        target_node = state_snapshot.next[0]
        print(f"\n--- ⏸️ 流程在节点 [{target_node}] 处等待人工干预 ---")
        # 传 None：从上一个检查点继续，触发审核节点里的 input() 交互
        novel_graph.invoke(None, config=config)

    # 收结果：从 checkpointer 取最终状态，组装成品文件
    # （正文渲染放主入口：节点只产出数据，文件拼装是展示层职责）
    final_state = novel_graph.get_state(config).values
    parts = final_state.get("script_parts") or []
    if parts:
        acts = final_state.get("act_structure") or []
        episodes = final_state.get("episode_structure") or []
        characters = "\n".join(
            f"- {c['姓名']}：{c['性格描述']}" for c in final_state.get("main_characters") or []
        )
        content = (
            f"# {final_state.get('novel_title', '未命名短剧')}\n\n"
            f"## 核心设定\n剧名：{final_state.get('novel_title')}\n"
            f"主要角色：\n{characters}\n"
            f"情节概述：{final_state.get('plot_overview')}\n\n"
            f"## 全剧总纲\n{final_state.get('novel_outline')}\n\n"
            "## 分幕结构\n"
            + "\n".join(
                f"- {a['幕名']}（{a['集数范围']}）：{a['主线目标']}｜幕末爽点：{a['幕末爽点']}"
                for a in acts
            )
            + "\n\n## 分集大纲（每集爽点+钩子）\n"
            + "\n".join(
                f"- 集{e['集数']}《{e['标题']}》爽点：{e['爽点']}｜钩子：{e['钩子']}"
                for e in episodes
            )
            + "\n\n---\n\n"
            + "\n\n---\n\n".join(parts)
            + f"\n\n### 全剧完本（总集数：{len(parts)} | 创作基于用户需求：{final_state.get('user_requirement')}）\n"
        )
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        filename = os.path.join(OUTPUT_DIR, time.strftime("script_%Y%m%d_%H%M%S.md"))
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        total_chars = sum(len(p) for p in parts)
        print(f"\n📁 完整剧本已保存到: {filename}")
        print(f"📊 共{len(parts)}集，正文总字数约{total_chars}")
    else:
        print("\n⚠️ 流程未能生成完整内容。")
