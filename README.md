# Realtek BTSoc HMI/Display Skills

一个 [Claude Agent Skills](https://agentskills.io) 集合仓库，收录 Realsil 内部与相关项目的
Agent Skills，供支持 Skills 的 AI 工具（Claude Code、公司 AI Plugin Hub 等）扫描与使用。

## 仓库结构

```
skills/                          # 本仓库根
├── .claude-plugin/
│   └── marketplace.json         # Claude Code plugin marketplace 注册
├── skills/                      # 实际 skill 都放这里，一个 skill = 一个子目录
│   └── <skill-name>/
│       └── SKILL.md             # 唯一必需文件，含 name / description frontmatter；
│                                # 其余支撑文件/目录（references、assets、scripts 等）可按需自由添加
├── spec/                        # Agent Skills 规范指引
└── template/
    └── SKILL.md                 # 新建 skill 的最小脚手架
```

## Skills 列表

| Skill | 说明 | 维护方式 |
| --- | --- | --- |
| [honeygui-designer](./skills/honeygui-designer/) | 根据自然语言描述生成生产级 HoneyGUI HML（嵌入式设备 UI 描述语言）文件——设计智能手表、可穿戴、IoT 界面 | **自动同步**，见下 |

## 贡献新 skill

复制 [`template/SKILL.md`](./template/SKILL.md) 到 `skills/<your-skill-name>/SKILL.md`，填好
frontmatter 和内容，然后在上表登记一行。不同 skill 目录互不影响；`honeygui-designer` 的自动同步
只会覆盖它自己负责的目录（见下），**不会动其他人的 skill**。

## 在 Claude Code 中使用

把本仓库注册为 Claude Code 的 plugin marketplace：

```text
/plugin marketplace add realmcu/skills
```

然后安装需要的 skill 插件：

```text
/plugin install honeygui-designer@realmcu-skills
```

## 自动同步的 skill

`skills/honeygui-designer/` 由 [HoneyGUI Visual Designer](https://github.com/realmcu/honeygui-design)
主仓库自动同步生成，**唯一真相源在主仓库** `vibe-designer/skills/honeygui-designer/`。

- 请**不要直接修改** `skills/honeygui-designer/` 目录——改动会在下次同步时被覆盖。
- 如需修改，请到 https://github.com/realmcu/honeygui-design 提交，合入 `master` 后 CI 自动同步到这里。
- 每次同步是一次 squash 提交，提交信息沿用源仓库对应改动的标题，并在正文标注来源 commit SHA。

## License

MIT，见 [LICENSE](./LICENSE)。各 skill 目录内如附带自己的 LICENSE，以其为准。
