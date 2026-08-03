(() => {
  "use strict";

  const qs = (selector, root = document) => root.querySelector(selector);
  const qsa = (selector, root = document) => [...root.querySelectorAll(selector)];
  const escapeHtml = (value = "") => String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
  const detailText = payload => {
    const detail = payload && payload.detail;
    const message = typeof detail === "string" ? detail
      : detail && typeof detail.message === "string" ? detail.message
      : detail && typeof detail.code === "string" ? detail.code
      : "请求失败，请稍后重试。";
    return window.CareerI18n?.t(message) || message;
  };
  const apiCall = async (url, options = {}) => {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: {"Content-Type": "application/json"},
      ...options
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(detailText(payload));
    return payload;
  };
  const toast = (message, icon = "check") => CareerUI.toast(message, icon);
  let principal = null;

  async function me() {
    if (!principal) principal = (await apiCall("/api/auth/me")).user || {};
    return principal;
  }

  function setActive(name, label) {
    qsa("[data-teacher-view]").forEach(item => item.classList.toggle("active", item.dataset.teacherView === name));
    const breadcrumb = qs("#teacherBreadcrumb");
    if (breadcrumb) breadcrumb.textContent = label || "总览";
  }

  function openList(title, description, rows, emptyMessage = "暂无数据") {
    return CareerUI.modal({
      title,
      description,
      html: rows.length ? `<div class="workspace-list">${rows.join("")}</div>` :
        `<div class="empty compact-empty"><div><div class="empty-icon"><i data-lucide="inbox"></i></div><h3>${escapeHtml(emptyMessage)}</h3><p>数据产生后会自动显示在这里。</p></div></div>`
    });
  }

  async function currentDashboard() {
    const query = encodeURIComponent(qs("#search")?.value.trim() || "");
    const stage = encodeURIComponent(qs("#stage")?.value || "all");
    return apiCall(`/api/teacher/dashboard?q=${query}&stage=${stage}`);
  }

  async function openUsers(profilesOnly = false) {
    const data = await currentDashboard();
    const rows = (data.sessions || []).map(item => `
      <button class="workspace-row interactive-row" data-open-student="${escapeHtml(item.session_id)}">
        <div><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml([item.school, item.major, item.grade].filter(Boolean).join(" · ") || "画像待完善")}</span></div>
        <div class="row-end"><span class="badge">${escapeHtml(item.stage_label)}</span><i data-lucide="chevron-right"></i></div>
      </button>`);
    const modal = openList(profilesOnly ? "用户画像" : "用户管理", `${rows.length} 名已授权用户`, rows, "当前没有可访问用户");
    qsa("[data-open-student]", modal.element).forEach(button => {
      button.onclick = () => {
        modal.close();
        const row = qs(`[data-id="${CSS.escape(button.dataset.openStudent)}"]`);
        if (row) row.click();
        else toast("用户详情不在当前筛选结果中，请清除筛选后重试", "triangle-alert");
      };
    });
    CareerUI.refreshIcons();
  }

  async function openArtifacts() {
    const data = await currentDashboard();
    const candidates = (data.sessions || []).filter(item => item.has_draft || item.stage === "draft" || item.score != null);
    const details = await Promise.all(candidates.slice(0, 30).map(item =>
      apiCall(`/api/teacher/sessions/${encodeURIComponent(item.session_id)}`).catch(() => null)
    ));
    const rows = details.filter(Boolean).flatMap(detail => {
      const profile = detail.state?.profile || {};
      return (detail.artifacts || []).map(artifact => `
        <button class="workspace-row interactive-row" data-open-student="${escapeHtml(detail.state.session_id)}">
          <div><strong>${escapeHtml(artifact.title)} V${artifact.version}</strong><span>${escapeHtml(profile.name || "未命名用户")} · ${escapeHtml(artifact.kind)}</span></div>
          <span class="badge">${(artifact.evidence_links || []).length} Evidence</span>
        </button>`);
    });
    const modal = openList("成果物中心", `${rows.length} 个版本化成果物`, rows, "当前没有成果物");
    qsa("[data-open-student]", modal.element).forEach(button => {
      button.onclick = () => {
        modal.close();
        const row = qs(`[data-id="${CSS.escape(button.dataset.openStudent)}"]`);
        if (row) row.click();
      };
    });
  }

  async function openPaths() {
    const data = await currentDashboard();
    const sessions = data.sessions || [];
    const stages = new Map();
    sessions.forEach(item => stages.set(item.stage_label, (stages.get(item.stage_label) || 0) + 1));
    const rows = [...stages.entries()].map(([label, count]) => `
      <button class="workspace-row interactive-row" data-stage-label="${escapeHtml(label)}">
        <div><strong>${escapeHtml(label)}</strong><span>${count} 名用户处于该阶段</span></div>
        <i data-lucide="arrow-right"></i>
      </button>`);
    const modal = openList("路径管理", "按真实会话状态观察用户推进路径", rows, "尚无路径数据");
    qsa("[data-stage-label]", modal.element).forEach(button => {
      button.onclick = () => {
        modal.close();
        qs("#progress").scrollIntoView({behavior: "smooth"});
        toast(`已定位路径阶段：${button.dataset.stageLabel}`);
      };
    });
    qs(".career-modal-body", modal.element)?.insertAdjacentHTML("beforeend",
      `<div class="workspace-actions"><button class="btn primary" id="openPlanRecommendations"><i data-lucide="route"></i>生成个性化方案推荐</button></div>`);
    qs("#openPlanRecommendations", modal.element).onclick = () => {
      modal.close();
      openRecommendations().catch(error => toast(error.message, "triangle-alert"));
    };
    CareerUI.refreshIcons();
  }

  async function openAgents() {
    const health = await apiCall("/api/health");
    const tasks = health.tasks || {};
    const rows = Object.entries(tasks).map(([name, config]) => `
      <div class="workspace-row">
        <div><strong>${escapeHtml(name)}</strong><span>${escapeHtml(config.provider_id || config.provider || "未配置 Provider")} · ${escapeHtml(config.model || "未配置模型")}</span></div>
        <span class="badge ${config.enabled ? "success" : ""}">${config.enabled ? "可用" : "未配置"}</span>
      </div>`);
    openList("AI 队友", `当前运行模式：${health.mode || "unknown"}`, rows, "尚未配置 Agent 路由");
  }

  async function openReviews() {
    const data = await currentDashboard();
    const rows = (data.sessions || []).filter(item => item.stage === "draft" || item.score != null).map(item => `
      <div class="workspace-row">
        <div><strong>${escapeHtml(item.name)}</strong><span>${item.score == null ? "成果物待评审" : `最近评分 ${item.score}/100`}</span></div>
        <div class="version-actions">
          <button class="btn small" data-open-student="${escapeHtml(item.session_id)}">查看</button>
          <button class="btn small primary" data-run-review="${escapeHtml(item.session_id)}">${item.score == null ? "开始评审" : "重新评审"}</button>
        </div>
      </div>`);
    const modal = openList("智能评审", "评分由真实 Reviewer 路由执行，不使用前端随机分数", rows, "当前没有待评审成果");
    qsa("[data-open-student]", modal.element).forEach(button => {
      button.onclick = () => {
        modal.close();
        qs(`[data-id="${CSS.escape(button.dataset.openStudent)}"]`)?.click();
      };
    });
    qsa("[data-run-review]", modal.element).forEach(button => {
      button.onclick = async () => {
        button.classList.add("button-busy");
        button.innerHTML = '<i data-lucide="loader-circle"></i>正在评审';
        CareerUI.refreshIcons();
        try {
          const result = await apiCall("/api/review", {
            method: "POST", body: JSON.stringify({session_id: button.dataset.runReview})
          });
          const review = result.review || result.state?.review;
          toast(`评审完成 · ${review?.total_score ?? "—"}/100`);
          modal.close();
          qs(`[data-id="${CSS.escape(button.dataset.runReview)}"]`)?.click();
          if (typeof load === "function") await load();
        } catch (error) {
          toast(error.message, "triangle-alert");
        } finally {
          button.classList.remove("button-busy");
          button.textContent = "重试评审";
        }
      };
    });
    CareerUI.refreshIcons();
  }

  async function openRecommendations() {
    const data = await currentDashboard();
    const rows = (data.sessions || []).map(item => `
      <div class="workspace-row">
        <div><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.target_job || item.track || "目标待明确")} · ${escapeHtml(item.stage_label)}</span></div>
        <button class="btn small primary" data-generate-recommendation="${escapeHtml(item.session_id)}">生成方案推荐</button>
      </div>`);
    const modal = openList("方案推荐", "推荐由 Coach 模型读取该用户已授权画像、Evidence 与成果物后生成", rows, "当前没有可访问用户");
    qsa("[data-generate-recommendation]", modal.element).forEach(button => {
      button.onclick = async () => {
        button.classList.add("button-busy");
        button.innerHTML = '<i data-lucide="loader-circle"></i>正在分析';
        CareerUI.refreshIcons();
        try {
          const detail = await apiCall(`/api/teacher/sessions/${encodeURIComponent(button.dataset.generateRecommendation)}`);
          const subjectUserId = detail.state?.student_user_id || detail.state?.student_id || "";
          if (!subjectUserId) throw new Error("该用户尚未绑定可授权的账户身份，无法跨用户调用 Coach。");
          const result = await apiCall(`/api/workspace/v1/ai/coach?subject_user_id=${encodeURIComponent(subjectUserId)}`, {
            method: "POST",
            body: JSON.stringify({
              mode: "advisor_recommendation",
              message: "请基于该用户已核验的画像、Evidence、成果物和当前工作流，生成一份可执行的职业发展方案推荐。逐项区分已有证据、缺口、下一步任务，禁止补造经历。"
            })
          });
          CareerUI.modal({
            title: "AI 方案推荐",
            description: `${escapeHtml(result.provider_id || "Model Gateway")} · ${escapeHtml(result.model || "configured model")}`,
            html: `<div class="preview" data-i18n-ignore>${escapeHtml(result.reply || "")}</div>
              <div class="workspace-actions"><button class="btn primary" id="useAdvisorRecommendation">写入顾问反馈</button></div>`
          });
          qs("#useAdvisorRecommendation").onclick = async event => {
            event.currentTarget.classList.add("button-busy");
            try {
              await apiCall(`/api/teacher/sessions/${encodeURIComponent(button.dataset.generateRecommendation)}/feedback`, {
                method: "POST",
                body: JSON.stringify({content: result.reply, teacher_name: "CareerOS Advisor", priority: "medium"})
              });
              toast("方案推荐已写入用户 Coach 与任务中心");
              if (typeof load === "function") await load();
            } catch (error) { toast(error.message, "triangle-alert"); }
            finally { event.currentTarget.classList.remove("button-busy"); }
          };
        } catch (error) {
          toast(error.message, "triangle-alert");
        } finally {
          button.classList.remove("button-busy");
          button.textContent = "重新生成";
        }
      };
    });
    CareerUI.refreshIcons();
  }

  async function openTasks() {
    const data = await apiCall("/api/tasks");
    const items = data.tasks || [];
    const rows = items.map(item => `
      <div class="workspace-row">
        <div><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.source || item.task_type)} · ${escapeHtml(item.priority)}</span></div>
        <button class="btn small" data-task-complete="${escapeHtml(item.task_id)}">${["done", "completed"].includes(item.status) ? "重新打开" : "完成"}</button>
      </div>`);
    const modal = openList("AI 任务", `${items.filter(item => !["done", "completed"].includes(item.status)).length} 项待处理`, rows, "当前没有任务");
    qsa("[data-task-complete]", modal.element).forEach(button => {
      button.onclick = async () => {
        button.classList.add("button-busy");
        try {
          const current = items.find(item => item.task_id === button.dataset.taskComplete);
          const nextStatus = ["done", "completed"].includes(current?.status) ? "todo" : "done";
          await apiCall(`/api/tasks/${encodeURIComponent(button.dataset.taskComplete)}`, {
            method: "PATCH", body: JSON.stringify({status: nextStatus})
          });
          if (current) current.status = nextStatus;
          button.textContent = nextStatus === "done" ? "重新打开" : "完成";
          toast(nextStatus === "done" ? "任务已完成" : "任务已重新打开");
          if (typeof load === "function") load();
        } catch (error) {
          toast(error.message, "triangle-alert");
        } finally {
          button.classList.remove("button-busy");
        }
      };
    });
  }

  async function openAnalytics() {
    const data = await currentDashboard();
    const stats = data.stats || {};
    const total = Math.max(1, stats.total_students || 0);
    const metrics = [
      ["画像完成率", stats.profiled || 0],
      ["目标确认率", stats.track_confirmed || 0],
      ["成果完成率", stats.drafted || 0],
      ["评审完成率", stats.reviewed || 0],
      ["修订完成率", stats.revised || 0]
    ];
    openList("数据分析", "基于当前租户与教师授权范围实时计算", metrics.map(([label, value]) => `
      <div class="workspace-row">
        <div><strong>${label}</strong><span>${value} / ${stats.total_students || 0} 名用户</span></div>
        <strong class="tabular">${Math.round(value / total * 100)}%</strong>
      </div>`), "当前没有可分析数据");
  }

  async function openAdmin(section) {
    const user = await me();
    const role = user.canonical_role || user.role;
    if (!user.is_super_admin && !["organization_admin", "school_admin", "platform_admin", "super_admin"].includes(role)) {
      return CareerUI.modal({
        title: section === "knowledge" ? "知识库" : "模型与设置",
        description: "当前账户没有系统管理权限",
        html: `<div class="inline-error"><strong>需要学校管理员权限</strong><span>教师可使用知识与模型能力，但不能修改学校级配置。</span><small>如需变更，请联系学校管理员。</small></div>`
      });
    }
    location.href = `/admin#${section}`;
  }

  function openHelp() {
    CareerUI.modal({
      title: "教师工作台帮助",
      description: "常用操作均会写入真实用户会话、任务或教师反馈记录",
      html: `<div class="workspace-list">
        <div class="workspace-row"><div><strong>查看用户</strong><span>点击关注项或用户表格行，打开 Inspector。</span></div></div>
        <div class="workspace-row"><div><strong>教师干预</strong><span>在 Inspector 中填写反馈并生成用户待办。</span></div></div>
        <div class="workspace-row"><div><strong>智能评审</strong><span>进入待评审用户，查看 Reviewer 评分与 Evidence 关联。</span></div></div>
        <div class="workspace-row"><div><strong>权限边界</strong><span>教师只能访问被授权班级；系统设置需要学校管理员权限。</span></div></div>
      </div>`
    });
  }

  async function openAccount() {
    const user = await me();
    CareerUI.modal({
      title: "账户",
      description: user.email || "当前账户",
      html: `<div class="workspace-list">
        <div class="workspace-row"><span>姓名</span><strong>${escapeHtml(user.display_name || "Advisor")}</strong></div>
        <div class="workspace-row"><span>角色</span><strong>${escapeHtml(user.canonical_role || user.role || "teacher")}</strong></div>
        <div class="workspace-row"><span>组织</span><strong>${escapeHtml(user.tenant_id || "—")}</strong></div>
      </div>
      <div class="workspace-actions"><button class="btn danger-outline" id="teacherLogout"><i data-lucide="log-out"></i>退出登录</button></div>`
    });
    qs("#teacherLogout").onclick = async () => {
      await apiCall("/api/auth/logout", {method: "POST", body: "{}"});
      location.href = "/login";
    };
    CareerUI.refreshIcons();
  }

  async function openNotifications() {
    const data = await currentDashboard();
    const attention = (data.sessions || []).filter(item => (item.risk_flags || []).length);
    openList("通知与关注", `${attention.length} 名用户需要处理`, attention.map(item => `
      <button class="workspace-row interactive-row" data-open-student="${escapeHtml(item.session_id)}">
        <div><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml((item.risk_flags || []).join(" · "))}</span></div>
        <span class="badge warning">需处理</span>
      </button>`), "当前没有需要处理的通知");
    qsa("[data-open-student]", qs(".career-modal")).forEach(button => {
      button.onclick = () => qs(`[data-id="${CSS.escape(button.dataset.openStudent)}"]`)?.click();
    });
  }

  function openCreateTask() {
    CareerUI.modal({
      title: "新建任务",
      description: "任务将保存到当前租户的 AI Task Center",
      html: `<div class="workspace-form">
        <label>任务名称</label>
        <input class="input" id="teacherTaskTitle" placeholder="例如：复核本周待评审成果">
        <label>优先级</label>
        <select class="select" id="teacherTaskPriority"><option value="normal">普通</option><option value="medium">中</option><option value="high">高</option></select>
        <button class="btn primary" id="saveTeacherTask"><i data-lucide="plus"></i>创建任务</button>
      </div>`
    });
    qs("#saveTeacherTask").onclick = async event => {
      const button = event.currentTarget;
      const title = qs("#teacherTaskTitle").value.trim();
      if (!title) return toast("请输入任务名称", "triangle-alert");
      button.disabled = true;
      try {
        await apiCall("/api/tasks", {method: "POST", body: JSON.stringify({
          title,
          task_type: "teacher_custom",
          priority: qs("#teacherTaskPriority").value,
          payload: {source_ui: "teacher_workspace"}
        })});
        qs(".career-modal-backdrop")?.classList.remove("open");
        toast("任务已创建");
        if (typeof load === "function") await load();
      } catch (error) {
        button.disabled = false;
        toast(error.message, "triangle-alert");
      }
    };
    CareerUI.refreshIcons();
  }

  const handlers = {
    overview: async () => {
      setActive("overview", "总览");
      qs("#overview").scrollIntoView({behavior: "smooth"});
      if (typeof load === "function") await load();
      toast("总览已刷新");
    },
    users: () => { setActive("users", "用户管理"); return openUsers(false); },
    profiles: () => { setActive("profiles", "用户画像"); return openUsers(true); },
    artifacts: () => { setActive("artifacts", "成果物中心"); return openArtifacts(); },
    paths: () => { setActive("paths", "路径管理"); return openPaths(); },
    agents: () => { setActive("agents", "AI 队友"); return openAgents(); },
    reviews: () => { setActive("reviews", "智能评审"); return openReviews(); },
    tasks: () => { setActive("tasks", "AI 任务"); return openTasks(); },
    analytics: () => { setActive("analytics", "数据分析"); return openAnalytics(); },
    knowledge: () => openAdmin("knowledge"),
    settings: () => openAdmin("models")
  };

  qsa("[data-teacher-view]").forEach(item => {
    item.addEventListener("click", async event => {
      event.preventDefault();
      const handler = handlers[item.dataset.teacherView];
      if (!handler) return toast("当前模块未绑定操作，请刷新后重试", "triangle-alert");
      item.setAttribute("aria-busy", "true");
      try { await handler(); } catch (error) { toast(error.message, "triangle-alert"); }
      finally { item.removeAttribute("aria-busy"); }
    });
  });

  qs("#workspaceSelect")?.addEventListener("click", async () => {
    const [user, contract] = await Promise.all([me(), apiCall("/api/workspace/v1/modules")]);
    const enabled = (contract.modules || []).filter(item => item.enabled).length;
    CareerUI.modal({
      title: "当前工作区",
      description: "工作区由账户角色与租户授权决定",
      html: `<div class="workspace-list">
        <div class="workspace-row"><div><strong>CareerOS AI 工作台</strong><span>${escapeHtml(user.tenant_id || "当前组织")} · ${escapeHtml(user.canonical_role || user.role || "teacher")} · ${enabled} 个可用模块</span></div><span class="badge success">当前</span></div>
      </div>`
    });
  });
  qs("#teacherHelp")?.addEventListener("click", openHelp);
  qs("#teacherNotifications")?.addEventListener("click", () => openNotifications().catch(error => toast(error.message, "triangle-alert")));
  qs("#teacherAccount")?.addEventListener("click", () => openAccount().catch(error => toast(error.message, "triangle-alert")));
  qs("#topAdvisorAvatar")?.addEventListener("click", () => openAccount().catch(error => toast(error.message, "triangle-alert")));
  if (qs("#newTask")) qs("#newTask").onclick = openCreateTask;

  document.addEventListener("click", event => {
    const metric = event.target.closest(".metric");
    if (metric) {
      const label = qs(".metric-label", metric)?.textContent || "指标";
      if (label.includes("关注")) return handlers.users();
      if (label.includes("评审")) return handlers.reviews();
      if (label.includes("修订")) return handlers.artifacts();
      return handlers.analytics();
    }
    const task = event.target.closest("#aiActivity .activity-item");
    if (task) handlers.tasks().catch(error => toast(error.message, "triangle-alert"));
    const progress = event.target.closest("#funnel .progress-row");
    if (progress) {
      const label = progress.querySelector("span")?.textContent || "进度阶段";
      CareerUI.modal({
        title: `${label} · 进度钻取`,
        description: "数据来自当前教师授权范围",
        html: `<div class="workspace-list"><div class="workspace-row"><span>完成比例</span><strong>${escapeHtml(progress.querySelector(".pct")?.textContent || "—")}</strong></div></div>
          <div class="workspace-actions"><button class="btn primary" id="viewProgressUsers">查看相关用户</button></div>`
      });
      qs("#viewProgressUsers").onclick = () => openUsers(false).catch(error => toast(error.message, "triangle-alert"));
    }
  });
})();
