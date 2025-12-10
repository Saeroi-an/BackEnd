# app/services/chat_service.py
"""
Chat Service Module
Supabase DB 기반 채팅 메모리 관리 및 Agent 실행
사용자당 하나의 세션 유지 (session_id = user_id)
"""
from supabase import Client
from app.AImodels.agent_factory import create_agent_executor
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
import logging

logger = logging.getLogger(__name__)


def load_chat_history_from_db(supabase: Client, user_id: str) -> list:
    """
    Supabase에서 사용자의 모든 채팅 기록 조회
    
    Args:
        supabase: Supabase 클라이언트
        user_id: 사용자 ID (= session_id)
        
    Returns:
        채팅 메시지 리스트
    """
    try:
        result = supabase.table("prescription_chats").select("*").eq(
            "user_id", user_id
        ).order("created_at").execute()
        
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"채팅 기록 조회 실패: {e}")
        return []


def create_memory_from_history(chat_history: list) -> ConversationBufferMemory:
    """
    DB에서 가져온 채팅 기록을 LangChain Memory로 변환
    
    Args:
        chat_history: DB에서 조회한 채팅 기록
        
    Returns:
        ConversationBufferMemory 인스턴스
    """
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True
    )
    
    # DB 기록을 메모리에 추가
    for msg in chat_history:
        if msg['sender_type'] == 'user':
            memory.chat_memory.add_message(HumanMessage(content=msg['message']))
        elif msg['sender_type'] == 'ai':
            memory.chat_memory.add_message(AIMessage(content=msg['message']))
    
    logger.info(f"📚 Loaded {len(chat_history)} messages into memory")
    
    return memory


def process_chat_with_db(
    supabase: Client,
    user_id: str,
    user_query: str,
    prescription_analysis: dict = None
) -> str:
    """
    DB 기반 채팅 처리
    
    Args:
        supabase: Supabase 클라이언트
        user_id: 사용자 ID (= session_id)
        user_query: 사용자 질문
        prescription_analysis: 처방전 분석 결과 (옵션)
        
    Returns:
        AI 응답
    """
    try:
        # 1. DB에서 과거 채팅 기록 로드
        chat_history = load_chat_history_from_db(supabase, user_id)
        
        # 2. 메모리 생성
        memory = create_memory_from_history(chat_history)
        
        # 3. 프롬프트 생성 (처방전 정보 포함)
        enhanced_query = user_query
        if prescription_analysis:
            enhanced_query = f"""
처방전 분석 결과:
{prescription_analysis}

사용자 질문: {user_query}

위 처방전 정보를 참고하여 답변해주세요.
"""
        
        logger.info(f"💬 Processing query for user: {user_id}")
        
        # 4. Agent 실행
        agent = create_agent_executor(memory)
        # ai_response = agent.run(enhanced_query)
        result = agent.invoke({"input": enhanced_query})
        ai_response = result.get("output", "응답을 생성할 수 없습니다.")
        
        logger.info(f"🤖 AI response generated")
        
        return ai_response
        
    except Exception as e:
        logger.error(f"❌ Chat processing error: {e}")
        import traceback
        traceback.print_exc()
        
        return "죄송합니다. 서비스 처리 중 오류가 발생했습니다."


def save_message_to_db(
    supabase: Client,
    user_id: str,
    prescription_id: int,
    message: str,
    sender_type: str
) -> dict:
    """
    채팅 메시지를 DB에 저장
    
    Args:
        supabase: Supabase 클라이언트
        user_id: 사용자 ID
        prescription_id: 처방전 ID
        message: 메시지 내용
        sender_type: 'user' 또는 'ai'
        
    Returns:
        저장된 메시지 데이터
    """
    try:
        data = {
            "user_id": user_id,
            "prescription_id": prescription_id,
            "message": message,
            "sender_type": sender_type
        }
        
        result = supabase.table("prescription_chats").insert(data).execute()
        
        logger.info(f"💾 Message saved: {sender_type}")
        
        return result.data[0] if result.data else None
        
    except Exception as e:
        logger.error(f"메시지 저장 실패: {e}")
        raise


# AI 파트 호환성을 위한 Alias 함수

def get_history_from_supabase(session_id: str, supabase: Client = None) -> str:
    """
    AI 파트 supabase_memory.py 호환 함수
    
    Args:
        session_id: 세션 ID (= user_id)
        supabase: Supabase 클라이언트 (옵션)
        
    Returns:
        대화 기록 문자열
    """
    if supabase is None:
        # Supabase 클라이언트가 없으면 기본 반환
        return f"[[이전 대화 기록 for {session_id}]]"
    
    chat_history = load_chat_history_from_db(supabase, session_id)
    
    # 문자열 형식으로 변환
    history_text = f"[[이전 대화 기록 for {session_id}]]\n"
    for msg in chat_history:
        sender = "사용자" if msg['sender_type'] == 'user' else "AI"
        history_text += f"{sender}: {msg['message']}\n"
    
    return history_text


def save_history_to_supabase(
    session_id: str,
    user_input: str,
    ai_response: str,
    supabase: Client = None,
    prescription_id: int = None
):
    """
    AI 파트 supabase_memory.py 호환 함수
    
    Args:
        session_id: 세션 ID (= user_id)
        user_input: 사용자 메시지
        ai_response: AI 응답
        supabase: Supabase 클라이언트 (옵션)
        prescription_id: 처방전 ID (옵션)
    """
    if supabase is None:
        logger.warning(f"[{session_id}] Supabase 클라이언트가 없어 저장을 건너뜁니다.")
        return
    
    # 사용자 메시지 저장
    save_message_to_db(supabase, session_id, prescription_id, user_input, "user")
    
    # AI 응답 저장
    save_message_to_db(supabase, session_id, prescription_id, ai_response, "ai")
    
    logger.info(f"[{session_id}] 대화 기록이 Supabase에 저장됨.")