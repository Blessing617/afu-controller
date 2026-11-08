# 变更：开源发布到 GitHub

## 动机

用户原话：「项目没有上库 github」「上 github 要参考阿福记账，不要上不需要的东西，
readme 图片脱敏不要出现具体网址和姓名什么什么的，教学引导合适，这玩意还是很麻烦的」。

现状：项目根目录**不是 git 仓库**（`git status` 报 not a git repository），
仓库里混着大量不能公开的东西：

- `server/.venv/`（依赖树，体积大、无意义）、`server/pytest-of-*/`、各处 `__pycache__/`
- `dist/阿福代肝控制器/`（打包产物，含 exe 与 `_internal`）
- `server/data/`（运行时数据：配对信息、任务记录、日志）
- `README.md` 与 `docs/新手图文教程.md` 中写有作者真实公网域名
  `https://host.tailxxxxxx.ts.net` 与主机名 `host`（多处）
- `docs/00~09` 内部验证报告：含本机路径、真实 IP、验证过程记录
- `docs/images/ui/*.png` 截图里直接显示真实地址
- `_perf.py`、`desktop/__pycache__` 等临时/缓存文件

参考对象 `Blessing617/afu-ledger` 的公开仓库做法（已核对）：README 有目录与演示截图、
`.gitignore` 排除构建产物与 keystore、许可证用 PolyForm Noncommercial 1.0.0、
有 `THIRD-PARTY-NOTICES.md`、截图全部使用虚构演示数据、字体授权单独注明。

## 范围

在范围内：

- 新建公开仓库 `Blessing617/afu-controller`（MIT 之外沿用阿福记账的 PolyForm
  Noncommercial 1.0.0，保持作者两个项目一致）。
- 仓库内容边界：只上源码、资源、必要文档；构建产物、运行时数据、依赖、缓存、内部验证报告不上。
- 全量脱敏：README、教程、截图、代码注释里不出现真实公网域名、主机名、内网 IP 段、
  真实姓名、QQ/邮箱、本机绝对路径。
- 重写 README：产品一句话、演示截图、功能、快速开始、依赖、架构、构建、常见问题、许可证、第三方声明。
- 教学引导整理成「别人照着能跑通」的程度，删除只对作者本机有意义的步骤与验证记录。
- 截图重拍：使用演示态数据（虚构地址；或对地址做遮挡），不带真实信息。
- 干净提交历史：一次初始化提交 + 若干整理提交，不携带被忽略的大文件历史。
- 验证：`.gitignore` 生效（`git status` 无意外文件）、仓库 clone 到新目录后内容完整、
  README 图片正常显示、无敏感串。

不在范围内：

- 功能改动、UI 改动（前者见 `rework-ui-style`）。
- 发布到应用商店、配置 CI/CD、自动构建、GitHub Actions。
- 发布 Release 附件（先把源码与文档上库；产物上传另行确认）。
- 改项目名、包名、目录结构。

## 方法

先用「敏感串清单 + grep 全仓」把所有需要脱敏的位置找全，再改写文本与重拍截图；
随后写 `.gitignore`、`LICENSE`、`THIRD-PARTY-NOTICES.md` 与 README；
最后 `git init` 后先 `git status --ignored` 人工核对一遍要提交的文件清单，确认无误再提交，
用本机已有凭证通过 GitHub API 建仓库并推送，最后在新目录 clone 一次做终验。
