# app/AImodels/agent_factory.py
"""
Agent Factory Module
LLM과 Tool을 전역으로 초기화하고, 세션별 Agent Executor를 생성합니다.
"""
from langchain_community.llms import HuggingFaceEndpoint
from langchain.agents import AgentExecutor, create_react_agent
from langchain.memory import ConversationBufferMemory
from langchain import hub
import os
import logging

from app.AImodels.tools import ALL_TOOLS

logger = logging.getLogger(__name__)

# 환경 변수 설정
HUGGINGFACE_TOKEN = os.getenv('HUGGINGFACE_TOKEN', '')
REPO_ID = os.getenv('LLM_REPO_ID', 'google/flan-t5-large')

logger.info(f"🔍 HUGGINGFACE_TOKEN 길이: {len(HUGGINGFACE_TOKEN) if HUGGINGFACE_TOKEN else 0}")
logger.info(f"🔍 LLM_REPO_ID: {REPO_ID}")

# 전역 변수
huggingfacehub = None
initial_agent = None
GLOBAL_TOOLS = ALL_TOOLS

def initialize_global_agent():
    """전역 LLM과 Tool을 초기화"""
    global huggingfacehub, GLOBAL_TOOLS, initial_agent
    
    try:
        logger.info("🚀 Initializing Global LLM and Tools...")
        
        if not HUGGINGFACE_TOKEN:
            raise ValueError("HUGGINGFACE_TOKEN 환경변수가 설정되지 않았습니다.")
        
        # HuggingFace Endpoint LLM 초기화
        huggingfacehub = HuggingFaceEndpoint(
            repo_id=REPO_ID,
            huggingfacehub_api_token=HUGGINGFACE_TOKEN,
            temperature=0.1,
            max_new_tokens=512,
            task="text2text-generation"
        )
        
        logger.info(f"✅ Tools loaded: {[tool.name for tool in GLOBAL_TOOLS]}")
        
        initial_agent = True
        
        logger.info(f"✅ LLM initialized: {REPO_ID}")
        logger.info(f"✅ Total tools: {len(GLOBAL_TOOLS)}")
        
    except Exception as e:
        logger.error(f"❌ LLM 초기화 오류: {e}")
        huggingfacehub = None
        initial_agent = False
        raise

def create_agent_executor(memory_instance: ConversationBufferMemory):
    """세션별 Agent Executor 생성 (새로운 API 사용)"""
    if not huggingfacehub or not initial_agent:
        raise RuntimeError("LLM이 초기화되지 않았습니다.")
    
    logger.info("🔧 Creating Agent Executor with memory...")
    
    # ReAct 프롬프트 템플릿
    from langchain.prompts import PromptTemplate
    
    template = """Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}"""
    
    prompt = PromptTemplate.from_template(template)
    
    # ReAct Agent 생성
    agent = create_react_agent(
        llm=huggingfacehub,
        tools=GLOBAL_TOOLS,
        prompt=prompt
    )
    
    # Agent Executor 생성 (output_keys 명시)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=GLOBAL_TOOLS,
        memory=memory_instance,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5,
        return_intermediate_steps=False  # 👈 추가
    )
    
    # output_keys 명시적 설정
    agent_executor.output_keys = ["output"]  # 👈 추가
    
    logger.info("✅ Agent Executor created successfully")
    
    return agent_executor

# 세션 메모리 캐시
SESSION_MEMORY_CACHE = {}

def cleanup_old_sessions(max_sessions: int = 1000):
    """메모리 캐시 정리"""
    if len(SESSION_MEMORY_CACHE) > max_sessions:
        keys_to_delete = list(SESSION_MEMORY_CACHE.keys())[:len(SESSION_MEMORY_CACHE) // 2]
        for key in keys_to_delete:
            del SESSION_MEMORY_CACHE[key]
        logger.info(f"🧹 Cleaned up {len(keys_to_delete)} old sessions")

GLOBAL_AGENT_EXECUTOR = None