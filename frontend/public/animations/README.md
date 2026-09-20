# 角色动作资源

- `haihegirl_idle_6s.vrma`：6 秒循环待机，包含呼吸、轻微重心移动、视线变化和眨眼。
- `haihegirl_thinking_4s.vrma`：4 秒循环思考，包含抬手托腮、侧头、轻微躯干变化和眨眼。

两段动画均由 `scripts/build_idle_thinking_vrma.py` 从本地 VRM 生成。脚本只读取模型并输出独立 VRMA，不会修改原始 VRM。
