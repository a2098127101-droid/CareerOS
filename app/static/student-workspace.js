(() => {
  "use strict";

  const qs = (selector, root = document) => root.querySelector(selector);
  const qsa = (selector, root = document) => [...root.querySelectorAll(selector)];
  const escapeHtml = (value = "") => String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
  const detailText = payload => {
    const detail = payload && payload.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail.message === "string") return detail.message;
    if (detail && typeof detail.code === "string") return detail.code;
    return "请求失败，请稍后重试。";
  };
  const api = async (url, options = {}) => {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: options.body instanceof FormData ? {} : {"Content-Type": "application/json"},
      ...options
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(detailText(payload));
    return payload;
  };
  const toast = (message, icon = "check") => CareerUI.toast(message, icon);
  const sessionId = () => {
    try { return localStorage.getItem("cc_student_session") || ""; } catch (_) { return ""; }
  };

  function setActiveView(name) {
    qsa("[data-student-view]").forEach(item => item.classList.toggle("active", item.dataset.studentView === name));
  }

  function modalList(title, description, rows, emptyMessage = "暂无数据") {
    const html = rows.length
      ? `<div class="workspace-list">${rows.join("")}</div>`
      : `<div class="empty compact-empty"><div><div class="empty-icon"><i data-lucide="inbox"></i></div><h3>${escapeHtml(emptyMessage)}</h3><p>继续使用 Career Coach 后，相关记录会出现在这里。</p></div></div>`;
    return CareerUI.modal({title, description, html});
  }

  async function loadWorkspace() {
    return api("/api/workspace/v1/bootstrap");
  }

  async function openExploration() {
    setActiveView("exploration");
    const data = await loadWorkspace();
    const rows = (data.evidence || []).map(item => `
      <div class="workspace-row">
        <div><strong>${escapeHtml(item.title || "成长证据")}</strong><span>${escapeHtml(item.action || item.proof || "未填写内容")}</span></div>
        <span class="badge ${item.verified ? "success" : ""}">${item.verified ? "已核验" : "待核验"}</span>
      </div>`);
    const modal = modalList("自我探索", `${rows.length} 条可追溯成长证据`, rows, "尚未记录成长证据");
    const body = qs(".career-modal-body", modal.element);
    body.insertAdjacentHTML("afterbegin", `
      <div class="workspace-form">
        <label>新增真实经历或能力证据</label>
        <input class="input" id="explorationTitle" placeholder="例如：社区调研项目">
        <textarea class="textarea" id="explorationAction" placeholder="只填写真实发生的职责、过程与结果"></textarea>
        <button class="btn primary" id="saveExploration"><i data-lucide="plus"></i>保存证据</button>
      </div>`);
    qs("#saveExploration", body).onclick = async event => {
      const button = event.currentTarget;
      const titleValue = qs("#explorationTitle", body).value.trim();
      const action = qs("#explorationAction", body).value.trim();
      if (!titleValue || !action) return toast("请完整填写证据标题与内容", "triangle-alert");
      button.disabled = true;
      try {
        await api("/api/workspace/v1/evidence", {method: "POST", body: JSON.stringify({
          title: titleValue, action, proof: "", capabilities: [], verified: false
        })});
        modal.close();
        toast("成长证据已保存");
      } catch (error) {
        toast(error.message, "triangle-alert");
      } finally {
        button.disabled = false;
      }
    };
    CareerUI.refreshIcons();
  }

  async function openPositioning() {
    setActiveView("positioning");
    const data = await loadWorkspace();
    const profile = data.session?.profile || {};
    CareerUI.modal({
      title: "职业定位",
      description: "基于当前画像与事实材料推进目标聚焦",
      html: `<div class="workspace-list">
        ${[
          ["目标方向", profile.target_job || "尚未明确"],
          ["目标行业", profile.target_industry || "尚未明确"],
          ["期望城市", (profile.target_cities || []).join("、") || "尚未明确"],
          ["当前阶段", data.session?.stage || "profile"]
        ].map(item => `<div class="workspace-row"><span>${item[0]}</span><strong>${escapeHtml(item[1])}</strong></div>`).join("")}
      </div>
      <div class="workspace-form">
        <label>让 Coach 继续完成定位</label>
        <textarea class="textarea" id="positioningPrompt" placeholder="例如：我希望聚焦用户研究，请结合已有证据追问我仍缺少的信息。"></textarea>
        <button class="btn primary" id="continuePositioning"><i data-lucide="arrow-right"></i>回到 Coach 推进</button>
      </div>`
    });
    qs("#continuePositioning").onclick = () => {
      const prompt = qs("#positioningPrompt").value.trim() || "请基于我的现有画像继续完成职业定位，并只追问缺少的事实。";
      qs("#input").value = prompt;
      qs("#coach").scrollIntoView({behavior: "smooth"});
      qs("#input").focus();
      toast("定位任务已放入输入框，请发送后继续");
    };
    CareerUI.refreshIcons();
  }

  async function openCapabilities() {
    setActiveView("capabilities");
    let items = [];
    let unavailable = "";
    try {
      const result = await api("/api/domain/v1/capabilities");
      items = result.items || [];
    } catch (error) {
      unavailable = error.message;
    }
    const rows = items.map(item => `
      <div class="workspace-row">
        <div><strong>${escapeHtml(item.capability_label || item.capability_id || "能力项")}</strong>
        <span>${escapeHtml(item.explanation || item.status || "等待分析")}</span></div>
        <span class="badge">${escapeHtml(item.level || item.status || "未评估")}</span>
      </div>`);
    const modal = modalList("能力画像", unavailable ? `当前状态：${unavailable}` : `${rows.length} 项证据化能力判断`, rows, "尚未生成能力画像");
    const body = qs(".career-modal-body", modal.element);
    body.insertAdjacentHTML("beforeend", `
      <div class="workspace-actions">
        <button class="btn primary" id="recomputeCapabilities"><i data-lucide="refresh-cw"></i>重新计算画像</button>
        <span class="meta">计算只使用当前 Evidence 与岗位要求，不会把岗位要求当作个人能力。</span>
      </div>`);
    qs("#recomputeCapabilities", body).onclick = async event => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        await api("/api/domain/v1/recompute", {method: "POST", body: JSON.stringify({job_id: "", reason: "student workspace recompute"})});
        modal.close();
        toast("能力画像已重新计算");
      } catch (error) {
        toast(error.message, "triangle-alert");
      } finally {
        button.disabled = false;
      }
    };
    CareerUI.refreshIcons();
  }

  async function openTasks() {
    setActiveView("tasks");
    const data = await api("/api/workspace/v1/tasks");
    const items = data.items || [];
    const rows = items.map(item => `
      <div class="workspace-row">
        <div><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.description || item.originType || "行动任务")}</span></div>
        <button class="btn small" data-complete-task="${escapeHtml(item.id)}" ${item.status === "done" ? "disabled" : ""}>${item.status === "done" ? "已完成" : "标记完成"}</button>
      </div>`);
    const modal = modalList("行动计划", `${items.filter(item => item.status !== "done").length} 项待推进任务`, rows, "当前没有行动任务");
    qsa("[data-complete-task]", modal.element).forEach(button => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          const item = items.find(candidate => candidate.id === button.dataset.completeTask);
          await api(`/api/workspace/v1/tasks/${encodeURIComponent(item.id)}`, {
            method: "PATCH",
            body: JSON.stringify({...item, status: "done", expected_version: item._version})
          });
          button.textContent = "已完成";
          toast("任务已完成");
        } catch (error) {
          button.disabled = false;
          toast(error.message, "triangle-alert");
        }
      };
    });
  }

  async function openArtifacts() {
    setActiveView("artifacts");
    const data = await api("/api/workspace/v1/artifacts");
    const items = data.items || [];
    const rows = items.map(item => `
      <div class="workspace-row">
        <div><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.type)} · V${item._version || 1}</span></div>
        <button class="btn small" data-download-artifact="${escapeHtml(item.id)}">导出</button>
      </div>`);
    const modal = modalList("简历 / 报告", `${items.length} 个当前版本成果物`, rows, "尚未生成成果物");
    const body = qs(".career-modal-body", modal.element);
    body.insertAdjacentHTML("beforeend", `
      <div class="workspace-actions">
        <button class="btn primary" id="generateArtifact"><i data-lucide="file-plus-2"></i>让 Coach 生成成果</button>
      </div>`);
    qs("#generateArtifact", body).onclick = () => {
      modal.close();
      qs("#input").value = "请基于我已确认的事实材料生成适合当前阶段的成果物，不要补造经历。";
      qs("#input").focus();
      toast("生成任务已放入输入框");
    };
    qsa("[data-download-artifact]", body).forEach(button => {
      button.onclick = () => {
        const item = items.find(candidate => candidate.id === button.dataset.downloadArtifact);
        const anchor = document.createElement("a");
        anchor.href = URL.createObjectURL(new Blob([item.content || ""], {type: "text/plain;charset=utf-8"}));
        anchor.download = `${item.title || "CareerOS成果"}_V${item._version || 1}.txt`;
        anchor.click();
        URL.revokeObjectURL(anchor.href);
        toast("成果物已导出");
      };
    });
    CareerUI.refreshIcons();
  }

  async function openReview() {
    setActiveView("review");
    const sid = sessionId();
    const stateData = sid ? await api(`/api/sessions/${encodeURIComponent(sid)}`) : (await loadWorkspace()).session;
    const review = stateData.review;
    CareerUI.modal({
      title: "成果评审",
      description: review ? `最近一次严格评审：${review.total_score}/100` : "当前成果尚未完成严格评审",
      html: review ? `<div class="workspace-list">
        ${(review.dimensions || []).map(item => `<div class="workspace-row"><span>${escapeHtml(item.name)}</span><strong>${item.score}/20</strong></div>`).join("")}
        <div class="preview">${escapeHtml(review.overall_comment || "评审已完成")}</div>
      </div>` : `<div class="empty compact-empty"><div><div class="empty-icon"><i data-lucide="scan-search"></i></div><h3>暂无评审结果</h3><p>先生成成果物，再发起严格评审。</p></div></div>
      <div class="workspace-actions"><button class="btn primary" id="startReview">开始严格评审</button></div>`
    });
    const button = qs("#startReview");
    if (button) button.onclick = () => {
      qs("#input").value = "请对当前成果物进行严格评审，给出证据、问题和可执行修改建议。";
      qs("#input").focus();
      toast("评审任务已放入输入框");
    };
    CareerUI.refreshIcons();
  }

  function openInterview() {
    setActiveView("interview");
    CareerUI.modal({
      title: "模拟面试",
      description: "回答将通过已配置的 Reviewer 模型进行真实评估；未配置模型时会明确报错，不生成虚假评分。",
      html: `<div class="workspace-form">
        <label>面试题</label>
        <textarea class="textarea" id="interviewQuestion">请介绍一次最能证明你目标岗位能力的真实经历。</textarea>
        <label>你的回答</label>
        <textarea class="textarea tall" id="interviewAnswer" placeholder="请输入真实回答，避免加入无法核验的经历或数据。"></textarea>
        <button class="btn primary" id="evaluateInterview"><i data-lucide="mic-2"></i>提交 AI 评估</button>
        <div id="interviewResult" aria-live="polite"></div>
      </div>`
    });
    qs("#evaluateInterview").onclick = async event => {
      const button = event.currentTarget;
      const question = qs("#interviewQuestion").value.trim();
      const answer = qs("#interviewAnswer").value.trim();
      if (!question || !answer) return toast("请填写面试题与回答", "triangle-alert");
      button.disabled = true;
      button.innerHTML = '<i data-lucide="loader-circle"></i>正在评估';
      CareerUI.refreshIcons();
      try {
        const result = await api("/api/workspace/v1/ai/interview/evaluate", {
          method: "POST", body: JSON.stringify({question, answer, target_job: ""})
        });
        const evaluation = result.evaluation;
        qs("#interviewResult").innerHTML = `<div class="review-result"><strong>${evaluation.overall_score}/100</strong>
          <p>${escapeHtml(evaluation.feedback)}</p>
          <div class="evidence-row">${(evaluation.risks || []).map(item => `<span class="badge warning">${escapeHtml(item)}</span>`).join("")}</div>
          <span class="meta">${escapeHtml(result.provider_id)} · ${escapeHtml(result.model)}</span></div>`;
        toast("面试评估已完成");
      } catch (error) {
        qs("#interviewResult").innerHTML = `<div class="inline-error"><strong>评估未完成</strong><span>${escapeHtml(error.message)}</span><small>请检查 Reviewer 模型路由或稍后重试。</small></div>`;
        toast(error.message, "triangle-alert");
      } finally {
        button.disabled = false;
        button.innerHTML = '<i data-lucide="mic-2"></i>重新评估';
        CareerUI.refreshIcons();
      }
    };
    CareerUI.refreshIcons();
  }

  async function openNotifications() {
    const data = await api("/api/workspace/v1/tasks");
    const items = (data.items || []).filter(item => item.status !== "done");
    modalList("通知与待办", `${items.length} 项未完成任务`, items.map(item => `
      <div class="workspace-row"><div><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.description || item.originType)}</span></div><span class="badge">${escapeHtml(item.priority)}</span></div>
    `), "当前没有待办通知");
  }

  async function openAccount() {
    const me = await api("/api/auth/me");
    const user = me.user || {};
    CareerUI.modal({
      title: "账户与隐私",
      description: user.email || "当前账户",
      html: `<div class="workspace-list">
        <div class="workspace-row"><span>姓名</span><strong>${escapeHtml(user.display_name || "用户")}</strong></div>
        <div class="workspace-row"><span>角色</span><strong>${escapeHtml(user.canonical_role || user.role || "student")}</strong></div>
        <div class="workspace-row"><span>组织</span><strong>${escapeHtml(user.tenant_id || "—")}</strong></div>
      </div>
      <div class="workspace-actions">
        <button class="btn" id="privacyExport"><i data-lucide="download"></i>导出我的数据</button>
        <button class="btn danger-outline" id="studentLogout"><i data-lucide="log-out"></i>退出登录</button>
      </div>`
    });
    qs("#privacyExport").onclick = () => { location.href = "/api/privacy/export"; };
    qs("#studentLogout").onclick = async () => {
      await api("/api/auth/logout", {method: "POST", body: "{}"});
      location.href = "/login";
    };
    CareerUI.refreshIcons();
  }

  function openNewConversation() {
    CareerUI.modal({
      title: "开始新对话",
      description: "新对话会创建独立规划会话，当前会话与成果历史仍保留。",
      html: `<div class="inline-error"><strong>确认切换会话</strong><span>新会话将从自我探索开始，不会删除现有 Evidence 或 Artifact。</span></div>
      <div class="workspace-actions"><button class="btn primary" id="confirmNewConversation"><i data-lucide="square-pen"></i>创建并切换</button></div>`
    });
    qs("#confirmNewConversation").onclick = async event => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        try { localStorage.removeItem("cc_student_session"); } catch (_) {}
        const created = await api("/api/sessions", {method: "POST", body: "{}"});
        try { localStorage.setItem("cc_student_session", created.session_id); } catch (_) {}
        toast("新对话已创建");
        location.reload();
      } catch (error) {
        button.disabled = false;
        toast(error.message, "triangle-alert");
      }
    };
    CareerUI.refreshIcons();
  }

  const handlers = {
    coach: () => { setActiveView("coach"); qs("#coach").scrollIntoView({behavior: "smooth"}); qs("#input").focus(); },
    history: () => { setActiveView("history"); qs("#messages").scrollIntoView({behavior: "smooth"}); toast("已定位到对话记录"); },
    exploration: openExploration,
    positioning: openPositioning,
    capabilities: openCapabilities,
    tasks: openTasks,
    artifacts: openArtifacts,
    review: openReview,
    interview: openInterview
  };

  qsa("[data-student-view]").forEach(item => {
    item.addEventListener("click", async event => {
      event.preventDefault();
      const handler = handlers[item.dataset.studentView];
      if (!handler) return toast("该模块暂不可用", "triangle-alert");
      item.setAttribute("aria-busy", "true");
      try { await handler(); } catch (error) { toast(error.message, "triangle-alert"); }
      finally { item.removeAttribute("aria-busy"); }
    });
  });

  qsa("[data-inspector-view]").forEach(tab => {
    tab.onclick = async () => {
      qsa("[data-inspector-view]").forEach(item => item.classList.toggle("active", item === tab));
      if (tab.dataset.inspectorView === "progress") return qs("#stageList").scrollIntoView({behavior: "smooth", block: "center"});
      if (tab.dataset.inspectorView === "profile") return openPositioning();
      return openArtifacts();
    };
  });

  qs("#studentNotifications")?.addEventListener("click", () => openNotifications().catch(error => toast(error.message, "triangle-alert")));
  qs("#studentAccount")?.addEventListener("click", () => openAccount().catch(error => toast(error.message, "triangle-alert")));
  qs("#studentAvatar")?.addEventListener("click", () => openAccount().catch(error => toast(error.message, "triangle-alert")));
  if (qs("#newSession")) qs("#newSession").onclick = openNewConversation;
  qs("#mobileProfile")?.addEventListener("click", event => {
    event.stopImmediatePropagation();
    openPositioning().catch(error => toast(error.message, "triangle-alert"));
  }, true);
})();
