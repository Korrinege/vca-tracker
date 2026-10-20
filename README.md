# vca-tracker

Van Cleef & Arpels 补货提醒：每 10 分钟自动检查一次商品页，一旦出现 **ADD TO BAG**（有货），就让你的 iPhone 响警报（静音、睡眠模式下也会响），同时发一封带截图的邮件。

全部在云端免费运行，电脑不用开着。

```
cron-job.org（每 10 分钟）
   └─> 触发 GitHub Actions
         └─> 用真浏览器打开商品页，看 ADD TO BAG 有没有出现
               └─> 有货：Bark 手机警报 + Gmail 邮件
```

> 为什么要用真浏览器？Van Cleef 的商品页 HTML 里 "ADD TO BAG" 和 "ORDER BY PHONE" 两个按钮**一直同时存在**，是 JS 加载库存后才决定显示哪一个。只搜网页文字会一直误报有货，所以脚本判断的是按钮是否**真正可见**。

---

## 你需要准备

- 一个 GitHub 账号（免费）
- 一个 Gmail 账号，用来发提醒邮件
- 一部 iPhone，装 Bark app（免费）
- 一个 cron-job.org 账号（免费）

整个设置大约 20 分钟。

---

## 设置步骤

### 1. 复制这个 repo

点本页右上角的 **Fork** → **Create fork**。保持 **Public**：public repo 跑 GitHub Actions 是免费的，private 的免费额度不够每 10 分钟跑一次。

> 不用担心公开：所有密码都存在 GitHub Secrets 里，别人看不到。**千万不要把密码或 key 写进代码。**

### 2. 改成你想监控的商品

在你 fork 出来的 repo 里点 `vca_monitor.py` → 右上角铅笔图标，修改最上面配置段里的两行：

```python
PRODUCT_URL = "你的商品页链接"
PRODUCT_NAME = "商品名字（只是显示在邮件里）"
```

改完点 **Commit changes**。任何地区的 Van Cleef 英文官网都可以；如果是其他网站，把下面的 `IN_STOCK_TEXT` / `OUT_OF_STOCK_TEXT` 改成那个网站有货 / 没货时的按钮文字。

### 3. 生成 Gmail App Password

Gmail 不能用登录密码发信，需要一个专用密码：

1. 给你的 Google 账号开启 **2-Step Verification**（两步验证）
2. 打开 <https://myaccount.google.com/apppasswords>，随便起个名字（比如 VCA），生成一个 16 位密码
3. 马上复制下来，它只显示一次

App Password 必须在**发信的那个 Gmail 账号**里生成。

### 4. 设置 Bark（iPhone 警报）

1. App Store 搜 **Bark - Custom Notifications**，安装
2. 打开 app，点 **Enable** 允许通知；弹出 **重要提醒（Critical Alerts）** 时也点允许
3. 去手机 **设置 → 通知 → Bark**，确认 **重要提醒** 是开着的（这样静音和睡眠模式也会响）
4. 回到 Bark 首页，示例里的 `YOUR_KEY` 会变成一串字母数字。点 **Copy** 复制

> 如果首页一直显示 `YOUR_KEY`，说明通知还没打开成功。

### 5. 添加 Secrets

在你的 repo 里点 **Settings → Secrets and variables → Actions → New repository secret**，逐个添加（名字必须全大写、一字不差）：

| Name | 填什么 | 必填？ |
|---|---|---|
| `GMAIL_USER` | 发信的 Gmail 地址 | 是 |
| `GMAIL_APP_PASSWORD` | 第 3 步的 16 位密码 | 是 |
| `TO_EMAIL` | 收提醒的邮箱（不填就发给 `GMAIL_USER` 自己） | 否 |
| `BARK_KEY` | 第 4 步复制的内容，整条粘贴即可，脚本会自动提取 key | 否（不填就只发邮件） |

### 6. 测试

1. 点 repo 顶部的 **Actions**。如果是第一次进，点绿色按钮 **I understand my workflows, go ahead and enable them**
2. 左边选 **VCA restock check**。如果提示 workflow 被停用，点 **Enable workflow**
3. **先把手机调成静音**，然后点右边的 **Run workflow** → 勾选测试选项 → **Run workflow**
4. 一两分钟内手机响了、也收到了测试邮件，就说明提醒设置成功
5. 再点一次 **Run workflow**，这次**不要**勾选。跑完后点进记录 → **check** → **Check stock**，看到 `状态：OUT_OF_STOCK` 就说明检测正常（如果正好有货，那就快去买 😄）

### 7. 用 cron-job.org 每 10 分钟自动触发

GitHub 自带的定时功能很不可靠（新 repo 可能几个小时都不触发），所以用 cron-job.org 来"按按钮"。

**① 生成 GitHub token**

点右上角头像 → **Settings**（账号设置，不是 repo 设置）→ 左栏最下面 **Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**：

- Token name：`vca-cron`
- Expiration：选一个够用的时间
- Repository access：**Only select repositories** → 选你 fork 的这个 repo
- Permissions：找到 **Actions**，设为 **Read and write**
- 生成后马上复制

这个 token 只能触发这一个 repo 的 Actions，权限很小。

**② 在 cron-job.org 新建 cronjob**

**COMMON** 标签：

- URL：`https://api.github.com/repos/你的用户名/你的repo名/actions/workflows/vca.yml/dispatches`
- Execution schedule：**Every 10 minutes**

**ADVANCED** 标签：

- Request method：**POST**
- Headers（Key 里**不要带冒号**）：

| Key | Value |
|---|---|
| `Accept` | `application/vnd.github+json` |
| `Authorization` | `Bearer 你的token`（Bearer 后面有一个空格） |
| `X-GitHub-Api-Version` | `2022-11-28` |
| `Content-Type` | `application/json` |

- Request body：`{"ref":"main"}`

点 **TEST RUN**，返回 **204** 就成功了，GitHub Actions 里会马上多一条运行记录。然后点 **CREATE**。

✅ 完成！之后每 10 分钟会自动检查一次。

---

## 日常使用

- **不用天天看。** 有货时手机会响、邮件会到。想确认有没有出问题，在 Actions 页面用 **Status → Failure** 筛选，空的就说明一切正常。
- **有货期间每 10 分钟会提醒一次**，直到你关掉为止。这是故意的，用来把你叫醒。
- **买到之后怎么停：** Actions → VCA restock check → 右上角 **⋯** → **Disable workflow**；再去 cron-job.org 把那个 job 的 **Enable job** 关掉。
- 运行记录不用清理，GitHub 默认保存 90 天后会自动删除。

## 常见问题

**cron-job.org 的 TEST RUN 没返回 204？**

| 返回码 | 原因 |
|---|---|
| 401 | token 粘贴错了或已过期 |
| 403 | token 的 Actions 权限没设成 Read and write |
| 404 | URL 打错了，或 token 没选到这个 repo |
| 422 | Request body 有问题，或 workflow 被停用了 |

**运行记录变红（失败）？** 点进去看 **Check stock** 的 log：

- `邮件发送失败` / authentication 错误：检查 `GMAIL_USER` 和 `GMAIL_APP_PASSWORD`
- `状态：UNKNOWN`：两个按钮都没找到，可能被网站反爬拦了，或者页面改版了。那次运行页面最下面的 **Artifacts** 里有当时的页面截图，下载下来看看

**手机没响？** 确认 Bark 的通知和"重要提醒"都打开了，并且 `BARK_KEY` 已经添加。可以在 Bark 首页点 **Send Test** 单独测试。

**用安卓手机？** Bark 只有 iOS 版。可以不填 `BARK_KEY`，只用邮件提醒。

---

*个人使用的小工具，只检查和提醒，不会自动下单。与 Van Cleef & Arpels 官方无关。请适度使用，尊重网站的使用条款。*
