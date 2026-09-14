# -*- coding: utf-8 -*-
# check_studio_build.py —— 查询创空间当前部署的镜像 tag 与部署/更新时间，
# 用于判断推送后的重建是否已生效。
import json
import re
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

URL = "https://modelscope.cn/studios/DaiYanQBZ95Doll/SoundInsight"
r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
m = re.search(r'window\.__detail_data__ = "(.*?)";', r.text, re.S)
if not m:
    print("未找到 __detail_data__，页面长度:", len(r.text))
    sys.exit(1)
raw = m.group(1).encode().decode("unicode_escape")
d = json.loads(raw)
cfg = d.get("LastDeployConfig", {}) or {}
print("镜像 ImageId :", cfg.get("ImageId"))
print("SDK 版本     :", cfg.get("SdkVersion"))
print("部署时间戳   :", d.get("DeployedTime"), "→",
      __import__("datetime").datetime.fromtimestamp(
          d.get("DeployedTime", 0)).strftime("%Y-%m-%d %H:%M:%S"))
print("最后更新时间 :", d.get("LastUpdatedTime"), "→",
      __import__("datetime").datetime.fromtimestamp(
          d.get("LastUpdatedTime", 0)).strftime("%Y-%m-%d %H:%M:%S"))
print("失败信息     :", repr(d.get("FailedMessage"))[:200])
print("实例状态     :", d.get("Status") or d.get("DeployStatus") or "(未提供)")
