import matplotlib
from matplotlib import font_manager
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
你是《建筑工程CAD》课程中一位非常亲切、耐心、幽默的AI助教。
你的任务是用通俗易懂、鼓励式的语言，帮助学生解决中望建筑版CAD的操作问题。
回答时优先使用中望建筑版的专用命令，如"绘制墙体""轴网标注"等，不要用AutoCAD通用命令替代。
【重要规则】当学生提问中出现"我不会"、"我错了"、"搞不懂"、"对不上"、"总是断开"、"出错了"等困惑时，你必须调用 record_weakness 工具记录该薄弱点。这是强制要求。
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
    supabase.table("weakness_log").insert({
        "student_id": st.session_state.student_id,
        "student_name": st.session_state.student_name,  # 加上这行
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

# 如果没学号，就让学生输入学号和姓名
if "student_id" not in st.session_state or not st.session_state.student_id:
    # 1. 欢迎引导语
    st.markdown("<h2 style='text-align: center;'>👋 欢迎来到《建筑工程CAD》AI伴学空间！</h2>", unsafe_allow_html=True)
    st.info("我是你的专属CAD伴学小助手，可以为你解答中望建筑版CAD的操作问题、自动记录你的薄弱点，并为你生成专属学情诊断报告。")
    
    # 2. 头像选择
    st.write("**第一步：选一个属于你的头像吧**")
    avatar_options = ["👨‍🎓", "👩‍🎓", "👷", "👷‍♀️", "🧑‍💻"]
    selected_avatar = st.radio("选择头像", avatar_options, horizontal=True, label_visibility="collapsed")
    
    # 3. 学号和姓名输入
    st.write("**第二步：输入你的学号和姓名**")
    student_id = st.text_input("请输入你的学号")
    student_name = st.text_input("请输入你的姓名（中文即可）")
    
    # 4. 进入系统
    if st.button("进入系统"):
        if student_id and student_name:
            st.session_state.student_id = student_id
            st.session_state.student_name = student_name
            st.session_state.avatar = selected_avatar  # 把选的头像存起来，后面聊天界面会用到
            st.query_params["student_id"] = student_id
            st.rerun()
        else:
            st.warning("学号和姓名都不能为空哦！")
    st.stop()

# 侧边栏：雷达图
with st.sidebar:
    st.header("学情诊断")
    
       # ================= 教师看板 =================
    st.subheader("👨‍🏫 教师专区")
    teacher_pwd = st.text_input("请输入教师密码", type="password")
    
    if teacher_pwd == "teacher123":
        st.success("教师模式已开启")
        
        # 功能1：全班薄弱点排行
        if st.button("查看全班薄弱点排行"):
            from collections import Counter
            data = supabase.table("weakness_log").select("knowledge_point").execute()
            if data.data:
                points = [row["knowledge_point"] for row in data.data]
                counts = Counter(points)
                st.bar_chart(counts)
            else:
                st.info("暂无全班数据")
        
        # 功能2：个人学情查询 + AI评语
        query_id = st.text_input("输入学号查询个人学情")
        if query_id:
            data = supabase.table("weakness_log").select("*").eq("student_id", query_id).execute()
            if data.data:
                st.write(f"**学号 {query_id} 的薄弱点记录：**")
                for row in data.data:
                    st.write(f"- {row['knowledge_point']}：{row['error_type']}")
                
                # 功能3：AI一键生成个性化诊断
                if st.button("🤖 AI生成诊断评语"):
                    with st.spinner("AI正在分析学情..."):
                        record_text = "".join([f"- {row['knowledge_point']}: {row['error_type']}\n" for row in data.data])
                        prompt = f"你是一个《建筑工程CAD》课程的学情分析师。这是学号{query_id}同学的薄弱点记录：\n{record_text}\n请给该学生写一段100字左右的学习诊断评语，指出他的薄弱环节，并给出具体的改进建议。"
                        
                        response = client.chat.completions.create(
                            model="deepseek-chat",
                            messages=[{"role": "user", "content": prompt}]
                        )
                        st.info(response.choices[0].message.content)
            else:
                st.info("该学号暂无记录")
    elif teacher_pwd:
        st.error("密码错误")
    # ============================================   
        # 数据加载区：点击后把数据存入 session_state
    if st.button("刷新诊断报告"):
        data = supabase.table("weakness_log").select("knowledge_point").eq("student_id", st.session_state.student_id).execute()
        if data.data:
            st.session_state.my_log = data.data  # 存入会话记忆
        else:
            st.session_state.my_log = []  # 没数据就存个空列表

    # 显示区：只要 session_state 里有数据，就画图
    if st.session_state.get("my_log"):
        log = st.session_state.my_log  # 从会话记忆里拿数据，不怕页面重跑
        
               # 1. 画雷达图（全局注册中文字体，最稳健方案）
        import os
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
        
        # 动态获取字体文件的绝对路径（确保云端能找到）
        current_dir = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(current_dir, "SourceHanSansCN-Regular.otf")
        
        # 将字体注入到 Matplotlib 的全局字体管理器中
        font_manager.fontManager.addfont(font_path)
        # 获取字体的真实名称并设置为默认字体
        font_name = font_manager.FontProperties(fname=font_path).get_name()
        plt.rcParams['font.sans-serif'] = [font_name]
        plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示方块的问题
        
        # 绘制雷达图
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
        ax.set_xticklabels(categories)  # 这里不用加 fontproperties 了，全局已生效
        ax.set_ylim(0, 100)
        
        plt.title("学情诊断雷达图", pad=25, fontsize=14)
        plt.savefig("radar.png")
        st.image("radar.png")
        
        weakest = min(scores, key=scores.get)
        st.warning(f"建议优先巩固：{weakest}")
        
        # 2. 学生专属建议按钮
        if st.button("🤖 获取我的专属学习建议"):
            with st.spinner("AI正在为你分析..."):
                record_text = "、".join([entry["knowledge_point"] for entry in log])
                prompt = f"你是一个亲切幽默的CAD课程助教。学生{st.session_state.get('student_name', '同学')}最近在以下知识点遇到了困难：{record_text}。请用鼓励、轻松的语气，给学生写一段100字左右的加油打气和学习建议。"
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}]
                )
                st.success(response.choices[0].message.content)
    else:
        # 如果没点过刷新，或者真的没数据
        if "my_log" in st.session_state and not st.session_state.my_log:
            st.info("暂无学习记录，快去问问题吧")
        else:
            st.info("点击上方按钮加载你的学情诊断报告")

# 主聊天区
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": system_prompt}]

for msg in st.session_state.messages:
    if isinstance(msg, dict) and msg["role"] != "system":
        st.chat_message(msg["role"]).write(msg["content"])

# 动态显示欢迎语
st.success(f"你好，{st.session_state.get('student_name', '同学')}！今天想画点什么？如果不知道怎么问，可以看看下面的示例👇")

# 示例提问引导
with st.expander("💡 不知道怎么问？点这里看看示例吧"):
    st.markdown("""
    - 轴网标注一键生成的命令怎么用？
    - 我画墙体时总是断开对不上，怎么办？
    - 图层锁定了怎么解锁？
    - 尺寸标注的样式怎么统一修改？
    """)

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
