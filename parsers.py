# LLM 输出解析：设定 / 总纲+幕表 / 分集大纲 三类文本 → 结构化字段
# 容错策略（教材"实践反思-问题1"的加强版）：
#   - 逐行 strip，容忍前后空行/缩进；跳过 ``` 代码块围栏
#   - 多字段行不依赖｜分隔符：按"标记词："出现顺序切片提取，
#     模型吞掉｜（实测高频：剧情：...。爽点：xxx）也能正确拆出
#   - 冒号兼容中英文；项目符号兼容 - * •
import re
from typing import Dict, List

_BULLETS = ("-", "*", "•")


def _clean_lines(text: str) -> List[str]:
    """拆行、去空白、过滤空行和代码块围栏"""
    lines = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line or line.startswith("```"):
            continue
        lines.append(line)
    return lines


def _after_marker(line: str, marker: str) -> str:
    """取 '标记：值' 冒号后的值；兼容英文冒号；没有冒号就取标记后的剩余文本"""
    rest = line[len(marker):].lstrip("：: ").strip()
    return rest


def _strip_bullet(line: str) -> str:
    return line.lstrip("".join(_BULLETS) + " ").strip()


def _parse_labeled_line(body: str, keys: List[str]) -> Dict[str, str]:
    """按标记词出现顺序切片：'集1｜标题：a｜剧情：b。爽点：c｜钩子：d'
    → {标题:a, 剧情:b, 爽点:c, 钩子:d}。不管分隔符是｜还是句号，都能切对。"""
    pattern = re.compile("|".join(f"{k}：" for k in keys))
    matches = list(pattern.finditer(body))
    fields: Dict[str, str] = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        value = body[m.end():end].strip().strip("｜").strip()
        fields[m.group()[:-1]] = value  # m.group() 形如 "标题："，去掉冒号当 key
    return fields


def parse_basic_setting(text: str) -> Dict[str, object]:
    """解析基础设定文本 → {novel_title, main_characters, plot_overview}"""
    result: Dict[str, object] = {
        "novel_title": None,
        "main_characters": [],
        "plot_overview": None,
    }
    plot_lines: List[str] = []
    section = None  # 记录当前小节，用于拼接跨行的情节概述

    for line in _clean_lines(text):
        # 标题行：长标记优先匹配，否则会把"题目："残留在值里
        title = None
        for marker in ("小说题目", "剧名", "备选题目", "题目"):
            if line.startswith(marker):
                title = _after_marker(line, marker) or None
                break
        if title is not None:
            result["novel_title"] = title
            section = None
        elif line.startswith("主要角色"):
            section = "characters"
        elif line.startswith("情节概述"):
            first = _after_marker(line, "情节概述")
            if first:
                plot_lines.append(first)
            section = "plot"
        elif line.startswith(_BULLETS):
            body = _strip_bullet(line)
            if "：" in body or ":" in body:
                name, desc = body.replace(":", "：", 1).split("：", 1)
                result["main_characters"].append({
                    "姓名": name.strip(),
                    "性格描述": desc.strip(),
                })
        elif section == "plot":
            # 情节概述标记行之后、下一个标记之前的普通行，视为续写
            plot_lines.append(line)

    if plot_lines:
        result["plot_overview"] = "\n".join(plot_lines).strip()
    return result


def parse_act_structure(text: str) -> Dict[str, object]:
    """解析总纲+幕表 → {novel_outline, act_structure}"""
    result: Dict[str, object] = {"novel_outline": None, "act_structure": []}
    outline_lines: List[str] = []
    section = None

    for line in _clean_lines(text):
        if line.startswith("整体大纲"):
            first = _after_marker(line, "整体大纲")
            if first:
                outline_lines.append(first)
            section = "outline"
        elif line.startswith("幕结构"):
            section = "acts"
        elif line.startswith(_BULLETS):
            fields = _parse_labeled_line(
                _strip_bullet(line), ["幕名", "集数", "主线", "幕末爽点"]
            )
            if fields:
                result["act_structure"].append({
                    "幕名": fields.get("幕名", "未命名幕"),
                    "集数范围": fields.get("集数", ""),
                    "主线目标": fields.get("主线", ""),
                    "幕末爽点": fields.get("幕末爽点", ""),
                })
        elif section == "outline":
            outline_lines.append(line)

    if outline_lines:
        result["novel_outline"] = "\n".join(outline_lines).strip()
    return result


def parse_episode_beats(text: str) -> List[Dict[str, object]]:
    """解析分集大纲 → [{集数, 标题, 剧情, 爽点, 钩子}]"""
    episodes: List[Dict[str, object]] = []
    for line in _clean_lines(text):
        if not line.startswith(_BULLETS):
            continue
        body = _strip_bullet(line)
        fields = _parse_labeled_line(body, ["标题", "剧情", "爽点", "钩子"])
        if not fields:
            continue
        head = body.split("｜")[0]
        digits = "".join(ch for ch in head if ch.isdigit())
        episodes.append({
            "集数": int(digits) if digits else len(episodes) + 1,
            "标题": fields.get("标题", ""),
            "剧情": fields.get("剧情", ""),
            "爽点": fields.get("爽点", ""),
            "钩子": fields.get("钩子", ""),
        })
    return episodes
