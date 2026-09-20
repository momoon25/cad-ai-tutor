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
【重要规则】当学生提问中出现"我不会"、"我错了"、"搞不懂"、"对不上"、"总是断开"、"出错了"等困惑时，你必须调用 record_weakness 工具记录该薄弱点，并根据学生的提问方式判断其学习习惯，从以下选项中选择最匹配的一项：提问深度浅、提问深度深、表述模糊、表述清晰、依赖AI直接要答案、有独立思考痕迹、有验证追问意识。这是强制要求。
"""

# ================= 3. 薄弱点记录工具 =================
tools = [{
    "type": "function",
    "function": {
        "name": "record_weakness",
         "description": "当学生提问暴露出对某个CAD知识点的理解困难或操作错误时，记录该薄弱点，并判断其学习习惯。",
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
                },
                "learning_habit": {
                    "type": "string",
                    "description": "根据学生提问方式判断其学习习惯，从以下选项中选择：提问深度浅、提问深度深、表述模糊、表述清晰、依赖AI直接要答案、有独立思考痕迹、有验证追问意识"
                }
            },
            "required": ["knowledge_point", "error_type", "learning_habit"]
        }
    }
}]

def record_weakness(knowledge_point, error_type, learning_habit):
    supabase.table("weakness_log").insert({
        "student_id": st.session_state.student_id,
        "student_name": st.session_state.student_name,
        "knowledge_point": knowledge_point,
        "error_type": error_type,
        "learning_habit": learning_habit
    }).execute()
    return "已记录"

# ================= 4. 网页界面 =================
st.set_page_config(page_title="CAD AI伴学", layout="wide")
st.title("《建筑工程CAD》AI伴学智能体")

# 从链接里读学号
query_params = st.query_params
if "student_id" in query_params:
    st.session_state.student_id = query_params["student_id"]

# 如果没学号，就让学生输入学号和姓名
if "student_id" not in st.session_state or not st.session_state.student_id:
        # 显示智能体形象
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.image("robot.jpeg", width=150)
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
        
        # ========== 功能1：全班薄弱点排行 ==========
        if st.button("查看全班薄弱点排行"):
            from collections import Counter
            import datetime
            
            # 时间区间选择
            with st.form("time_filter_form"):
                st.write("**选择时间范围：**")
                col_a, col_b = st.columns(2)
                with col_a:
                    start_date = st.date_input("开始日期", value=datetime.date(2026, 4, 1))
                with col_b:
                    end_date = st.date_input("结束日期", value=datetime.date(2026, 5, 31))
                submitted = st.form_submit_button("应用时间筛选")
            
            # 查询指定时间范围内的数据
            data = supabase.table("weakness_log").select("knowledge_point, created_at").gte(
                "created_at", start_date.isoformat()
            ).lte(
                "created_at", end_date.isoformat() + "T23:59:59"
            ).execute()
            
            if data.data:
                points = [row["knowledge_point"] for row in data.data]
                counts = Counter(points)
                
                # 用 matplotlib 画横向彩色条形图
                import os
                import matplotlib.pyplot as plt
                from matplotlib import font_manager
                
                current_dir = os.path.dirname(os.path.abspath(__file__))
                font_path = os.path.join(current_dir, "SourceHanSansCN-Regular.otf")
                font_manager.fontManager.addfont(font_path)
                font_name = font_manager.FontProperties(fname=font_path).get_name()
                plt.rcParams['font.sans-serif'] = [font_name]
                plt.rcParams['axes.unicode_minus'] = False
                
                sorted_counts = sorted(counts.items(), key=lambda x: x[1])
                cats = [item[0] for item in sorted_counts]
                vals = [item[1] for item in sorted_counts]
                
                color_list = ['#FF6B6B', '#4ECDC4', '#FFD93D', '#6BCB77', '#9B59B6', '#FF8C42', '#3ABEF9', '#F76E9C', '#2ECC71']
                bar_colors = color_list[:len(cats)]
                
                fig, ax = plt.subplots(figsize=(7, 4.5))
                bars = ax.barh(cats, vals, color=bar_colors, edgecolor='white', linewidth=1.5)
                
                for bar, val in zip(bars, vals):
                    ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2, 
                            str(val), va='center', fontsize=11, fontweight='bold', color='#333333')
                
                ax.set_xlabel("薄弱点出现次数", fontsize=11)
                ax.set_title(f"全班薄弱点排行（{start_date} 至 {end_date}）", fontsize=12, fontweight='bold', pad=12)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                plt.tight_layout()
                st.pyplot(fig)
                
                st.info(f"该时间段内共有 {len(data.data)} 条薄弱点记录，涉及 {len(counts)} 个知识点维度")
            else:
                st.info("该时间段内暂无数据，请调整时间范围")

                st.markdown("---")
            st.subheader("🔔 课中即时热词（最近30分钟）")
            if st.button("刷新热词"):
                import datetime
                thirty_min_ago = (datetime.datetime.now() - datetime.timedelta(minutes=30)).isoformat()
                data = supabase.table("weakness_log").select("knowledge_point").gte(
                    "created_at", thirty_min_ago
                ).execute()
                if data.data:
                    from collections import Counter
                    points = [row["knowledge_point"] for row in data.data]
                    counts = Counter(points)
                    top = counts.most_common(3)
                    for point, cnt in top:
                        if cnt >= 3:
                            st.error(f"⚠️ 高频问题：**{point}**（{cnt}次）——建议暂停操作，集中讲解")
                        else:
                            st.info(f"📌 {point}（{cnt}次）")
                else:
                    st.success("当前无高频问题，课堂进展顺利")
                
        # ========== 功能2：教师修正学情画像 ==========
        st.markdown("---")
        st.subheader("📝 教师修正学情画像")
        
        if st.button("加载待标注记录"):
            data = supabase.table("weakness_log").select(
                "id, student_id, student_name, knowledge_point, error_type, teacher_remark"
            ).order("created_at", desc=True).limit(20).execute()
            if data.data:
                st.session_state.pending_records = data.data
            else:
                st.info("暂无记录")
        
        if "pending_records" in st.session_state and st.session_state.pending_records:
            remarks_to_save = {}
            for record in st.session_state.pending_records:
                col1, col2, col3 = st.columns([3, 2, 2])
                with col1:
                    st.write(f"**{record.get('student_name', '未知')}**（{record['student_id']}）：{record['knowledge_point']} - {record['error_type']}")
                with col2:
                    if record.get("teacher_remark"):
                        st.write(f"已标注：**{record['teacher_remark']}**")
                    else:
                        st.write("未标注")
                with col3:
                    default_index = 0
                    if record.get("teacher_remark") in ["未标注", "真实难点", "初学噪声", "已强化"]:
                        default_index = ["未标注", "真实难点", "初学噪声", "已强化"].index(record["teacher_remark"])
                    remark = st.selectbox(
                        "标注",
                        ["未标注", "真实难点", "初学噪声", "已强化"],
                        index=default_index,
                        key=f"remark_{record['id']}",
                        label_visibility="collapsed"
                    )
                    remarks_to_save[record["id"]] = remark
            
            if st.button("💾 批量保存所有标注"):
                saved_count = 0
                for record_id, remark in remarks_to_save.items():
                    if remark != "未标注":
                        supabase.table("weakness_log").update(
                            {"teacher_remark": remark}
                        ).eq("id", record_id).execute()
                        saved_count += 1
                st.success(f"已批量保存 {saved_count} 条标注")
                st.rerun()
        
        # ========== 功能3：本课重难点推荐 ==========
        st.markdown("---")
        st.subheader("🎯 本课重难点推荐")
        
        data = supabase.table("weakness_log").select("knowledge_point, teacher_remark").execute()
        if data.data:
            from collections import Counter
            # 统计被标记为“真实难点”的记录
            real_difficulties = [
                row["knowledge_point"] for row in data.data 
                if row.get("teacher_remark") == "真实难点"
            ]
            if real_difficulties:
                counts = Counter(real_difficulties)
                top = counts.most_common(1)[0]
                st.warning(f"**教学难点建议**：{top[0]}（被标记为真实难点 {top[1]} 次）")
                
                # 全班最高频薄弱点作为重点建议
                all_points = [row["knowledge_point"] for row in data.data]
                all_counts = Counter(all_points)
                top_all = all_counts.most_common(1)[0]
                st.info(f"**教学重点建议**：{top_all[0]}（全班高频薄弱点，出现 {top_all[1]} 次）")
            else:
                st.info("暂无标记为“真实难点”的记录，请先在上方完成标注")
        else:
            st.info("暂无数据")

         # ========== 功能3.5：全班学习习惯分析 ==========
        st.markdown("---")
        st.subheader("🧠 全班学习习惯分析")
        if st.button("生成全班学习习惯诊断"):
            with st.spinner("AI正在分析全班学习习惯..."):
                data = supabase.table("weakness_log").select("student_id, student_name, learning_habit").execute()
                habits_all = [row.get("learning_habit", "") for row in data.data if row.get("learning_habit")]
                
                if habits_all:
                    from collections import Counter
                    counts = Counter(habits_all)
                    
                    st.write("**全班学习习惯分布：**")
                    st.bar_chart(counts)
                    
                    habit_summary = "、".join([f"{k}（{v}人）" for k, v in counts.items()])
                    prompt = f"这是一个CAD课程班级的学习习惯统计：{habit_summary}。请分析这个班级整体的学习习惯特点，指出优势、问题和教学改进建议，写一段150字左右的班级学情诊断。"
                    response = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    st.info(response.choices[0].message.content)
                else:
                    st.info("暂无学习习惯记录，请先让学生使用智能体提问")
          # ========== 功能3.6：班级薄弱点热力图 ==========
        st.markdown("---")
        st.subheader("🔥 班级薄弱点热力图")
        if st.button("生成薄弱点热力图"):
            import pandas as pd
            import os
            import matplotlib.pyplot as plt
            from matplotlib import font_manager
            
            # 加载中文字体
            current_dir = os.path.dirname(os.path.abspath(__file__))
            font_path = os.path.join(current_dir, "SourceHanSansCN-Regular.otf")
            font_manager.fontManager.addfont(font_path)
            font_name = font_manager.FontProperties(fname=font_path).get_name()
            plt.rcParams['font.sans-serif'] = [font_name]
            plt.rcParams['axes.unicode_minus'] = False
            
            # 拉取数据
            data = supabase.table("weakness_log").select("knowledge_point, error_type").execute()
            if data.data:
                df = pd.DataFrame(data.data)
                pivot = pd.crosstab(df["knowledge_point"], df["error_type"])
                
                # 画热力图
                fig, ax = plt.subplots(figsize=(8, 6))
                im = ax.imshow(pivot.values, cmap='YlOrRd', aspect='auto')
                
                ax.set_xticks(range(len(pivot.columns)))
                ax.set_yticks(range(len(pivot.index)))
                ax.set_xticklabels(pivot.columns, fontsize=10)
                ax.set_yticklabels(pivot.index, fontsize=10)
                plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
                
                # 在格子中标注数字
                for i in range(len(pivot.index)):
                    for j in range(len(pivot.columns)):
                        val = pivot.values[i, j]
                        if val > 0:
                            ax.text(j, i, str(val), ha="center", va="center", 
                                    color="black" if val < pivot.values.max() * 0.7 else "white",
                                    fontsize=11, fontweight='bold')
                
                plt.title("班级薄弱点热力图（知识点 × 错误类型）", fontsize=13, pad=15)
                plt.colorbar(im, ax=ax, label="出现次数")
                plt.tight_layout()
                st.pyplot(fig)
                
                st.info(f"该热力图基于 {len(data.data)} 条薄弱点记录，横轴为错误类型，纵轴为知识点，颜色越深表示该组合出现次数越多。")
            else:
                st.info("暂无薄弱点数据")
                    
        # ========== 功能4：个人学情查询 + AI评语 ==========
        st.markdown("---")
        query_id = st.text_input("输入学号查询个人学情")
        if query_id:
            data = supabase.table("weakness_log").select("*").eq("student_id", query_id).execute()
            if data.data:
                st.write(f"**学号 {query_id} 的薄弱点记录：**")
                for row in data.data:
                    remark = row.get("teacher_remark", "")
                    st.write(f"- {row['knowledge_point']}：{row['error_type']}" + (f"（教师标注：{remark}）" if remark else ""))

        # ========== 个人能力雷达图 ==========
                st.markdown("---")
                st.write("**该生能力雷达图：**")
                
                import os
                import matplotlib.pyplot as plt
                from matplotlib import font_manager
                
                current_dir = os.path.dirname(os.path.abspath(__file__))
                font_path = os.path.join(current_dir, "SourceHanSansCN-Regular.otf")
                font_manager.fontManager.addfont(font_path)
                font_name = font_manager.FontProperties(fname=font_path).get_name()
                plt.rcParams['font.sans-serif'] = [font_name]
                plt.rcParams['axes.unicode_minus'] = False
                
                categories = ["图层管理", "基础绘图命令", "轴网与墙体", "参数化门窗", "楼梯与垂直交通", "尺寸与文字", "首层构件", "图框与输出", "图纸校审"]
                scores = {cat: 100 for cat in categories}
                for row in data.data:
                    kp = row["knowledge_point"]
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
                plt.title(f"{query_id} 能力雷达图", pad=25, fontsize=14)
                plt.tight_layout()
                st.pyplot(fig)

         # ========== AI学习习惯分析 ==========
                st.markdown("---")
                if st.button("🧠 AI学习习惯分析"):
                    with st.spinner("AI正在分析该生学习习惯..."):
                        habits = [row.get("learning_habit", "") for row in data.data if row.get("learning_habit")]
                        if habits:
                            habit_text = "、".join(habits)
                            prompt = f"这是一个CAD课程学生的学习习惯记录：{habit_text}。请分析该生的学习习惯特点，指出他在学习方式上的优势和需要改进的地方，写一段100字左右的诊断。"
                            response = client.chat.completions.create(
                                model="deepseek-chat",
                                messages=[{"role": "user", "content": prompt}]
                            )
                            st.info(response.choices[0].message.content)
                        else:
                            st.info("该生暂无可分析的学习习惯记录")
                            
                if st.button("🤖 AI生成诊断评语"):
                    with st.spinner("AI正在分析学情..."):
                        record_text = "".join([
                            f"- {row['knowledge_point']}: {row['error_type']}\n" 
                            for row in data.data
                        ])
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
        categories = ["图层管理", "基础绘图命令", "轴网与墙体", "参数化门窗", "楼梯与垂直交通", "尺寸与文字", "首层构件", "图框与输出", "图纸校审"]
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
        if msg["role"] == "assistant":
            st.chat_message(msg["role"], avatar="robot.jpeg").write(msg["content"])
        else:
            st.chat_message(msg["role"], avatar=st.session_state.get("avatar", "👤")).write(msg["content"])

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
    st.chat_message("user", avatar=st.session_state.get("avatar", "👤")).write(user_input)
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
    st.chat_message("assistant", avatar="robot.jpeg").write(reply)
