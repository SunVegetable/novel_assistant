# 节点定义（对应教材 7.4.3，短剧版）
# LangGraph 的节点 = "状态进、状态出"的执行单元，每个节点只干一件事。
# 短剧版的关键变化：
#   - generate_outline：两级大纲（总纲+幕表 → 逐幕生成分集大纲），爽点/钩子在此逐集排定
#   - generate_episode：每次调用只生成"一集"，靠图级自循环跑满全部集数——
#     每集生成完就写检查点，90集跑到一半中断可从断点续（教材未演示的循环图模式）
import math

from config import (
    llm_structured,
    llm_creative,
    TOTAL_EPISODES,
    EPISODES_PER_ACT,
    EPISODE_BEATS_CHUNK,
    WORDS_PER_EPISODE,
)
from parsers import parse_basic_setting, parse_act_structure, parse_episode_beats
from prompts import (
    BASIC_SETTING_PROMPT,
    MODIFY_SETTING_PROMPT,
    ACT_OUTLINE_PROMPT,
    EPISODE_BEATS_PROMPT,
    EPISODE_SCRIPT_PROMPT,
)
from state import NovelCreationState
from utils import (
    print_process_progress,
    print_episode_progress,
    print_basic_setting,
    print_outline,
)


# ==================== 节点1：需求收集（流程入口） ====================
def get_user_input(state: NovelCreationState) -> NovelCreationState:
    """接收用户输入的创作需求（题材/人设/爽点偏好）"""
    print_process_progress("需求收集", "（开始）")
    user_input = input(
        "请输入你的短剧创作需求"
        "（示例：都市逆袭，外卖小哥是隐藏身份的集团继承人，被看不起后一路打脸，要有情感线和终极反转）："
    )
    state["user_requirement"] = user_input
    state["current_stage"] = "需求收集"
    state["is_setting_confirmed"] = False  # 审核标记初始化，条件分支依赖它
    state["is_outline_confirmed"] = False
    print_process_progress("需求收集", "（完成）✅")
    return state


# ==================== 节点2：生成基础设定 ====================
def generate_basic_setting(state: NovelCreationState) -> NovelCreationState:
    """根据用户需求生成短剧基础设定（剧名/角色/核心冲突）"""
    print_process_progress("设定生成", "（开始生成剧名/角色/情节）")

    response = llm_structured.invoke(
        BASIC_SETTING_PROMPT.format(user_requirement=state["user_requirement"])
    )
    setting = parse_basic_setting(response.content)
    # 解析结果整体合并进状态（解析失败的字段是 None/[]，展示层会提示）
    state.update(setting)

    print_basic_setting(state["novel_title"], state["main_characters"], state["plot_overview"])

    state["current_stage"] = "设定生成"
    print_process_progress("设定生成", "（完成）✅")
    return state


# ==================== 节点3：人工审核基础设定 ====================
def confirm_basic_setting(state: NovelCreationState) -> NovelCreationState:
    """人工审核确认基础设定：通过→置位标记；不通过→按修改意见重生成并二次确认"""
    print("\n===== ⚠️ 人工审核 - 基础设定确认环节 =====")
    confirm = input("是否确认以上基础设定？（确认请输入y，需修改请输入n并说明修改内容）：")

    if confirm.lower() == "y":
        state["is_setting_confirmed"] = True
        print("✅ 基础设定已确认，进入下一阶段！")
        return state

    modify_content = input("请输入你的修改需求（如：修改角色名/调整核心冲突/换剧名）：")
    print("🔄 正在根据你的需求修改基础设定...")
    response = llm_structured.invoke(
        MODIFY_SETTING_PROMPT.format(
            user_requirement=state["user_requirement"],
            modify_content=modify_content,
        )
    )
    state.update(parse_basic_setting(response.content))

    print("\n===== 修改后的基础设定 =====")
    print_basic_setting(state["novel_title"], state["main_characters"], state["plot_overview"])

    re_confirm = input("是否确认修改后的设定？（y/n）：")
    if re_confirm.lower() == "y":
        state["is_setting_confirmed"] = True
        print("✅ 基础设定已确认！")
    else:
        # 标记保持 False，条件边会把流程送回 generate_basic_setting 从头再生
        print("❌ 未确认，将重新生成基础设定。")
    return state


# ==================== 节点4：生成总纲+幕表+分集大纲（两级） ====================
def _characters_text(state: NovelCreationState) -> str:
    """把角色列表拼成提示词用的多行文本"""
    return "\n".join(f"- {c['姓名']}：{c['性格描述']}" for c in state["main_characters"])


def _generate_episode_structure(state: NovelCreationState) -> int:
    """大纲第二步：逐幕分块生成分集大纲，写入 state['episode_structure']，返回总集数。
    分块 + 短块重试：一次让模型排一整幕（15行）实测会漏行，改成每次排一小段。"""
    episodes = []
    for i, act in enumerate(state["act_structure"]):
        act_start = i * EPISODES_PER_ACT + 1
        act_end = min(TOTAL_EPISODES, act_start + EPISODES_PER_ACT - 1)
        print(f"  ▶ {act['幕名']}（第{act_start}-{act_end}集）：{act['主线目标']}")

        pos = act_start
        while pos <= act_end:
            chunk_end = min(pos + EPISODE_BEATS_CHUNK - 1, act_end)
            expected = chunk_end - pos + 1
            beats = []
            for attempt in (1, 2):
                resp = llm_structured.invoke(
                    EPISODE_BEATS_PROMPT.format(
                        novel_title=state["novel_title"],
                        main_characters=_characters_text(state),
                        novel_outline=state["novel_outline"],
                        act_name=act["幕名"],
                        act_goal=act["主线目标"],
                        act_climax=act["幕末爽点"],
                        start_episode=pos,
                        end_episode=chunk_end,
                        episode_count=expected,
                    )
                )
                beats = parse_episode_beats(resp.content)
                if len(beats) >= expected:
                    break
                print(f"    ⚠️ 需要{expected}行只解析到{len(beats)}行，重试...")
            if len(beats) < expected:
                print(f"    ⚠️ 该段仍缺行（{len(beats)}/{expected}），总集数会少于计划，审核时请注意")
            # 重编号防模型数错集数：以段内顺序为准
            for j, beat in enumerate(beats):
                beat["集数"] = pos + j
            episodes.extend(beats)
            pos = chunk_end + 1

    state["episode_structure"] = episodes
    return len(episodes)


def generate_outline(state: NovelCreationState) -> NovelCreationState:
    """两级大纲：第一步总纲+幕表；第二步逐幕生成分集大纲（每集排定爽点+钩子）"""
    if not state.get("is_setting_confirmed", False):
        raise ValueError("❌ 基础设定未确认，无法生成大纲！")

    print_process_progress("大纲生成", f"（总纲+分幕，全剧{TOTAL_EPISODES}集）")

    # ---- 第一步：总纲 + 幕表 ----
    act_count = math.ceil(TOTAL_EPISODES / EPISODES_PER_ACT)
    response = llm_structured.invoke(
        ACT_OUTLINE_PROMPT.format(
            novel_title=state["novel_title"],
            main_characters=_characters_text(state),
            plot_overview=state["plot_overview"],
            total_episodes=TOTAL_EPISODES,
            act_count=act_count,
            episodes_per_act=EPISODES_PER_ACT,
            next_act_start=EPISODES_PER_ACT + 1,               # 示例行里的第二幕起止
            next_act_end=min(EPISODES_PER_ACT * 2, TOTAL_EPISODES),
        )
    )
    state.update(parse_act_structure(response.content))
    if not state["act_structure"]:
        raise ValueError("❌ 幕表解析失败（模型输出格式偏离），可重新运行")

    # ---- 第二步：逐幕分块生成分集大纲 ----
    print(f"  幕表已生成（{len(state['act_structure'])}幕），开始逐幕排分集大纲+爽点...")
    total = _generate_episode_structure(state)

    state["current_stage"] = "大纲生成"
    print_outline(state["novel_outline"], state["act_structure"], state["episode_structure"])
    print_process_progress("大纲生成", f"（完成，共{total}集✅）")
    return state


# ==================== 节点5：人工审核大纲与分集爽点 ====================
def confirm_outline(state: NovelCreationState) -> NovelCreationState:
    """人工审核总纲/幕表/分集大纲：通过→置位标记；不通过→按修改意见重生成并二次确认"""
    print("\n===== ⚠️ 人工审核 - 总纲与分集大纲确认环节 =====")
    total = len(state.get("episode_structure") or [])
    confirm = input(
        f"是否确认以上大纲（共{total}集，每集已排定爽点+钩子）？"
        f"（确认请输入y，需修改请输入n并说明修改内容）："
    )

    if confirm.lower() == "y":
        state["is_outline_confirmed"] = True
        print(f"✅ 大纲已确认！确认后将连续生成{total}集剧本（每集约{WORDS_PER_EPISODE}字）")
        return state

    modify_content = input("请输入你的修改需求（如：换爽点类型/调整某幕主线/增删情节线）：")
    print("🔄 正在根据你的需求修改大纲（会重排全部分集爽点）...")
    # 修改走整体重生成：两级流程同节点4，保证幕与分集的一致性
    act_count = math.ceil(TOTAL_EPISODES / EPISODES_PER_ACT)
    response = llm_structured.invoke(
        ACT_OUTLINE_PROMPT.format(
            novel_title=state["novel_title"],
            main_characters=_characters_text(state),
            plot_overview=state["plot_overview"] + f"\n（用户修改需求：{modify_content}）",
            total_episodes=TOTAL_EPISODES,
            act_count=act_count,
            episodes_per_act=EPISODES_PER_ACT,
            next_act_start=EPISODES_PER_ACT + 1,
            next_act_end=min(EPISODES_PER_ACT * 2, TOTAL_EPISODES),
        )
    )
    state.update(parse_act_structure(response.content))
    _generate_episode_structure(state)

    print("\n===== 修改后的总纲与分集大纲 =====")
    print_outline(state["novel_outline"], state["act_structure"], state["episode_structure"])

    re_confirm = input("是否确认修改后的大纲？（y/n）：")
    if re_confirm.lower() == "y":
        state["is_outline_confirmed"] = True
        print("✅ 大纲已确认！")
    else:
        print("❌ 未确认，将重新生成大纲。")
    return state


# ==================== 节点6：逐集生成剧本（图级自循环，一次一集） ====================
def generate_episode(state: NovelCreationState) -> NovelCreationState:
    """生成"下一集"剧本：每次调用只生成一集，由条件边自循环驱动跑完全部集数。
    每集完成即写检查点——跑到第N集中断，恢复后从第N+1集继续，不重复花钱。"""
    if not state.get("is_outline_confirmed", False):
        raise ValueError("❌ 大纲未确认，无法生成剧本！")

    structure = state["episode_structure"]
    total = len(structure)
    idx = state.get("episode_generated_count", 0)  # 已生成集数（0-based 游标）

    if idx == 0:
        print_process_progress("剧本生成", f"（开始逐集生成，共{total}集）")
        state["script_parts"] = []
    print_episode_progress(idx, total)

    ep = structure[idx]
    prev = structure[idx - 1] if idx > 0 else None
    response = llm_creative.invoke(
        EPISODE_SCRIPT_PROMPT.format(
            episode_num=idx + 1,
            total_episodes=total,
            novel_title=state["novel_title"],
            main_characters=_characters_text(state),
            novel_outline=state["novel_outline"],
            prev_hook=prev["钩子"] if prev else "（本集是第一集，开场直接立冲突）",
            prev_plot=prev["剧情"] if prev else "无",
            episode_title=ep["标题"],
            episode_plot=ep["剧情"],
            episode_payoff=ep["爽点"],
            episode_hook=ep["钩子"],
            words_per_episode=WORDS_PER_EPISODE,
        )
    )
    content = response.content.strip()
    state["script_parts"] = state.get("script_parts", []) + [content]
    state["episode_generated_count"] = idx + 1
    state["current_stage"] = "剧本生成"

    # 紧凑进度行（90集不再整段刷屏，完整正文进成品文件）
    print(f"✅ 第{idx + 1}/{total}集《{ep['标题']}》完成｜爽点：{ep['爽点'][:40]}")
    if state["episode_generated_count"] >= total:
        print_process_progress("剧本生成", f"（完成，共{total}集✅）")
    return state
