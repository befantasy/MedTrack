# MedTrack-Onco | 肿瘤全过程治疗与慢病智能管理平台

> **以肿瘤全生命周期治疗管理为主，其他慢病为辅的现代化自托管个人健康档案（PHR）与就医协作系统。**

支持多用户自主登录、多模态 AI 智能提取（化验单、CT/MRI影像、病理分子报告、出院用药单）、肿瘤全景治疗时间轴、ECharts 标志物与毒副反应趋势看板，以及专为门诊与 MDT 会诊设计的一键病历生成与 7 天加密只读分享。

全容器化交付，专为配合 **`cloudflared` 容器隧道** 设计，无需公网 IP 与路由器端口映射即可享受安全 HTTPS 域名访问。

---

## 一、 核心功能特色

1. **多用户与肿瘤专科建档**：
   * 用户独立注册登录（基于加盐哈希与 JWT 鉴权），数据多租户严格物理/逻辑隔离。
   * 专科肿瘤档案：原发部位、病理类型、初诊分期（TNM）、当前分期、分子驱动基因/靶点（EGFR/ALK/KRAS/PD-L1等）、合并慢病（高血压/糖尿病等）与过敏史。
2. **专科治疗全要素登记**：
   * **外科手术**：术式名称、手术日期、切缘（R0/R1/R2）、淋巴结清扫枚数与转移比率、术后病理总结。
   * **放射治疗**：照射靶区、照射技术（IMRT/SBRT/质子）、总剂量（Gy）、分割照射次数、急慢性放射性反应。
   * **系统药物治疗**：治疗线数（辅助/新辅助/一线/二线/维持）、疗法（化疗/靶向/免疫/联合方案）、方案名称、周期轮次、药物明细与 CTCAE 不良反应分级。
3. **多模态 AI 智能单据识别与结构化**：
   * 接入多模态大模型（兼容 Google Gemini 2.0 Flash、阿里通义千问 Qwen2.5-VL、OpenAI GPT-4o 等）。
   * 自动解析中文复杂化验单（指标名、代码缩写、测定值、参考范围、高低状态）、影像报告（部位、所见、诊断印象、RECIST疗效）、病理报告（组织分化、IHC免疫组化、基因突变）与出院小结。
4. **全病程治疗全景时间轴 (Oncology Swimlane)**：
   * 多轨泳道直观展现“确诊 ➔ 手术 ➔ 辅助化疗 1-4 周期 ➔ 辅助放疗 ➔ 靶向维持 ➔ 各节点影像复查与化验”的全景演变。
5. **双层动态指标时序看板 (ECharts)**：
   * 上层：肿瘤标志物（CEA, CA19-9, CA125 等）演变曲线与参考上限警戒线。
   * 下层：化疗/靶向治疗骨髓与器官安全性（白细胞、中性粒细胞、血小板、转氨酶、肌酐）动态监控。
6. **一键生成就诊病历报告与安全分享**：
   * 患者就诊前一键生成《门诊就医与 MDT 会诊汇总单》。
   * 支持一键排版打印与导出 PDF。
   * 支持生成 7 天有效的专属安全分享链接（支持自定义 4 位访问提取码），直接微信发给医生或异地专家在手机端免登录只读查阅。

---

## 二、 目录结构

```
MedTrack/
├── docker-compose.yml              # 统一容器编排 (Nginx + Backend + Postgres)
├── .env.example                    # 环境变量模版 (API Key, DB配置, JWT密钥)
├── README.md                       # 部署与使用完整文档
├── nginx/
│   └── default.conf                # 反向代理网关配置 (50M上传限制, 120s识图超时)
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                     # FastAPI 启动入口与静态文件托管
│   ├── config.py                   # 全局配置管理
│   ├── database.py                 # PostgreSQL 数据库引擎
│   ├── models.py                   # 肿瘤全周期数据模型 (SQLAlchemy)
│   ├── schemas.py                  # Pydantic 校验与契约
│   ├── auth.py                     # 密码哈希与 JWT 鉴权
│   ├── services/
│   │   ├── ai_extractor.py         # 多模态大模型智能识别 (化验/影像/病理/出院小结)
│   │   └── report_generator.py     # 肿瘤门诊 MDT 就诊病历生成器
│   └── routers/
│       ├── auth_router.py          # 注册、登录、档案设置
│       ├── oncology_router.py      # 手术、放疗、系统治疗、全景时间轴
│       ├── lab_router.py           # 化验单与检验指标管理
│       ├── imaging_router.py       # 影像复查与 RECIST 疗效追踪
│       ├── upload_router.py        # 文件上传与 AI 触发提取
│       ├── chart_router.py         # ECharts 时序数据集接口
│       └── share_router.py         # 门诊报告只读分享与校验
└── frontend/                       # 现代化响应式 Web 前端 (PC/手机端自适应)
    ├── index.html                  # 主控制台 (时间轴、AI识别、治疗登记、图表)
    ├── share.html                  # 医生/专家专属只读就诊汇报单 (免登录外链)
    ├── css/
    │   └── style.css               # 医疗专科清爽样式表 (含 @media print 打印排版)
    └── js/
        ├── api.js                  # 统一 API 请求封装
        ├── app.js                  # 核心交互、弹窗与多模块调度
        ├── charts.js               # ECharts 图表初始化与重绘
        └── timeline.js             # 全病程时间轴渲染
```

---

## 三、 快速部署教程 (Docker Compose)

### 1. 配置环境变量
在项目根目录下复制一份 `.env` 文件：
```bash
cp .env.example .env
```
根据需要修改 `.env` 中的大模型 API 密钥：
```ini
AI_API_KEY=你的多模态大模型API密钥
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
AI_MODEL=gemini-2.0-flash
```
*(注：如果暂时未填写 API Key，系统内置了高质量医学级模拟数据引擎，完全可以正常演示全部上传、提取、入库和图表逻辑)*

### 2. 启动容器集群
```bash
docker-compose up -d --build
```
启动后容器包含：
*   `med_nginx`：反向代理网关（监听宿主机 `8080` 端口）
*   `med_backend`：FastAPI 业务与 AI 引擎
*   `med_postgres`：PostgreSQL 15 数据库

---

## 四、 与 `cloudflared` 容器无缝打通

由于您的 `cloudflared` 是以容器方式运行的，我们已在 `docker-compose.yml` 中建立了名为 `med-net` 的 Docker 网络。

### 步骤 1：将您的 `cloudflared` 容器连接到该网络
执行以下命令（将 `<你的cloudflared容器名称>` 替换为您实际的容器名）：
```bash
docker network connect med-net <你的cloudflared容器名称>
```

### 步骤 2：在 Cloudflare 控制台配置隧道转发
登录 [Cloudflare Zero Trust 控制台](https://one.dash.cloudflare.com/) ➔ 进入 **Networks** ➔ **Tunnels** ➔ 点击您的隧道：
1. 添加一条 **Public Hostname**：
   * **Subdomain**：例如 `med` 或 `health`
   * **Domain**：选择您的主域名（如 `yourdomain.com`）
2. 在 **Service** 部分配置：
   * **Type**：`HTTP`
   * **URL**：`med_nginx:80`
3. 保存即可。

现在，您和所有用户即可通过公网安全域名（如 `https://med.yourdomain.com`）直接访问系统，在微信中点击分享链接也能秒开！
