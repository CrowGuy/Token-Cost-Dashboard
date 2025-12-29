import random
from gateway_sdk.pricing import PriceBook
from gateway_sdk.emitter import JsonlEmitter
from gateway_sdk.instrument import LLMInstrumentor

def fake_llm_client(prompt: str, model: str, **kwargs):
    # 假裝生成，回傳啥都行；tokens 我們先手動塞
    return {"text": "ok"}

if __name__ == "__main__":
    pb = PriceBook.load("pricing/price_book.yaml")
    emitter = JsonlEmitter("data/events.jsonl")
    inst = LLMInstrumentor(pb, emitter, provider_default="openai", region_default="us")

    for i in range(50):
        prompt = "You are a helpful assistant.\n" + ("context " * random.randint(50, 300))
        pt = random.randint(200, 2500)          # 模擬 prompt 變長
        ct = random.randint(50, 600)
        cache_hit = random.random() < 0.15
        retry = 1 if random.random() < 0.1 else 0

        inst.call(
            fake_llm_client,
            tenant_id="tenant_a" if i < 30 else "tenant_b",
            user_id=f"user_{i%5}",
            feature="search_rerank" if i % 2 == 0 else "chat_support",
            endpoint="/v1/chat",
            prompt=prompt,
            model="gpt-4o-mini",
            prompt_tokens=pt,
            completion_tokens=ct,
            retry_count=retry,
            cache_hit=cache_hit,
        )

    print("Wrote events to data/events.jsonl")