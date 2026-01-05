import os
from gateway_sdk.gateway import LLMGateway, GatewayConfig

def main():
    gw = LLMGateway(GatewayConfig(
        price_book_path=os.getenv("PRICE_BOOK_PATH", "pricing/price_book.yaml"),
        events_jsonl_path=os.getenv("EVENTS_JSONL_PATH", "data/events.jsonl"),
        region_default=os.getenv("REGION_DEFAULT", "us"),
    ))

    # OpenAI
    #gw.chat(
    #    provider="openai",
    #    model="gpt-4o-mini",
    #    messages=[{"role":"user","content":"Say hi in 5 words."}],
    #    tenant_id="tenant_a",
    #    user_id="user_1",
    #    feature="chat_support",
    #    endpoint="/v1/chat",
    #)

    # vLLM (OpenAI-compatible)
    gw.chat(
        provider="vllm",
        model="gpt-oss-20b-local",  # 依你 vLLM serve 的模型名
        messages=[{"role":"user","content":"Give me one sentence about Taipei."}],
        tenant_id="tenant_a",
        user_id="user_2",
        feature="local_chat",
        endpoint="/v1/chat",
        region="onprem",
    )

    # Gemini
    gw.chat(
        provider="gemini",
        model="gemini-3-flash-preview",  # 依你有權限的 model
        messages=[{"role":"user","content":"Give me 3 bullet points about RAG."}],
        tenant_id="tenant_b",
        user_id="user_3",
        feature="assist",
        endpoint="/v1/chat",
        region="global",
    )

    print("Done. Events appended to JSONL.")

if __name__ == "__main__":
    main()