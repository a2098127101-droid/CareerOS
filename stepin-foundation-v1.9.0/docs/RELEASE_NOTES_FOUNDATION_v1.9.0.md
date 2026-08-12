# StepIn v1.9.0 · Foundation Release Notes

Version: `1.9.0-beta-foundation`  
Date: 2026-08-12

## 本版重点

本版不继续扩大岗位数量，而是在 v1.8 Desktop Workbench 前增加“公共实践底座”。零基础学生不再先选专业、岗位、课程或项目，而是从一件简单、真实、能马上开始的小工作动作进入。

## 新增

- 10 项公共实践能力模型。
- 8 个连续基础任务。
- `guided → assisted → independent → revision → transfer → combined` 脚手架撤离。
- 任务级提示次数、得分和独立完成记录。
- Foundation Evidence 写入原 Canonical Evidence Store。
- 第 8 步自动组合第一份 `foundation_project` Artifact。
- 小项目后的实践表达：自己复盘 / 简历 / 面试说法。
- 基础完成后增加 3 次跨材料探索，再显示完整职业路径。
- 多任务 Evidence 回写公共能力的保守聚合信号。
- 教师“基础成长”列表与单个学生成长轨迹。
- Foundation API 显式 `session_id` 绑定。
- 已登录学生的服务器级专业 Practice 锁定，不能从 API 绕过 Foundation。

## 保持兼容

- 已有进行中专业 Practice 不被强行打断。
- v1.8 Desktop/Offline、Workbench、Artifact、Evidence、Export、Attachment、Backup、Practice Studio 均保留。
- 未认证旧测试/开发链保留兼容启动能力；正式登录学生使用新 Foundation Gate。

## 当前边界

第一组公共基础任务仍为内置内容；Foundation 无代码编辑器、跨更多专业任务的能力聚合、完整项目链编辑器留给后续版本。Windows EXE/Installer 仍需 Windows x64 真机构建。
