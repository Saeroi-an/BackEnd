import "dotenv/config";
import { ChatOpenAI } from "@langchain/openai";
import { tool } from "@langchain/core/tools";
import * as z from "zod";

const VL_INFERENCE_API_URL = "http://localhost:8000/api/vqa_inference"; // 👈 Python API 서버 주소


const PRESCRIPTION_IMAGE_MAP: { [key: number]: string } = {
  1: "D:\\Backend\\testimage.png",
  2: "D:\\Backend\\testimage2.png",
  3: "D:\\Backend\\testimage3.jpg"
  // ... 다른 처방전 ID 및 경로
};

// ------------------------------
// 2. VQA Tool 정의 및 실행 함수 수정
// (image_path를 스키마에서 제거하고 내부 로직으로 이동)
// ------------------------------
const VLInference = tool(
  // LLM은 question과 prescription_id만 전달합니다.
  async ({ question, prescription_id }) => {
      
      // 1. Tool 내부에서 prescription_id를 사용하여 image_path를 조회합니다.
      const image_path = PRESCRIPTION_IMAGE_MAP[prescription_id];
      
      if (!image_path) {
           return `오류: 처방 ID ${prescription_id}에 해당하는 이미지 경로를 찾을 수 없습니다.`;
      }

      console.log(`[LangChain] ID ${prescription_id}의 이미지 경로 ${image_path}를 사용하여 Python VQA API 호출 시작.`);
      
      try {
          // 2. Python API 서버에 HTTP 요청을 보낼 때 image_path를 추가하여 전달합니다.
          const response = await fetch(VL_INFERENCE_API_URL, {
              method: 'POST',
              headers: {
                  'Content-Type': 'application/json',
              },
              // VQA 백엔드에 image_path와 question, prescription_id를 모두 포함하여 전달
              body: JSON.stringify({ 
                  image_path, 
                  question, 
                  prescription_id 
              }),
          });

          if (!response.ok) {
              throw new Error(`API 호출 실패: 상태 코드 ${response.status}`);
          }

          const data = await response.json();
          return data.inference_result; 

      } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            console.error("VQA API 통신 오류:", message);
            return `오류: Qwen-vl 모델 API 호출에 실패했습니다. (${message})`;
      }
  },
  {
      name: "Qwen-vl-inference",
      description: "在内部查询处方ID对应的图像路径后，对该图像提问并使用Qwen-vl模型进行推理。(处方解读)",
      // description: "처방 ID에 해당하는 이미지 경로를 내부적으로 조회한 후, 해당 이미지에 대해 질문을 하여 Qwen-vl 모델로 추론을 수행합니다. (처방전 해석)",
      // 3. 스키마에서 image_path 제거
      schema: z.object({
          question: z.string().describe("이미지에 대한 구체적인 질문"),
          prescription_id: z.number().int().describe("처리할 처방전의 고유 ID. 이 ID를 통해 이미지 경로가 결정됩니다."),
      }),
  }
);

// 위에 VLinfernce 처럼 Tool를 하나더 생성해야함
// const DrugAPI = tool() 


// ------------------------------
// 3. LLM 바인딩 및 호출
// ------------------------------
const llmWithStrictTrue = new ChatOpenAI({
model: "gpt-4o",
}).bindTools([VLInference], { // DrugAPI 추가해야함
strict: true,
tool_choice: VLInference.name,
});

const fixed_question = "这张处方上写了什么？ 尤其是药品、服用次数等，请准确全部告诉我。"
const prescription_id = 3

// 💡 수정된 중국어 프롬프트
const invoke_prompt = `请对 ID ${prescription_id} 对应的图片进行视觉问答：${fixed_question}`;

const strictTrueResult = await llmWithStrictTrue.invoke([{
    role: "user",
    content: invoke_prompt
}]);

console.dir(strictTrueResult.tool_calls, { depth: null });
console.dir(strictTrueResult)


if (strictTrueResult.tool_calls && strictTrueResult.tool_calls.length > 0) {
  const toolCall = strictTrueResult.tool_calls?.[0];

    if (toolCall) {
        console.log("\n=== 3단계: Tool 실제 실행 중... ===");
        console.log("실행할 Tool:", toolCall.name);
        console.log("전달 인자:", toolCall.args);
        
        // 🔥 타입 단언 추가
        const toolResult = await VLInference.invoke(toolCall.args as { 
            question: string; 
            prescription_id: number; 
        });
        
        console.log("\n=== 4단계: Tool 실행 결과 ===");
        console.log(toolResult);
    }
}