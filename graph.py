# 图构建（对应教材 7.4.4 核心步骤3，短剧版）
# 组件清单：
#   add_node              → 6个节点
#   add_edge              → 固定边（主流程直线部分）
#   add_conditional_edges → 条件边×3：两次人工审核分支 + 剧本生成的自循环
#   compile(checkpointer=..., interrupt_before=...) → 人机协同中断 + 断点续跑
# 短剧版新增的"图级自循环"：generate_episode 一次只写一集，条件边判断
#   已生成集数 < 总集数 → 回到 generate_episode 继续；否则 → END。
# 好处：每集完成都过一次检查点，90集长跑中断可续、进度可查（get_state 随时看游标）。
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from nodes import (
    get_user_input,
    generate_basic_setting,
    confirm_basic_setting,
    generate_outline,
    confirm_outline,
    generate_episode,
)
from state import NovelCreationState


def build_novel_creation_graph() -> CompiledStateGraph:
    """构建带人工审核中断+逐集自循环的短剧创作工作流"""
    graph = StateGraph(NovelCreationState)

    # 1. 注册节点
    graph.add_node("get_user_input", get_user_input)                   # 需求收集
    graph.add_node("generate_basic_setting", generate_basic_setting)   # 设定生成
    graph.add_node("confirm_basic_setting", confirm_basic_setting)     # 设定审核
    graph.add_node("generate_outline", generate_outline)               # 两级大纲
    graph.add_node("confirm_outline", confirm_outline)                 # 大纲审核
    graph.add_node("generate_episode", generate_episode)               # 单集生成（自循环）

    # 2. 固定边：主流程的直线部分
    graph.set_entry_point("get_user_input")
    graph.add_edge("get_user_input", "generate_basic_setting")
    graph.add_edge("generate_basic_setting", "confirm_basic_setting")
    graph.add_edge("generate_outline", "confirm_outline")

    # 3. 条件边①②：审核通过走下游，不通过打回上游重生成（回环）
    def setting_confirm_router(state: NovelCreationState) -> str:
        return "generate_outline" if state.get("is_setting_confirmed", False) \
            else "generate_basic_setting"

    graph.add_conditional_edges("confirm_basic_setting", setting_confirm_router)

    def outline_confirm_router(state: NovelCreationState) -> str:
        return "generate_episode" if state.get("is_outline_confirmed", False) \
            else "generate_outline"

    graph.add_conditional_edges("confirm_outline", outline_confirm_router)

    # 4. 条件边③：剧本生成的自循环——没写完回自己，写完去 END
    def episode_loop_router(state: NovelCreationState) -> str:
        total = len(state.get("episode_structure") or [])
        done = state.get("episode_generated_count", 0)
        return "generate_episode" if done < total else END

    graph.add_conditional_edges(
        "generate_episode", episode_loop_router, ["generate_episode", END]
    )

    # 5. 编译：挂检查点 + 在两个人工审核节点前中断（人机协同）
    checkpointer = MemorySaver()
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["confirm_basic_setting", "confirm_outline"],
    )
