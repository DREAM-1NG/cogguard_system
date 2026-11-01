# Mannocci et al. (2024) — 四维度定义（综述原文摘录）

> 来源: "Detection and Characterization of Coordinated Online Behavior: A Survey" (arXiv 2408.01257)
> 用途: Characterization 四维度的概念锚点。所有 Dim-A/B/C/D 的操作化定义必须忠于以下原文语义。

协同在线行为由四个**正交（orthogonal）**的定义维度刻画：authenticity, harmfulness, orchestration, time-variance。

---

## Authenticity（真实性）

Authenticity refers to the **degree of genuineness and transparency** that the actors exhibit in their actions and overall online presence.

- **Coordinated authentic behavior** is executed by genuine actors and typically emerges organically within a community of users who share common interests or beliefs. While authentic forms of coordination are also harmless in the majority of cases, there also exist less frequent cases of authentic yet harmful behaviors.
- **Coordinated inauthentic behavior** entails the use of fake accounts, such as social bots, trolls, and fake personas. Inauthentic coordination is often **characterized by its deceptive nature and aim to manipulate unaware users**. Nonetheless, there exist cases of inauthentic yet harmless coordination.
- **关键**: authenticity 与 harmfulness 是**两个正交维度**（orthogonal dimensions），形成 4 个象限：authentic+harmless / authentic+harmful / inauthentic+harmless / inauthentic+harmful。

---

## Harmfulness（危害性）

Harmfulness refers to the **negative impact, consequences, or outcomes** — both online and offline — resulting from the coordinated actions of the actors. Harmfulness **depends both on the shared intent and actions of the actors engaged in coordination, and on the viewpoint of the observer**.

- **Clear-cut harmful cases**: 协同传播 disinformation、hate speech、online harassment。
- **Clear-cut harmless cases**: 在突发灾难后协同收集与共享信息和资源。
- **关键**: harmfulness 既取决于行为者的 shared intent + actions，也取决于**观察者视角**（主观性）。

---

## Orchestration（组织度）

Orchestration represents the **degree of planning and organization between the coordinated actors**. This dimension is closely linked to the intent of the actors — highly orchestrated campaigns typically imply shared intent and goals.

The orchestration of a coordinated campaign can be **centralized**, **decentralized**, or **non-orchestrated**:

- **Centralized orchestration**: 单一 actor/entity 控制所有其他 actor 的行为。This centralized authority dictates the **timing, content, and strategy** of the coordinated actions, allowing for tight coordination and synchronization. 例: social botnets，大量自动账号在 botmaster 命令下准同时执行预定动作。
- **Decentralized orchestration**: 控制分布在网络中多个 actor，无单一中央权威。Actors may **self-organize, collaborate, or communicate autonomously**, often guided by shared goals, interests, or ideologies. 例: 2021 年 1 月 Reddit 散户协同针对 GameStop 做空。
- **Non-orchestrated coordinated behavior**: 多个 actor 的行为**自发地**围绕某话题/叙事/活动汇聚。例: 某些病毒式社媒趋势，由 hashtag 或活动的广泛采用自然涌现，用户观察并模仿他人行为。
- **关键**: 我们系统中的 `emergent` 对应综述的 `non-orchestrated`。三档而非两档。

---

## Time-variance（时变性）

Time-variance refers to **the temporal characteristics and the dynamic nature of coordinated online behavior**. It grasps possible changes in the **types, timing, frequency, and intensity** of the actions, which in turn may reflect changes in the intent of the actors, as well as adaptations or responses to external stimuli.

- **Static coordinated behavior**: 某些 spammer 和 bot 重复执行相同动作，遵循固定模式，无明显适应或变化。
- **Dynamic / time-varying behavior**: 许多 information operations 在不同时间点呈现不同特征。变化的特征包括参与协同的 actor 类型（自动 vs 人工操作）或讨论话题。
- **Duration（持续时间）**: time-variance 强烈依赖协同行为本身的持续时间。
  - 某些 state-sponsored disinformation campaigns 在平台上运营**数年甚至数十年**。在如此长的时间跨度内，actors **adapt their tactics, narratives, and targets** 以响应 intent 转变、技术与平台变化、或反制措施进展。这意味着协同行为相对**渐进而细致的演化**。
  - 相反，其他形式的在线协同依赖**可丢弃/一次性账号**（expendable/disposable accounts），为短命、快节奏的活动而创建。
- **关键**: time-variance = 静态/动态 + 持续时间（长期渐进演化 vs 短命一次性）。

---

## 对 CogGuard Characterization 的总体启示

1. **正交性**: Authenticity 与 Harmfulness 必须独立评估，不能合并为单一"可疑度"。系统应输出 4 象限定位。
2. **Orchestration 三档**: centralized / decentralized / non-orchestrated(emergent)，与 intent 强关联。
3. **Time-variance 双轴**: 模式轴（static/dynamic）+ 时长轴（短命/长期）。
4. **观察者视角**: Harmfulness 评估需声明视角假设（本项目: 网络舆论安全视角）。
5. **Intent 是隐变量**: orchestration 和 harmfulness 都与 intent 关联，但 intent 通常未知/隐藏，只能通过 actions 间接推断。
