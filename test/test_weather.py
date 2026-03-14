# 天气功能测试
from src.agent.workflow import run_agent
from src.agent.tools import get_weather

print("=" * 60)
print("测试1: 直接调用天气工具")
print("=" * 60)

cities = ["北京", "上海", "杭州", "深圳"]
for city in cities:
    print(f"\n查询 {city} 天气:")
    result = get_weather(city)
    print(result[:300])

print("\n" + "=" * 60)
print("测试2: 通过工作流查询")
print("=" * 60)

queries = [
    "明天北京的天气怎么样",
    "上海后天天气如何",
]

for q in queries:
    print(f"\n查询: {q}")
    result = run_agent(q)
    print(f"意图: {result.get('intent')}")
    print(f"成功: {result.get('success')}")
    print(f"响应:\n{result.get('response', '')[:400]}...")
