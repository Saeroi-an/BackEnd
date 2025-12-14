# app/AImodels/agent_factory.py
import os
import logging
from supabase import Client

# LangChain 최신 버전(1.x)에서는 기존의 에이전트 구현(AgentExecutor, ReAct agent 등)이
# 'langchain' 본 패키지에서 분리되어 'langchain-classic' 패키지로 이동한 경우가 많음.
# 기존 코드(레거시 ReAct 에이전트)를 유지하려면 classic에서 가져오는 게 안정적.
from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
# ↑ AgentExecutor: "Agent(추론 로직) + Tools(도구)"를 묶어서 실행(invoke)할 수 있게 해주는 실행기
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from app.AImodels.tools import ALL_TOOLS
from app.core.config import settings


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
            api_key=settings.OPENAI_API_KEY,
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
def create_agent_executor(supabase: Client, user_id: str):
    """세션별 Agent Executor 생성 (Memory 없이 Supabase 직접 사용)"""
    # Import at function level to avoid circular dependency
    from app.services.chat_service import load_chat_history_from_db
    
    global GLOBAL_LLM, GLOBAL_TOOLS
    
    if GLOBAL_LLM is None:
        logger.error("❌ LLM이 초기화되지 않았습니다.")
        raise ValueError("LLM is not initialized.")
    
    logger.info(f"🔧 Creating Agent Executor for user: {user_id}")
    
    
    chat_history = load_chat_history_from_db(supabase, user_id)
    chat_history_text = chat_history[0] if chat_history else ""
 
    # Create optimized prompt template # ✅ check
    react_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a helpful medical assistant for Chinese patients in Korea.

Your capabilities:
- Analyze prescription images when users upload them
- Search for Korean drug information
- Answer medical questions in Chinese

Guidelines:
- Always respond in Chinese (中文)
- Be clear and concise
- If you need to analyze a prescription image, use the available tools
- If asked about drug information, search using the drug API tool
- Provide helpful medical guidance while being cautious about medical advice

Remember: You're helping Chinese patients understand Korean prescriptions and medical information."""),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}")
    ])

#     react_prompt = PromptTemplate.from_template("""You are a helpful medical assistant. Answer questions based on the tools available and conversation history.

# Available tools:
# {tools}

# Tool Names: {tool_names}

# Guidelines:
# - If the question contains "prescription_id: [number]", use VL_Model_Image_Analyzer with that number as input 
# - For drug information questions, use Public_Data_API_Searcher
# - Otherwise, answer based on your knowledge

# Use this format:
# Question: the input question
# Thought: think about what to do
# Action: the tool to use (one of [{tool_names}]) OR say "No tool needed"
# Action Input: the input for the tool (if using a tool)
# Observation: the tool's response
# ... (repeat Thought/Action/Observation if needed)
# Thought: I now know the final answer
# Final Answer: the complete answer to the question

# Begin!

# Previous conversation:
# {chat_history}

# Question: {user_query}""")
    
    
    
    agent = create_openai_tools_agent(
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