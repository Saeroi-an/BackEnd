# app/services/chat_service.py
"""
Chat Service Module
Supabase DB 기반 채팅 메모리 관리 및 Agent 실행
사용자당 하나의 세션 유지 (session_id = user_id)
"""
from supabase import Client
from app.AImodels.agent_factory import create_agent_executor
# from langchain.memory import ConversationBufferMemory
# from langchain.schema import HumanMessage, AIMessage
import logging
# from app.AImodels.tools import ALL_TOOLS
# from app.AImodels.agent_factory import (llm)

logger = logging.getLogger(__name__)

def load_chat_history_from_db(supabase: Client, user_id: str, limit: int = 25) -> list:
    """
    Supabase에서 사용자의 과거 채팅 기록을 가져와 LangChain 메시지 객체 리스트로 반환
    """
    try:
        from langchain_core.messages import HumanMessage, AIMessage
        
        # 1) prescription_chats 테이블에서 user_id로 필터링하여 조회
        query = (
            supabase.table("prescription_chats")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
        )
        
        # 2) limit이 있으면 최근 limit개만 가져오기
        if limit:
            query = query.limit(limit)
        
        # 3) 쿼리 실행
        result = query.execute()
        
        # 4) 시간순으로 정렬
        chat_history = sorted(result.data, key=lambda x: x["created_at"]) if result.data else []
        
        # 5) LangChain 메시지 객체로 변환
        messages = []
        for msg in chat_history:
            if msg["sender_type"] == "user":
                messages.append(HumanMessage(content=msg["message"]))
            elif msg["sender_type"] == "ai":
                messages.append(AIMessage(content=msg["message"]))
        
        return messages
    
    except Exception as e:
        logger.error(f"채팅 기록 조회 실패: {e}")
        return []


def process_chat_with_db(
    supabase: Client,
    user_id: str,
    user_query: str
) -> str:
    """
    DB 기반 채팅 처리 메인 함수
    
    Supabase에서 과거 대화 기록을 가져와 LangChain Agent를 실행하여 AI 응답 생성
    
    Args:
        supabase (Client): Supabase 클라이언트
        user_id (str): 사용자 ID
        user_query (str): 사용자의 현재 질문 (prescription.py에서 이미 전처리됨)
    
    Returns:
        str: AI 응답 문자열
    """
    try:
        # 1) 최근 대화 기록을 DB에서 가져오기 (메시지 객체 리스트)
        chat_history_messages = load_chat_history_from_db(supabase, user_id, limit=25)
        
        # 2) user_query를 그대로 사용 (prescription.py에서 이미 처리됨)
        logger.info(f"💬 Processing query for user: {user_id}")
        logger.info(f"📝 User query: {user_query[:100]}...")  # 처음 100자만 로그
        
        # 3) AgentExecutor 생성
        executor = create_agent_executor(supabase, user_id)
        
        # 4) invoke() 실행 (LangChain 메시지 객체 리스트 전달)
        result = executor.invoke({
            "input": user_query,  # prescription.py에서 이미 "prescription_id: X\n..." 형식으로 전달됨
            "chat_history": chat_history_messages
        })
        
        # 5) 결과에서 "output"만 뽑아 문자열로 반환
        ai_response = result.get("output", "응답을 생성할 수 없습니다.")
        logger.info(f"result 상황!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!: {result}")
        logger.info("🤖 AI response generated")
        
        return ai_response
        
    except Exception as e:
        # 예외가 발생하면 traceback을 찍고, 사용자에게는 일반 에러 메시지를 반환함
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
    from langchain_core.messages import HumanMessage, AIMessage
    
    if supabase is None:
        return f"[[이전 대화 기록 for {session_id}]]"
    
    # 메시지 객체 리스트 가져오기
    messages = load_chat_history_from_db(supabase, session_id)
    
    # 문자열 형식으로 변환
    history_text = f"[[이전 대화 기록 for {session_id}]]\n"
    for msg in messages:
        if isinstance(msg, HumanMessage):
            history_text += f"사용자: {msg.content}\n"
        elif isinstance(msg, AIMessage):
            history_text += f"AI: {msg.content}\n"
    
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