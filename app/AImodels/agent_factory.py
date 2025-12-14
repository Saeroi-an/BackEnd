# app/AImodels/agent_factory.py
import os
import logging
from supabase import Client

# LangChain 최신 버전(1.x)에서는 기존의 에이전트 구현(AgentExecutor, ReAct agent 등)이
# 'langchain' 본 패키지에서 분리되어 'langchain-classic' 패키지로 이동한 경우가 많음.
# 기존 코드(레거시 ReAct 에이전트)를 유지하려면 classic에서 가져오는 게 안정적.
from langchain_classic.agents import AgentExecutor
# ↑ AgentExecutor: "Agent(추론 로직) + Tools(도구)"를 묶어서 실행(invoke)할 수 있게 해주는 실행기
try:
    from langchain_classic.agents import create_react_agent
except ImportError:
    # 버전/배포 형태에 따라 위 경로로 export가 안 되어 있을 수 있음 -> 그럴 땐 실제 구현 위치(react.agent)에서 직접 import.
    #  이렇게 try/except로 fallback을 두면 환경/버전이 조금 달라도 서비스가 깨질 확률이 낮아짐.
    from langchain_classic.agents.react.agent import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain.tools import Tool
from langchain_core.prompts import PromptTemplate
from app.AImodels.tools import ALL_TOOLS

logger = logging.getLogger(__name__)


# 전역 변수
GLOBAL_TOOLS = ALL_TOOLS
GLOBAL_LLM = None

def initialize_global_agent():
    """전역 LLM과 Tool을 초기화 (로컬 모델)"""
    global GLOBAL_TOOLS, GLOBAL_LLM
    
    try:
        logger.info("🚀 OpenAI 불러오는 중...")
        
        # Initialize the language model with specific parameters
        llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.1,  # Low temperature for consistent reasoning
            max_tokens=2000,
            timeout=30
        )
        
        logger.info(f"✅ global tools 출력 확인: {GLOBAL_TOOLS}")
        logger.info(f"✅ Tools loaded: {[tool.name for tool in GLOBAL_TOOLS]}")
        
        
        GLOBAL_LLM = llm
        
        logger.info(f"✅ Total tools: {len(GLOBAL_TOOLS)}")
        
    except Exception as e:
        logger.error(f"❌ OpenAI 불러오기 오류: {e}")

        raise

# 이제 Supabase 직접 접근
def create_agent_executor(supabase: Client, user_id: str):  # 👈 1. 파라미터 변경
    """세션별 Agent Executor 생성 (Memory 없이 Supabase 직접 사용)"""
    global GLOBAL_LLM, GLOBAL_TOOLS
    
    if GLOBAL_LLM is None:
        logger.error("❌ LLM이 초기화되지 않았습니다.")
        raise ValueError("LLM is not initialized.")
    
    logger.info(f"🔧 Creating Agent Executor for user: {user_id}")
    
    # 👇 2. Supabase에서 채팅 기록 조회: 채팅 기록 직접 조회
    from app.services.chat_service import load_chat_history_from_db
    
    chat_history = load_chat_history_from_db(supabase, user_id, limit=6)
    chat_history_text = chat_history[0] if chat_history else ""
 
    # Create optimized prompt template # ✅ check
    react_prompt = PromptTemplate.from_template("""You are a helpful medical assistant. Answer questions based on the tools available and conversation history.

Available tools:
{ALL_TOOLS}

Tool Names: {tool_names}

Guidelines:
- If the question contains "prescription_id: [number]", use VL_Model_Image_Analyzer with that number as input 
- For drug information questions, use Public_Data_API_Searcher
- Otherwise, answer based on your knowledge

Use this format:
Question: the input question
Thought: think about what to do
Action: the tool to use (one of [{tool_names}]) OR say "No tool needed"
Action Input: the input for the tool (if using a tool)
Observation: the tool's response
... (repeat Thought/Action/Observation if needed)
Thought: I now know the final answer
Final Answer: the complete answer to the question

Begin!

Previous conversation:
{chat_history}

Question: {user_query}""")
    
    
    
    agent = create_react_agent(
        llm=GLOBAL_LLM,
        tools=GLOBAL_TOOLS,
        prompt=react_prompt
    )
    
    agent_executor = AgentExecutor(
        agent=agent,
        tools=GLOBAL_TOOLS,
        # memory=memory_instance, : memory 파라미터 제거: 채팅 기록이 이미 프롬프트에 포함됨 & LangChain Memory 시스템 불필요
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=3 
    )
    
    logger.info("ReAct agent created successfully")
    
    # executor 객체만 반환: invoke는 chat_service에서 실행 & agent_factory는 생성만 담당
    # ai_response = agent_executor.invoke({"input": user_query})
    logger.info("✅ Agent Executor created successfully")
    # logger.info(f"랭체인이 생성한 답변: {ai_response}")
    
    # return ai_response # string
    return agent_executor

SESSION_MEMORY_CACHE = {}

def cleanup_old_sessions(max_sessions: int = 1000):
    """메모리 캐시 정리"""
    if len(SESSION_MEMORY_CACHE) > max_sessions:
        keys_to_delete = list(SESSION_MEMORY_CACHE.keys())[:len(SESSION_MEMORY_CACHE) // 2]
        for key in keys_to_delete:
            del SESSION_MEMORY_CACHE[key]
        logger.info(f"🧹 Cleaned up {len(keys_to_delete)} old sessions")

GLOBAL_AGENT_EXECUTOR = None