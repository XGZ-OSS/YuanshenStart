# 沅神启动 · GitHub 自动发布与联网更新

**用途：** 本仓库通过 GitHub Actions 在 Windows 上自动将 `app.py` 打包成
`YuanshenStart.exe`，生成 SHA-256 清单，发布到 GitHub Releases，
然后将固定入口 `latest.json` 发布到 GitHub Pages。

## 首次设置（只做一次）

1. 注册或登录 GitHub，创建一个**公开仓库**（例如 `YuanshenStart`）。
   公开仓库的 Release 文件无需用户登录即可下载。
2. 将本 ZIP 中的全部文件（包括隐藏的 `.github/workflows/release.yml`）
   上传到仓库根目录。不要上传任何含真实积分的 `data` 文件夹。
3. 打开 GitHub 仓库的 **Settings → Pages**，将 Source 设为
   **GitHub Actions**。
4. 确认仓库启用了 GitHub Actions。构建工作流使用
   `contents: write` 创建 Releases，并使用 `pages: write` 发布 Pages。
5. 重要：`app.py` 的 `APP_VERSION` 必须与发布 Tag 匹配。例如
   `APP_VERSION = "3.9"` 对应 Tag `v3.9`。
6. 在仓库 **Releases → Draft a new release** 中创建 `v3.9` 版本可能
   不会触发 tag push 工作流（如果只在网站点击发布）。**建议在仓库终端
   或 GitHub Desktop 中先创建并推送 Tag**：

   ```bash
   git tag v3.9
   git push origin v3.9
   ```

   也可以在 **GitHub 网站 → Releases → Draft** 之前创建 Tag，再发版，
   但不要与 Actions 自动创建 Release 的任务重复。首次推荐用 git push tag。

7. 打开 **Actions → Build and publish YuanshenStart**，
   观察 `build`、`deploy-pages` 两个作业均成功。
8. 最新版固定清单地址将是：

   `https://你的用户名.github.io/你的仓库名/latest.json`

9. 在 GitHub Release 页面下载 `YuanshenStart_Windows.zip`。
   解压后直接双击 `YuanshenStart.exe`，**使用者不用安装 Python**。
   首次发布 ZIP 中已带 `update_url.txt`，安装到其他电脑后无需再配置更新地址。

## 发布下一版（例如 3.10）

1. 修改 app.py 的 `APP_VERSION` 为 `"3.10"`。
2. 更新 `更新日志.md`，提交并推送代码。
3. 在同一提交上创建 `v3.10` Tag 并推送：
   `git tag v3.10 && git push origin v3.10`。
4. GitHub Actions 自动打包 Windows EXE、发布 Release 和刷新 Pages。
5. 已安装 v3.9 的用户打开程序即可检查更新；确认后下载安装。
   更新前程序会保存积分数据；原 EXE 会备份为
   `YuanshenStart.previous.exe`。

## 安全与数据

- 版本信息和下载地址都必须通过 HTTPS 提供。
- 下载完会根据 `latest.json` 中的 SHA-256 检查文件完整性。
- 这并不能替代软件发行者签名，公开分发建议考虑 Windows 代码签名。
- 老版本的 `data/积分数据.json`、备份、`update_url.txt` 不会随 EXE
  覆盖；不要上传私人积分数据到 GitHub。
- 原来 v3.8 的自动继承旧版数据功能仍保留。
- 若发布后用户仍无法访问 GitHub，可能是网络连接问题；联网更新需要能
  正常访问 GitHub Release 下载及 GitHub Pages。
- 此处没有连接你的 GitHub 账号或替你创建仓库、Tag、Release；需要你
  手动上传代码并开启 Pages。
