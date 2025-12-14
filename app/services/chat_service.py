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
    Supabase에서 사용자의 과거 채팅 기록을 가져와 "하나의 문자열"로 합친 뒤 리스트로 감싸서 반환
    (형태: ["Human: ...\\nAI: ...\\n"])
    """
    try:
        # 1) prescription_chats 테이블에서 user_id로 필터링하여 조회.
        #    created_at 기준 desc(내림차순)으로 가져오면 최근 기록부터 내려옴.
        query = (
            supabase.table("prescription_chats")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
        )
        
        # 2) limit이 있으면 최근 limit개만 가져오기.
        if limit:
            query = query.limit(limit)
        
        # 3) 쿼리 실행
        result = query.execute()
        
        # 4) DB에서 가져온 결과는 desc(최근→과거)일 가능성이 높음.
        #    프롬프트에 넣을 때는 대화 흐름을 created_at 오름차순(시간순)으로 다시 정렬.
        chat_history = sorted(result.data, key=lambda x: x["created_at"]) if result.data else []
        
        # 5) "Human: ...", "AI: ..." 포맷으로 한 덩어리 문자열로 합침.
        #    ※ 여기 포맷은 프롬프트 설계에 따라 바뀌어도 됨
        history_text = ""
        for msg in chat_history:
            if msg["sender_type"] == "user":
                history_text += f"Human: {msg['message']}\n"
            elif msg["sender_type"] == "ai":
                history_text += f"AI: {msg['message']}\n"
        
        # 6) 호환성 유지 목적으로 리스트로 감싸 반환함.
        return [history_text]
    
    except Exception as e:
        # DB 조회 실패 등 예외가 나면 빈 문자열 리스트를 반환.
        # 호출부에서는 [0]으로 꺼내 쓸 때도 안전하게 동작함.
        logger.error(f"채팅 기록 조회 실패: {e}")
        return [""]


def process_chat_with_db(
    supabase: Client,
    user_id: str,
    user_query: str,
    prescription_analysis: dict = None
) -> str:
    """
    DB 기반 채팅 처리 메인 함수
    
    Supabase에서 과거 대화 기록을 가져와 chat_history_text를 만들고 
    필요 시 처방전 분석 결과를 질문에 함께 포함.
    AgentExecutor를 생성 후 invoke()를 실행하여 결과에서 "output"을 문자열로 반환함.
    
    Args:
        supabase (Client): Supabase 클라이언트
        user_id (str): 사용자 ID
        user_query (str): 사용자의 현재 질문(입력)
        prescription_analysis (dict | None): 처방전 분석 결과(선택)
    
    Returns:
        str: AI 응답 문자열
    """
    try:
        # 1) 최근 대화 기록을 DB에서 가져오기
        chat_history_text = load_chat_history_from_db(supabase, user_id, limit=25)[0]
        
        # 2) 사용자 질문 보강(enhanced_query)
#        enhanced_query = user_query
#         if prescription_analysis:
#             enhanced_query = f"""처방전 분석 결과:
# {prescription_analysis}
# 사용자 질문: {user_query}
# 위 처방전 정보를 참고하여 답변해주세요.
# """
        
        logger.info(f"💬 Processing query for user: {user_id}")
        
        # 3) AgentExecutor 생성
        # (중요) agent_factory 내부에서 memory를 쓰지 않아야 함
        executor = create_agent_executor(supabase, user_id)
        
        # 4) invoke() 실행 (여기서 실제 LLM 호출/툴 호출이 일어남)
        # ✅ 수정: "input" → "user_query" (agent_factory.py의 프롬프트와 일치)
        result = executor.invoke({
            "input": user_query,      # ← 수정됨
            "chat_history": chat_history_text
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