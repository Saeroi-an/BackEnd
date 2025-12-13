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

logger = logging.getLogger(__name__)


def load_chat_history_from_db(supabase: Client, user_id: str, limit: int = 25) -> list:
    #Supabase에서 사용자의 과거 채팅 기록을 가져와 "하나의 문자열"로 합친 뒤 리스트로 감싸서 반환
    # (형태: ["Human: ...\\nAI: ...\\n"])

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
    
    # DB 기반 채팅 처리 메인 함수
    # Supabase에서 과거 대화 기록을 가져와 chat_history_text를 만들고 필요 시 처방전 분석 결과를 질문에 함께 포함.
    # AgentExecutor를 생성 후 invoke()를 실행하여 결과에서 "output"을 문자열로 반환함.

    # Args:
    #     supabase (Client): Supabase 클라이언트
    #     user_id (str): 사용자 ID
    #     user_query (str): 사용자의 현재 질문(입력)
    #     prescription_analysis (dict | None): 처방전 분석 결과(선택)

    # Returns:
    #     str: AI 응답 문자열
    
    try:
        # 1) 최근 대화 기록을 DB에서 가져오기
        chat_history_text = load_chat_history_from_db(supabase, user_id, limit=25)[0]

        # 2) 사용자 질문 보강(enhanced_query)
        enhanced_query = user_query
        if prescription_analysis:
            enhanced_query = f"""처방전 분석 결과:
{prescription_analysis}

사용자 질문: {user_query}

위 처방전 정보를 참고하여 답변해주세요.
"""

        logger.info(f"💬 Processing query for user: {user_id}")

        # 3) AgentExecutor 생성
        # (중요) agent_factory 내부에서 memory를 쓰지 않아야 함
        executor = create_agent_executor(supabase, user_id)

        # 4) invoke() 실행 (여기서 실제 LLM 호출/툴 호출이 일어남)
        result = executor.invoke({
            "input": enhanced_query,           # ReAct 기본 입력 키(보통 input)
            "chat_history": chat_history_text  # 우리가 추가한 변수
        })

        # 5) 결과에서 "output"만 뽑아 문자열로 반환
        ai_response = result.get("output", "응답을 생성할 수 없습니다.")

        logger.info("🤖 AI response generated")
        return ai_response

    except Exception as e:
        # 예외가 발생하면 traceback을 찍고, 사용자에게는 일반 에러 메시지를 반환함
        logger.error(f"❌ Chat processing error: {e}")
        import traceback
        traceback.print_exc()
        return "죄송합니다. 서비스 처리 중 오류가 발생했습니다."