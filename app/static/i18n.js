(() => {
  "use strict";

  const STORAGE_KEY = "careeros_locale";
  const SUPPORTED = {
    "zh-CN": "简体中文",
    "en-US": "English"
  };

  const EN = {
    "切换主题": "Theme",
    "用户端 · AI Career Coach": "User · AI Career Coach",
    "顾问端 · AI Operations Workspace": "Advisor · AI Operations Workspace",
    "系统端 · Model & Knowledge": "System · Model & Knowledge",
    "让职业发展、成果生产与 AI 协作运行在一个系统里。": "Run career development, artifact production, and AI collaboration in one system.",
    "CareerOS 将用户画像、目标定位、能力映射、成果生成、智能评审、顾问协作与多模型知识库连接成持续推进的工作流，而不是一次性聊天。": "CareerOS connects profiles, career positioning, capability mapping, artifact creation, rigorous review, advisor collaboration, and multi-model knowledge into a continuous workflow.",
    "职业发展、能力证据、成果物与 AI 协作运行在同一工作空间。": "Career development, evidence, artifacts, and AI collaboration in one workspace.",
    "Chat-first 工作台：推进目标、生成成果物、调用智能评审与迭代修订。": "A chat-first workspace for goals, artifacts, rigorous review, and iterative revision.",
    "优先处理需要关注的用户、待评审成果与 AI 标记风险。": "Prioritize users requiring attention, pending reviews, and AI-flagged risks.",
    "管理多模型路由、Fallback、知识投喂、调用统计与安全设置。": "Manage model routing, fallbacks, knowledge ingestion, usage, and security.",
    "新对话": "New conversation",
    "我的发展": "My development",
    "自我探索": "Self exploration",
    "职业定位": "Career positioning",
    "能力画像": "Capability profile",
    "行动计划": "Action plan",
    "成果物": "Artifacts",
    "简历 / 报告": "Resume / Reports",
    "成果评审": "Artifact review",
    "模拟面试": "Mock interview",
    "历史": "History",
    "对话": "Conversations",
    "文件": "Files",
    "附件": "Attachment",
    "发送": "Send",
    "深度分析": "Deep analysis",
    "生成成果": "Generate artifact",
    "当前画像": "Current profile",
    "当前规划进度": "Current progress",
    "工作流": "Workflow",
    "姓名": "Name",
    "学校": "School",
    "专业": "Major",
    "年级": "Year",
    "目标岗位": "Target role",
    "赛道": "Track",
    "当前评分": "Current score",
    "作品预览": "Artifact preview",
    "复制": "Copy",
    "导出": "Export",
    "分析职业方向": "Analyze career direction",
    "推荐发展路径": "Recommend pathway",
    "生成初稿": "Generate draft",
    "严格评审": "Rigorous review",
    "给 Career Coach 发消息...": "Message Career Coach...",
    "搜索对话、任务、文件": "Search conversations, tasks, or files",
    "搜索对话、任务、文件...": "Search conversations, tasks, or files...",
    "分析发展路径": "Analyze development pathway",
    "来自你的事实材料": "From your evidence",
    "当前阶段": "Current stage",
    "探索中": "Exploring",
    "当前按目标定位、能力映射、差距分析与行动计划推进。": "Progress is driven by target positioning, capability mapping, gap analysis, and action planning.",
    "尚未生成成果": "No artifact generated",
    "暂无作品": "No artifacts",
    "进度": "Progress",
    "作品": "Artifacts",
    "画像": "Profile",
    "我": "Me",
    "当前": "Current",
    "目标方向": "Target direction",
    "能力匹配": "Capability matching",
    "差距分析": "Gap analysis",
    "成长路径": "Growth pathway",
    "履历成果": "Resume artifact",
    "发展报告": "Development report",
    "展示材料": "Presentation materials",
    "模拟训练": "Mock training",
    "显示名": "Display name",
    "组织": "Organization",
    "背景方向": "Background",
    "来源": "Source",
    "通用模式": "General mode",
    "未设置": "Not set",
    "职业发展进行中": "Career development in progress",
    "你好，我是 CareerOS AI Coach。你可以从目标方向、已有经历、技能、作品或当前困惑开始；信息不完整也没关系，我会先建立可验证画像，再逐步推进定位、能力差距、行动计划与成果物。": "Hello, I am CareerOS AI Coach. Start with your target direction, experience, skills, artifacts, or current questions. Incomplete information is fine: I will first build a verifiable profile, then guide positioning, gap analysis, action planning, and artifact creation.",
    "建立可核验的经历、兴趣与能力基础。": "Build a verifiable foundation of experience, interests, and capabilities.",
    "收敛发展方向并形成选择依据。": "Narrow the direction and establish decision evidence.",
    "明确职业、岗位或发展机会边界。": "Define the target role and opportunity boundaries.",
    "把个人证据与目标机会要求对应。": "Map personal evidence to target requirements.",
    "识别证据、能力与成果结构缺口。": "Identify evidence, capability, and artifact gaps.",
    "形成可执行的阶段行动方案。": "Create an executable phased action plan.",
    "生成并迭代与目标方向匹配的履历型成果。": "Create and iterate resume artifacts aligned with the target.",
    "形成可追踪证据的职业发展成果。": "Create an evidence-traceable career development report.",
    "形成结构化展示材料并建立证据链。": "Build structured presentation materials with evidence traceability.",
    "进行面试、陈述或问答训练并复盘。": "Practice interviews, presentations, and Q&A with review.",
    "搜索用户、成果、任务或知识": "Search users, artifacts, tasks, or knowledge",
    "总览": "Overview",
    "用户": "Users",
    "用户管理": "User management",
    "用户画像": "User profiles",
    "成果物中心": "Artifact center",
    "路径管理": "Path management",
    "AI 队友": "AI agents",
    "智能评审": "AI review",
    "AI 任务": "AI tasks",
    "数据": "Data",
    "数据分析": "Analytics",
    "资源": "Resources",
    "知识库": "Knowledge base",
    "模型与设置": "Models & settings",
    "帮助": "Help",
    "今日需要关注": "Needs attention today",
    "学生进度": "User progress",
    "用户工作区": "User workspace",
    "查看进度、发展路径、评分与风险；点击用户打开 Inspector。": "Review progress, pathways, scores, and risks. Select a user to open the inspector.",
    "搜索用户、背景、目标方向": "Search users, background, or target",
    "全部阶段": "All stages",
    "新建任务": "Create task",
    "顾问反馈": "Advisor feedback",
    "保存备注": "Save note",
    "生成干预建议": "Create intervention",
    "生成个性化方案推荐": "Generate personalized recommendation",
    "方案推荐": "Plan recommendations",
    "生成方案推荐": "Generate recommendation",
    "重新生成": "Regenerate",
    "写入顾问反馈": "Add to advisor feedback",
    "当前工作区": "Current workspace",
    "通知与关注": "Notifications & attention",
    "退出登录": "Sign out",
    "System": "System",
    "模型配置": "Model configuration",
    "组织与成员": "Organization & members",
    "产品与商业化": "Product & commercialization",
    "模板配置": "Template configuration",
    "组织与权限": "Organization & permissions",
    "岗位数据": "Job data",
    "调用统计": "Usage",
    "安全设置": "Security",
    "返回首页": "Back to home",
    "模型与 Agent 路由": "Models & agent routing",
    "让不同 Agent 绑定不同模型，并通过 Fallback 控制稳定性与成本。": "Bind each agent to independent models and use fallbacks for reliability and cost control.",
    "添加 / 编辑 Provider": "Add / edit provider",
    "保存 Provider": "Save provider",
    "保存": "Save",
    "编辑": "Edit",
    "测试": "Test",
    "删除": "Delete",
    "模型": "Models",
    "主模型与 Fallback 独立配置；业务代码不绑定厂商。": "Primary and fallback models are configured independently; business logic is provider-agnostic.",
    "知识投喂与检索": "Knowledge ingestion & retrieval",
    "规则、岗位、案例与组织资源独立管理，保留权威度、年份、Scope 与优先级。": "Manage rules, jobs, cases, and organization resources with authority, year, scope, and priority metadata.",
    "添加知识源": "Add knowledge source",
    "支持 PDF / DOCX / TXT / MD / CSV / JSON。": "Supports PDF, DOCX, TXT, MD, CSV, and JSON.",
    "拖拽文件到这里，或点击选择": "Drop a file here or click to select",
    "上传后自动解析、切块并加入检索。": "Files are parsed, chunked, and indexed automatically.",
    "开始投喂": "Start ingestion",
    "测试 Hybrid 检索": "Test hybrid retrieval",
    "重建索引": "Rebuild index",
    "岗位结构化数据": "Structured job data",
    "CSV 导入": "CSV import",
    "导入岗位数据": "Import job data",
    "岗位检索测试": "Job search test",
    "检索岗位": "Search jobs",
    "账户安全与密钥": "Account security & secrets",
    "保存 Token": "Save token",
    "组织、成员与分组": "Organization, members & groups",
    "成员": "Members",
    "添加成员": "Add member",
    "邮箱": "Email",
    "角色": "Role",
    "初始密码": "Initial password",
    "创建成员": "Create member",
    "分组": "Groups",
    "新分组名称": "New group name",
    "创建分组": "Create group",
    "分组与成员分配": "Group membership",
    "分配到分组": "Assign to group",
    "产品模式与商业化基础": "Product mode & commercialization",
    "保存产品模式": "Save product mode",
    "应用方案": "Apply plan",
    "工作流模板": "Workflow templates",
    "成果模板": "Artifact templates",
    "权限分配": "Permission assignment",
    "系统工作区": "System workspace",
    "创建模板": "Create template",
    "启用": "Activate",
    "停用": "Deactivate",
    "已启用": "Active",
    "当前版本": "Current version",
    "归档版本": "Archived version",
    "查看差异": "View diff",
    "恢复此版本": "Restore version",
    "提交方案": "Submit plan",
    "方案标题": "Plan title",
    "方案类型": "Plan type",
    "方案内容": "Plan content",
    "证据 ID": "Evidence IDs",
    "提交并创建版本": "Submit & create version",
    "目录": "Directory",
    "版本历史": "Version history",
    "丢分项": "Score gaps",
    "重新打开": "Reopen",
    "已完成": "Completed",
    "完成": "Complete",
    "进行中": "In progress",
    "重试": "Retry",
    "加载中": "Loading",
    "正在读取数据": "Loading data",
    "正在分析": "Analyzing",
    "正在评审": "Reviewing",
    "正在提交": "Submitting",
    "请求已接收": "Request accepted",
    "正在分析上下文与证据": "Analyzing context and evidence",
    "请求失败，请稍后重试。": "Request failed. Please try again.",
    "请输入任务名称": "Enter a task name.",
    "任务已创建": "Task created.",
    "任务状态已更新": "Task status updated.",
    "成长证据已保存": "Evidence saved.",
    "能力画像已重新计算": "Capability profile recalculated.",
    "成果物已导出": "Artifact exported.",
    "成果已提交并创建新版本": "Artifact submitted as a new version.",
    "面试评估已完成": "Interview evaluation completed.",
    "评估未完成": "Evaluation not completed",
    "请检查 Reviewer 模型路由或稍后重试。": "Check the Reviewer model route or try again later.",
    "语言": "Language",
    "导入文件": "Import file",
    "通知": "Notifications",
    "账户": "Account",
    "给 Career Coach 发消息": "Message Career Coach",
    "移动端导航": "Mobile navigation",
    "命令面板": "Command palette",
    "搜索学生、作品、任务、智能体…": "Search users, artifacts, tasks, or agents…",
    "搜索命令": "Search commands",
    "简体中文": "简体中文",
    "English": "English"
  };

  const translations = {"en-US": EN};
  let locale = localStorage.getItem(STORAGE_KEY) || "zh-CN";
  if (!SUPPORTED[locale]) locale = "zh-CN";
  let applying = false;

  const normalize = value => String(value || "").replace(/\s+/g, " ").trim();
  function translateText(value, target = locale) {
    if (target === "zh-CN") return value;
    const normalized = normalize(value);
    if (!normalized) return value;
    return translations[target]?.[normalized] || value;
  }

  function translateNode(node) {
    if (node.nodeType !== Node.TEXT_NODE) return;
    const parent = node.parentElement;
    if (!parent || parent.closest("script,style,code,pre,[data-i18n-ignore]")) return;
    const source = node.__careerosSource ?? node.nodeValue;
    if (node.__careerosSource === undefined) node.__careerosSource = source;
    const leading = source.match(/^\s*/)?.[0] || "";
    const trailing = source.match(/\s*$/)?.[0] || "";
    const translated = translateText(source);
    node.nodeValue = `${leading}${translated.trim()}${trailing}`;
  }

  function translateAttributes(element) {
    for (const attr of ["placeholder", "title", "aria-label"]) {
      if (!element.hasAttribute(attr)) continue;
      const key = `careerosOriginal${attr.replace("-", "")}`;
      if (element.dataset[key] === undefined) element.dataset[key] = element.getAttribute(attr) || "";
      element.setAttribute(attr, translateText(element.dataset[key]));
    }
  }

  function apply(root = document.body) {
    if (!root || applying) return;
    applying = true;
    try {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      nodes.forEach(translateNode);
      if (root.nodeType === Node.ELEMENT_NODE) translateAttributes(root);
      root.querySelectorAll?.("input,textarea,button,a,[title],[aria-label]").forEach(translateAttributes);
      document.documentElement.lang = locale;
      document.documentElement.dir = "ltr";
      document.querySelectorAll("[data-locale-current]").forEach(node => {
        node.textContent = SUPPORTED[locale];
      });
    } finally {
      applying = false;
    }
  }

  function setLocale(next) {
    if (!SUPPORTED[next] || next === locale) return;
    locale = next;
    localStorage.setItem(STORAGE_KEY, locale);
    apply(document.body);
    window.dispatchEvent(new CustomEvent("careeros:localechange", {detail: {locale}}));
    window.CareerUI?.toast(`${translateText("语言")}: ${SUPPORTED[locale]}`, "languages");
  }

  function installControl() {
    if (document.querySelector("[data-language-control]")) return;
    const control = document.createElement("div");
    control.className = "language-switcher";
    control.dataset.languageControl = "true";
    control.innerHTML = `
      <button class="icon-btn language-trigger" type="button" aria-label="语言" aria-haspopup="menu" aria-expanded="false">
        <i data-lucide="globe-2"></i>
      </button>
      <div class="language-menu" role="menu">
        ${Object.entries(SUPPORTED).map(([code, label]) =>
          `<button type="button" role="menuitemradio" data-set-locale="${code}" aria-checked="${code === locale}">
            <span>${label}</span><i data-lucide="${code === locale ? "check" : "circle"}"></i>
          </button>`).join("")}
      </div>`;
    const host = document.querySelector(".top-actions")
      || document.querySelector(".auth-panel")
      || document.querySelector(".landing-main")
      || document.body;
    if (host.classList.contains("top-actions")) host.prepend(control);
    else {
      control.classList.add("language-switcher-floating");
      host.append(control);
    }
    const trigger = control.querySelector(".language-trigger");
    trigger.addEventListener("click", event => {
      event.stopPropagation();
      const open = control.classList.toggle("open");
      trigger.setAttribute("aria-expanded", String(open));
    });
    control.querySelectorAll("[data-set-locale]").forEach(button => {
      button.addEventListener("click", () => {
        setLocale(button.dataset.setLocale);
        control.remove();
        installControl();
        apply(document.body);
      });
    });
    document.addEventListener("click", event => {
      if (!control.contains(event.target)) {
        control.classList.remove("open");
        trigger.setAttribute("aria-expanded", "false");
      }
    });
    window.CareerUI?.refreshIcons();
  }

  const observer = new MutationObserver(records => {
    if (applying) return;
    records.forEach(record => record.addedNodes.forEach(node => {
      if (node.nodeType === Node.TEXT_NODE) translateNode(node);
      if (node.nodeType === Node.ELEMENT_NODE) apply(node);
    }));
  });

  window.CareerI18n = {
    locale: () => locale,
    supported: () => ({...SUPPORTED}),
    setLocale,
    apply,
    t: translateText,
    agentInstruction: () => locale === "en-US"
      ? "Respond in English. Keep evidence IDs and source titles unchanged."
      : "请使用简体中文回答，并保留 Evidence ID 与来源标题。"
  };

  document.addEventListener("DOMContentLoaded", () => {
    installControl();
    apply(document.body);
    observer.observe(document.body, {childList: true, subtree: true});
  });
})();
