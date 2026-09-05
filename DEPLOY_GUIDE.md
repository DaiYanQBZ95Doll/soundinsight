# SoundInsight 在线 Demo 部署指南（ModelScope 创空间）

目标：获得一个中国大陆网络可直接访问的公网 Demo 地址，总操作量约 30 分钟。

## 第 1 步：注册并登录（3 分钟）

访问 https://modelscope.cn ，注册账号并登录。预期页面：右上角出现你的头像。

## 第 2 步：创建模型仓库并上传权重（10 分钟）

1. 进入「模型」-「创建模型」，仓库名填 SoundInsight_models，可见性选公开，创建。
2. 进入「个人中心」-「访问令牌」，创建令牌并复制。
3. 在本地项目目录运行以下命令（替换用户名与令牌）：

python upload_models.py --repo 你的用户名/SoundInsight_models --token 你的令牌

4. 预期：终端显示上传完成，模型仓库页面出现 sound_model 与 multi_label_model 两个文件夹。

## 第 3 步：创建创空间（10 分钟）

1. 进入「创空间」-「创建创空间」，SDK 选 Gradio，命名 SoundInsight。
2. 把本地 deployment/ 目录下的四个文件上传到空间仓库：
   - app.py
   - requirements.txt
   - config.json
   - README_Space.md
3. 编辑 config.json，把 model_repo_id 填为 你的用户名/SoundInsight_models。
4. 提交后空间自动构建（首次构建约 5-8 分钟，日志在空间「日志」页）。

## 第 4 步：验证（7 分钟）

1. 空间构建完成后打开公网地址，用手机流量访问一次（验证非本地网络可达）。
2. 在「单条评论」页输入示例评论，确认延迟 ≤5 秒、判定正确。
3. 在「批量分析」页上传 sample_reviews_100.csv，确认 100 条 ≤90 秒出报告。
4. 切换到「边界案例」页，确认六类场景完整显示。
5. 把公网地址发给我，我执行 deploy_check.md 的自动验收。

## 常见问题

启动崩溃 `RuntimeError: operator torchvision::nms does not exist`：requirements.txt 钉了 torch 版本，与创空间基础镜像（自带 torch 2.10.0 + 配套 torchvision）产生 ABI 冲突。已修复：deployment/requirements.txt 不再钉 torch/numpy/gradio 版本，深度学习栈沿用镜像自带版本（文件内有注释说明）。此坑不要再踩回。

首次构建超过 15 分钟：多为 torch 大包下载缓慢所致；修复后已不再重复下载 torch，构建应明显加快。

构建失败：查看空间日志，先看是否是上述 torch/torchvision 冲突；其他依赖冲突可删版本号重试。

下载模型失败：确认 model_repo_id 拼写正确（当前已填 DaiYanQBZ95Doll/SoundInsight_models）、模型仓库为公开可见。

延迟偏高：免费空间为 CPU 环境，单条推理约 2-5 秒属正常。

## 备选降级

若 ModelScope 创空间不可用：deployment/ 目录同时兼容 Hugging Face Spaces（requirements.txt 与 app.py 通用，仅 config.json 的下载地址需改），但国内访问受限，需在文档中注明。

若两者均不可用：本地一键启动（python demo_sound_v2.py）+ 录屏演示，并在 deploy_check.md 记录受阻原因。
