# app/AImodels/agent_factory.py
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
from langchain_community.llms import HuggingFacePipeline
from langchain.agents import AgentExecutor, create_react_agent
from langchain.memory import ConversationBufferMemory
from langchain import hub  # 👈 추가
import torch
import os
import logging
from app.AImodels.tools import ALL_TOOLS

logger = logging.getLogger(__name__)

# 환경 변수 설정
REPO_ID = os.getenv('LLM_REPO_ID', 'google/flan-t5-large')

logger.info(f"🔍 LLM_REPO_ID: {REPO_ID}")

# 전역 변수
huggingfacehub = None
initial_agent = None
GLOBAL_TOOLS = ALL_TOOLS

def initialize_global_agent():
    """전역 LLM과 Tool을 초기화 (로컬 모델)"""
    global huggingfacehub, GLOBAL_TOOLS, initial_agent
    
    try:
        logger.info("🚀 Initializing Global LLM and Tools (Local Model)...")
        
        # GPU 사용 가능 확인
        device = 0 if torch.cuda.is_available() else -1
        logger.info(f"🖥️ Using device: {'GPU' if device == 0 else 'CPU'}")
        
        # 토크나이저와 모델 로드
        tokenizer = AutoTokenizer.from_pretrained(REPO_ID)
        model = AutoModelForSeq2SeqLM.from_pretrained(
            REPO_ID,
            torch_dtype=torch.float16 if device == 0 else torch.float32,
            device_map="auto" if device == 0 else None
        )
        
        # Pipeline 생성
        pipe = pipeline(
            "text2text-generation",
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=512,
            temperature=0.1
        )
        
        # LangChain LLM으로 래핑
        huggingfacehub = HuggingFacePipeline(pipeline=pipe)
        
        logger.info(f"✅ Tools loaded: {[tool.name for tool in GLOBAL_TOOLS]}")
        
        initial_agent = True
        
        logger.info(f"✅ LLM initialized (Local): {REPO_ID}")
        logger.info(f"✅ Total tools: {len(GLOBAL_TOOLS)}")
        
    except Exception as e:
        logger.error(f"❌ LLM 초기화 오류: {e}")
        huggingfacehub = None
        initial_agent = False
        raise

def create_agent_executor(memory_instance: ConversationBufferMemory):
    """세션별 Agent Executor 생성"""
    if not huggingfacehub or not initial_agent:
        raise RuntimeError("LLM이 초기화되지 않았습니다.")
    
    logger.info("🔧 Creating Agent Executor with memory...")
    
    # LangChain Hub에서 공식 ReAct 프롬프트 가져오기
    prompt = hub.pull("hwchase17/react")
    
    agent = create_react_agent(
        llm=huggingfacehub,
        tools=GLOBAL_TOOLS,
        prompt=prompt
    )
    
    agent_executor = AgentExecutor(
        agent=agent,
        tools=GLOBAL_TOOLS,
        memory=memory_instance,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5
    )
    
    logger.info("✅ Agent Executor created successfully")
    
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