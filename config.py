# 模型与环境配置：统一收口，节点代码不直接碰 os.getenv
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_PROJECT_DIR)

# .env 在上级目录（langgraph学习/.env），显式加载优先；
# 再 load_dotenv() 兜底搜一遍当前工作目录向上（默认不覆盖已加载的值）
load_dotenv(os.path.join(_PARENT_DIR, ".env"))
load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
CHAT_MODEL = os.getenv("MODEL", "qwen3.6-flash")

if not API_KEY:
    raise ValueError("未检测到 API_KEY，请在 langgraph学习/.env 中配置")

# ---- 短剧产能参数（都可用环境变量覆盖，方便小规模试跑）----
# 总集数：一集2-3分钟，全剧90集
TOTAL_EPISODES = int(os.getenv("TOTAL_EPISODES", "90"))
# 每幕集数：90集拆成6幕，幕是排爽点节奏的单位（3集一小爽、幕末一大爽）
EPISODES_PER_ACT = int(os.getenv("EPISODES_PER_ACT", "15"))
# 分集大纲每块行数：一次让模型排太多行会漏行（实测要3行只给1行），分小块生成
EPISODE_BEATS_CHUNK = int(os.getenv("EPISODE_BEATS_CHUNK", "5"))
# 单集字数：竖屏短剧 1分钟≈300字台本，2-3分钟对应700-900字
WORDS_PER_EPISODE = os.getenv("WORDS_PER_EPISODE", "700-900")

# 两套模型实例，对应两类任务：
# - llm_structured：设定/总纲/分集大纲，要求严格按格式输出（解析靠逐行匹配）→ 低温度
# - llm_creative   ：单集剧本正文，要冲突张力和台词情绪 → 高温度
_LLM_COMMON = dict(
    api_key=API_KEY,
    base_url=BASE_URL,
    model=CHAT_MODEL,
    # qwen3 系列关键参数：不关思考模式，思考 token 会计入 max_tokens，
    # 实测会出现 content 为空、finish_reason=length（本机踩过的坑）
    extra_body={"enable_thinking": False},
    timeout=120,
    max_retries=2,
)

llm_structured = ChatOpenAI(temperature=0.3, max_tokens=3000, **_LLM_COMMON)
llm_creative = ChatOpenAI(temperature=0.7, max_tokens=2000, **_LLM_COMMON)

# 剧本成品的保存目录（独立于运行时 cwd，放哪儿运行都不迷路）
OUTPUT_DIR = os.path.join(_PROJECT_DIR, "output")
