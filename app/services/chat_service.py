# app/services/chat_service.py
"""
Chat Service Module
세션별 메모리 관리 및 Agent 실행을 담당합니다.
"""
from langchain.memory import ConversationBufferMemory
from app.AImodels.agent_factory import (
    create_agent_executor, 
    SESSION_MEMORY_CACHE,
    cleanup_old_sessions
)

def get_or_create_memory(session_id: str) -> ConversationBufferMemory:
    """세션 ID로 메모리 인스턴스를 가져오거나 새로 생성"""
    if session_id not in SESSION_MEMORY_CACHE:
        SESSION_MEMORY_CACHE[session_id] = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        print(f"🆕 New session created: {session_id}")
        cleanup_old_sessions()
    
    return SESSION_MEMORY_CACHE[session_id]

def process_chat_query(session_id: str, user_query: str) -> str:
    """사용자 쿼리를 Agent에 전달하고 응답 생성"""
    try:
        # 1. 세션 메모리 로드
        session_memory = get_or_create_memory(session_id)
        
        print(f"💬 Processing query for session: {session_id}")
        print(f"📝 User query: {user_query}")
        
        # 2. Agent Executor 생성
        agent = create_agent_executor(session_memory)
        
        # 3. Agent 실행
        ai_response = agent.run(user_query)
        
        print(f"🤖 AI response: {ai_response}")
        
        return ai_response
        
    except Exception as e:
        print(f"❌ Agent 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        
        return "죄송합니다. 서비스 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."

def get_session_history(session_id: str) -> list:
    """세션의 대화 기록 조회"""
    if session_id in SESSION_MEMORY_CACHE:
        memory = SESSION_MEMORY_CACHE[session_id]
        return memory.chat_memory.messages
    return []

def clear_session(session_id: str) -> bool:
    """특정 세션의 메모리 삭제"""
    if session_id in SESSION_MEMORY_CACHE:
        del SESSION_MEMORY_CACHE[session_id]
        print(f"🗑️ Session cleared: {session_id}")
        return True
    return False