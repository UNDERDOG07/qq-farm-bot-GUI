# QQ经典农场 自农场挂机脚本GUI版本

反馈加 QQ 群 1072882497 

这个有什么优势：去除所有好友，任务相关功能，避免招人烦（吃举报必封号）。轻量化，调用系统浏览器，无封装。提供两个版本，一个施普通肥，一个不施肥。内置扫码获取code网站，运行前打开，免手机抓包。

其他作者也非常优秀，可以看看其他的分支哦。

基于 Node.js 的 QQ/微信 经典农场小程序自动化挂机脚本。通过分析小程序 WebSocket 通信协议（Protocol Buffers），实现全自动农场管理。
本脚本基于ai制作，必然有一定的bug，遇到了建议自己克服一下，后续不一定会更新了。增加了GUI，简化了安装，目前不完善。。。

（小萌新一枚，各位大佬多多指教😭）测试下来没有太大的问题，浏览器标签页关闭之后挂机依然进行，数据3秒刷新一次。已知bug：关闭标签页后，居中显示的进行时间没了。

## 安装与使用
  先运行install.bat进行环境部署，再运行start.bat输入code打开挂机。要关闭时最好打开标签页点击停止并且清除缓存数据。
  
  你需要从小程序中抓取 code。可以通过抓包工具（如 Fiddler、Charles、mitmproxy 等）获取 WebSocket 连接 URL 中的 `code` 参数。

### 邀请码功能（微信环境）

在项目根目录创建 `share.txt` 文件，每行一个邀请链接：

```
https://xxx?uid=123&openid=xxx&share_source=4&doc_id=2
https://xxx?uid=456&openid=xxx&share_source=4&doc_id=2
```

启动时会自动处理这些邀请链接，申请添加好友。处理完成后文件会被清空。

## 功能特性

### 自己农场
- **自动收获** — 检测成熟作物并自动收获
- **自动铲除** — 自动铲除枯死/收获后的作物残留
- **自动种植** — 收获/铲除后自动购买种子并种植（当前设定为种植白萝卜，因为经过数据计算(脚本可以自动种植-收获)，白萝卜的收益是最高的（经验收益）不喜欢的自己修改一下即可
- **自动施肥** — 种植后自动施放普通肥料加速生长
- **自动除草** — 检测并清除杂草
- **自动除虫** — 检测并消灭害虫
- **自动浇水** — 检测缺水作物并浇水
- ~~**自动出售** — 每分钟自动出售仓库中的果实（暂时不行）~~



### 开发工具
- **PB 解码工具** — 内置 Protobuf 数据解码器，方便调试分析
- **经验分析工具** — 分析作物经验效率，计算最优种植策略



### 依赖（如果运行环境有问题参考一下）

- [ws](https://www.npmjs.com/package/ws) — WebSocket 客户端
- [protobufjs](https://www.npmjs.com/package/protobufjs) — Protocol Buffers 编解码
- [long](https://www.npmjs.com/package/long) — 64 位整数支持
- python 相关
  pip install nicegui
  可选：更漂亮的日志高亮
  pip install pygments



## 项目结构

```
├── client.js              # 入口文件 - 参数解析与启动调度
├── src/
│   ├── config.js          # 配置常量与生长阶段枚举
│   ├── utils.js           # 工具函数 (类型转换/日志/时间同步/sleep)
│   ├── proto.js           # Protobuf 加载与消息类型管理
│   ├── network.js         # WebSocket 连接/消息编解码/登录/心跳
│   ├── farm.js            # 自己农场: 收获/浇水/除草/除虫/铲除/种植/施肥
│   ├── friend.js          # 好友农场: 进入/帮忙/偷菜/巡查循环
│   ├── task.js            # 任务系统: 自动领取任务奖励
│   ├── status.js          # 状态栏: 终端顶部固定显示用户状态
│   ├── warehouse.js       # 仓库系统: 自动出售果实
│   ├── invite.js          # 邀请码处理: 自动申请好友
│   ├── gameConfig.js      # 游戏配置: 等级经验表/植物数据
│   └── decode.js          # PB 解码/验证工具模式
├── proto/                 # Protobuf 消息定义
│   ├── game.proto         # 网关消息定义 (gatepb)
│   ├── userpb.proto       # 用户/登录/心跳消息
│   ├── plantpb.proto      # 农场/土地/植物消息
│   ├── corepb.proto       # 通用 Item 消息
│   ├── shoppb.proto       # 商店消息
│   ├── friendpb.proto     # 好友列表/申请消息
│   ├── visitpb.proto      # 好友农场拜访消息
│   ├── notifypb.proto     # 服务器推送通知消息
│   ├── taskpb.proto       # 任务系统消息
│   └── itempb.proto       # 背包/仓库/物品消息
├── gameConfig/            # 游戏配置数据
│   ├── RoleLevel.json     # 等级经验表
│   └── Plant.json         # 植物数据（名称/生长时间/经验等）
├── tools/                 # 辅助工具
│   └── analyze-exp-*.js   # 经验效率分析脚本
├── package.json
├── start.py               # 提供简易的GUI界面
├── install.bat            # 提供环境部署
├── start.bat              
```

## 运行示例
  

## 配置说明

### src/config.js

```javascript
const CONFIG = {
    serverUrl: 'wss://gate-obt.nqf.qq.com/prod/ws',
    clientVersion: '1.6.0.5_20251224',
    platform: 'qq',              // 平台: qq 或 wx
    heartbeatInterval: 25000,    // 心跳间隔 25秒
    farmCheckInterval: 2000,     // 农场巡查间隔 2秒
    friendCheckInterval: 1000,   // 好友巡查间隔 1秒
};
```

### src/friend.js

```javascript
const HELP_ONLY_WITH_EXP = true;      // 只在有经验时帮助好友
const ENABLE_PUT_BAD_THINGS = false;  // 是否启用放虫放草功能
```

## 注意事项

1. **登录 Code 有效期有限**，过期后需要重新抓取
2. **请合理设置巡查间隔**，过于频繁可能触发服务器限流
3. **微信环境**才支持邀请码和好友申请功能
4. **QQ环境**下服务器不推送土地状态变化，依靠定时巡查

## 免责声明

本项目仅供学习和研究用途。使用本脚本可能违反游戏服务条款，由此产生的一切后果由使用者自行承担。

## License

MIT

## Star History

<a href="https://www.star-history.com/#UNDERDOG07/qq-farm-bot-GUI&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=UNDERDOG07/qq-farm-bot-GUI&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=UNDERDOG07/qq-farm-bot-GUI&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=UNDERDOG07/qq-farm-bot-GUI&type=date&legend=top-left" />
 </picture>
</a>
