import streamlit as st
from openai import OpenAI
from supabase import create_client
import json, os
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np

# ================= 1. 配置 API =================
# 把这里的密钥换成你自己的（保留引号）
MY_API_KEY = st.secrets["DEEPSEEK_API_KEY"] 

# 连接 DeepSeek
client = OpenAI(
    api_key=MY_API_KEY,
    base_url="https://api.deepseek.com"
)

# 连接 Supabase（云账本）
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

# ================= 2. 设定角色 =================
system_prompt = """
你是《建筑工程CAD》课程的AI助教。本课程使用中望建筑版CAD。
回答时优先使用中望建筑版的专用命令，如"绘制墙体""轴网标注"等，不要用AutoCAD通用命令替代。

【重要规则】当学生提问中出现以下词汇："我不会"、"我错了"、"搞不懂"、"对不上"、"总是断开"、"出错了"、"怎么办"时，你必须调用 record_weakness 工具记录该薄弱点。这是强制要求。
"""

# ================= 3. 薄弱点记录工具 =================
tools = [{
    "type": "function",
    "function": {
        "name": "record_weakness",
        "description": "当学生提问暴露出对某个CAD知识点的理解困难或错误操作时，记录该薄弱点。",
        "parameters": {
            "type": "object",
            "properties": {
                "knowledge_point": {
                    "type": "string",
                    "description": "知识点：图层管理、基础绘图命令、轴网与墙体、参数化门窗、尺寸与文字、图框与输出、图纸校审"
                },
                "error_type": {
                    "type": "string",
                    "description": "错误类型：命令混淆、参数错误、操作顺序错误、概念不清"
                }
            },
            "required": ["knowledge_point", "error_type"]
        }
    }
}]

def record_weakness(knowledge_point, error_type):
    print(f"【测试追踪】后台正在记录：{knowledge_point} - {error_type}")
    supabase.table("weakness_log").insert({
        "student_id": st.session_state.student_id,
        "knowledge_point": knowledge_point,
        "error_type": error_type
    }).execute()
    return "已记录薄弱点"

# ================= 4. 网页界面 =================
st.set_page_config(page_title="CAD AI伴学", layout="wide")
st.title("《建筑工程CAD》AI伴学智能体")

# 从链接里读学号
query_params = st.query_params
if "student_id" in query_params:
    st.session_state.student_id = query_params["student_id"]

# 如果没学号，就让学生输入
if "student_id" not in st.session_state or not st.session_state.student_id:
    student_id = st.text_input("请输入你的学号，按回车确认")
    if student_id:
        st.session_state.student_id = student_id
        st.query_params["student_id"] = student_id
        st.rerun()
    st.stop()

# 侧边栏：雷达图
with st.sidebar:
    st.header("学情诊断")
    
    if st.button("刷新诊断报告"):
        # 注意：这里从 Supabase 读取数据，整段都缩进在 if st.button 里面
        data = supabase.table("weakness_log").select("knowledge_point").eq("student_id", st.session_state.student_id).execute()

        # 注意：这里的 if 要和上面 data = ... 对齐，不能跑到按钮外面去
        if data.data:
            log = data.data
            categories = ["图层管理", "基础绘图命令", "轴网与墙体", "参数化门窗", "尺寸与文字", "图框与输出", "图纸校审"]
            scores = {cat: 100 for cat in categories}
            
            for entry in log:
                kp = entry["knowledge_point"]
                if kp in scores:
                    scores[kp] = max(0, scores[kp] - 15)
            
            values = [scores[cat] for cat in categories]
            angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
            values += values[:1]
            angles += angles[:1]
            
            fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
            ax.plot(angles, values, 'o-', linewidth=2)
            ax.fill(angles, values, alpha=0.25)
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(categories)
            ax.set_ylim(0, 100)
            plt.title("学情诊断雷达图")
            plt.savefig("radar.png")
            st.image("radar.png")
            
            weakest = min(scores, key=scores.get)
            st.warning(f"建议优先巩固：{weakest}")
        else:
            st.info("暂无学习记录，快去问问题吧")

# 主聊天区
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": system_prompt}]

for msg in st.session_state.messages:
    if isinstance(msg, dict) and msg["role"] != "system":
        st.chat_message(msg["role"]).write(msg["content"])

if user_input := st.chat_input("问一个CAD问题..."):
    st.chat_message("user").write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 调用 AI
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=st.session_state.messages,
        tools=tools
    )
    
    msg = response.choices[0].message
    
    # 处理自动记录薄弱点
    if msg.tool_calls:
        for tool_call in msg.tool_calls:
            if tool_call.function.name == "record_weakness":
                args = json.loads(tool_call.function.arguments)
                record_weakness(**args)
        
        st.session_state.messages.append(msg)
        for tool_call in msg.tool_calls:
            st.session_state.messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": "已记录"
            })
        
        final = client.chat.completions.create(
            model="deepseek-chat",
            messages=st.session_state.messages,
            tools=tools
        )
        reply = final.choices[0].message.content
    else:
        reply = msg.content
    
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.chat_message("assistant").write(reply)
