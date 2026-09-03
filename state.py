# LangGraph 状态定义（对应教材 7.4.2 核心步骤1，已短剧化）
# State 是整个智能体的"数据载体"，节点间所有数据传递都走这里。
from typing import Dict, List, Optional, TypedDict

from typing_extensions import NotRequired


class NovelCreationState(TypedDict):
    """短剧创作全流程状态管理（含进度追踪）"""

    # ---- 初始输入（必填）----
    user_requirement: str  # 用户的短剧创作需求

    # ---- 基础设定（节点2 生成后填充）----
    novel_title: NotRequired[Optional[str]]                       # 剧名
    main_characters: NotRequired[Optional[List[Dict[str, str]]]]  # [{姓名, 性格描述}]
    plot_overview: NotRequired[Optional[str]]                     # 核心冲突与主线概述

    # ---- 人工审核结果（条件分支依据）----
    is_setting_confirmed: NotRequired[bool]  # 基础设定是否确认
    is_outline_confirmed: NotRequired[bool]  # 总纲+分集大纲是否确认

    # ---- 大纲（节点4 生成后填充，两级结构）----
    novel_outline: NotRequired[Optional[str]]                       # 全剧总纲
    act_structure: NotRequired[Optional[List[Dict[str, str]]]]      # 幕结构 [{幕名, 集数范围, 主线目标, 幕末爽点}]
    episode_structure: NotRequired[Optional[List[Dict[str, str]]]]  # 分集大纲 [{集数, 标题, 剧情, 爽点, 钩子}]×90

    # ---- 正文（节点6 每集追加一条，图级自循环逐集写入检查点）----
    script_parts: NotRequired[List[str]]  # 每集剧本正文，顺序即集数

    # ---- 进度追踪（贯穿全程的可观测字段）----
    current_stage: NotRequired[str]            # 需求收集/设定生成/大纲生成/剧本生成
    episode_generated_count: NotRequired[int]  # 已生成集数
