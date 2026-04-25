# Resume Tailor — 一键配置 Prompt

把下面这整段 prompt 复制粘贴给 **Claude Code** 或 **Codex**，AI 会引导你完成全部配置，不需要手动编辑任何文件。

---

````
你是我的 resume-tailor 配置助手。我已经把项目 clone 到本地，现在需要你帮我完成全部配置，让我可以直接运行。

请按以下顺序一步步来，每一步完成之后再进行下一步，不要跳步。

---

## 第零步：检查环境

先运行这些命令，告诉我每项是否就绪：

1. `python3 --version`（需要 3.11+）
2. `claude --version`（Claude Code CLI）
3. `which pdflatex || which xelatex`（LaTeX，可选）
4. `pip install -r requirements.txt`

如果 Python 不满足版本要求，告诉我怎么升级。
如果 `claude` 命令找不到，告诉我去 https://claude.ai/code 下载安装。
如果 LaTeX 没有，告诉我这只影响 PDF 生成，可以用 --no-pdf 跳过，之后要装的话运行 `brew install --cask basictex`。

---

## 第一步：配置 profile.yaml

我需要你通过问答帮我写 profile.yaml。请**逐一**问我下面这 5 个问题，每次只问一个，等我回答后再问下一个：

1. **你叫什么名字？**（用于求职信署名）

2. **用 2-3 句话介绍你的背景：你学过什么、做过什么，你的背景有什么不寻常的地方？**
   （不要写官方简历语言，说真实的。例："我在X大学读了计算机和经济双学位，然后在Y公司做了两年数据分析，主要处理供应链问题。"）

3. **你为什么想做这类工作？说一个真实的原因，不用说得好听。**
   （例："我在实习时发现大家都在做同样的 Excel 模型但结论不一样，想搞清楚为什么。"）

4. **你的核心优势是什么——你能做到而同领域大多数候选人做不到的事？**
   （要具体，不要写"沟通能力强""学习速度快"。例："我能同时读中英文政策原文，不依赖翻译，这让我在分析中国监管政策时比大多数外资分析师准确很多。"）

5. **你做过的最得意的一件事？要具体，有数字或结果更好。**
   （例："帮导师清洗了20万条社交媒体数据，最后这篇论文发表在了X期刊。"）

收集完 5 个回答后，把 profile.example.yaml 复制为 profile.yaml，并用我的回答填写每个字段。写完后把文件内容展示给我确认。

---

## 第二步：配置 story_bank.yaml

故事库是求职信的核心。我需要你帮我写 3-5 个真实职业故事，每个故事用于不同类型的岗位。

请先解释一下什么是好故事：
- 一个具体的时刻，不是泛泛的总结
- 2-4 句话，说清楚你观察到什么、做了什么、意识到什么
- 不用写得完美，听起来真实比听起来好看更重要

然后问我：

"你有哪些真实的职业/学术时刻可以作为故事？随便说几个，不用完整，关键词也行。比如：'在X公司发现了一个别人都忽视的问题'，'帮导师做了一件很枯燥但重要的事'，'一个项目最后做出了意想不到的结果'。"

根据我提供的素材，帮我写出 3-5 个故事，每个故事格式如下：
- id：英文短标识（如 first_real_insight）
- tags：2-5 个标签，从这里选：consulting, finance, research, data, policy, tech, engineering, leadership, due-diligence, modeling, strategy, startup, esg, pm, china, climate
- text：2-4 句话的故事正文，第一人称，具体，有场景感

写完后把每个故事展示给我，让我确认或修改，然后把 story_bank.example.yaml 复制为 story_bank.yaml 并写入。

---

## 第三步：准备简历

问我：**你的简历现在是什么格式？**

---

**情况 A：有 .tex 文件**
让我把文件路径告诉你，或者把内容粘贴给你。把文件放到 resumes/ 目录下，确认能找到 `\documentclass` 和 `\end{document}`，然后继续第四步。

---

**情况 B：有 Word 文档（.docx）**
告诉我：`.docx` 可以直接用，工具会自动转换。让我把 .docx 文件放到 resumes/ 目录下。运行：

```bash
python tailor.py --resume resumes/<文件名>.docx --jd "test" --no-cover-letter --no-pdf
```

转换完成后，`resumes/` 里会自动生成同名的 `.tex` 文件，之后用 `.tex` 文件运行即可。

---

**情况 C：想用自己喜欢的 LaTeX 模板**

推荐去 Overleaf 找：https://www.overleaf.com/latex/templates?q=resume

步骤：
1. 在 Overleaf 找到喜欢的模板，点进去
2. 点右上角 **"Open as Template"**，进入编辑器
3. 点左上角菜单 → **Download Source** → 得到 `.zip` 文件
4. 解压，找到主 `.tex` 文件（通常叫 `main.tex` 或模板名.tex），放到 resumes/ 目录下
5. 把文件内容粘贴给我，我帮你用这个模板结构重建简历

---

**情况 D：只有 PDF，或者完全没有简历**

问我以下内容，我来帮你从头建一份：
- 工作/实习经历（每段：公司名、职位、时间、主要做了什么，2-4 件事）
- 教育背景（学校、专业、时间、GPA 可选）
- 技能和工具
- 项目或研究经历（可选）

内置模板可选：
- `resumes/sample_resume.tex` — 通用技术岗（SWE/数据/产品）
- `resumes/template_finance.tex` — 金融/咨询（教育在前，含 Leadership 部分）
- `resumes/template_with_summary.tex` — 有工作经验 / 转行（含 Summary 段）

告诉我你是哪类岗位，我会选对应模板来填写，保存为 `resumes/my_resume.tex`。

---

## 第四步（可选）：写作风格样本

问我：**你有没有自己写的文章、邮件、报告或任何文字作品，可以作为写作风格参考？**

如果有，让我粘贴内容，你帮我保存为 writing_samples/sample.txt。
如果没有，跳过这步，使用默认风格。

---

## 第五步：验证配置

运行下面的命令做一次测试：

```bash
python tailor.py \
  --resume resumes/<我的简历文件名>.tex \
  --jd "Software Engineer. Requirements: Python, SQL, data analysis, problem-solving, collaborative work environment, fast-paced startup." \
  --no-pdf
```

如果成功，展示 output/ 目录里生成了哪些文件，并把 cover_letter.md 的内容展示给我看。

如果失败，把错误信息告诉我并帮我排查。

---

## 完成

配置完成后，给我一个总结：
1. ✅ 哪些步骤完成了
2. ⚠️ 哪些步骤跳过了（以及跳过的原因）
3. 下次使用时的命令是什么（填入我的实际文件名）

格式示例：
```bash
python tailor.py --resume resumes/my_resume.tex --jd <JD的URL或文件路径>
```
````

---

## 使用方法

1. `git clone https://github.com/Waaangjl/resume-tailor && cd resume-tailor`
2. 打开 Claude Code（终端输入 `claude`）或 Codex
3. 把上面代码块内的全部内容复制粘贴进去
4. 按照 AI 的引导一步步完成配置

全程大约 10–15 分钟。
