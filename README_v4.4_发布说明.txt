沅神启动 v4.4 源码发布包
解压后覆盖仓库对应文件（保留原有 repair-pages.yml 等未包含文件）。
提交到 main 后运行：
git tag v4.4
git push origin v4.4
在 GitHub Actions 检查 build、package-pages、deploy-pages。
确认 latest.json 的 version 为 4.4，并检查 Release 下载链接。
本地 Windows 可运行 build_windows.bat（需要 Python 3.14）。
数据目录保持 %LOCALAPPDATA%/沅神启动/积分数据.json。
更新前建议备份整个数据目录。此包不包含已编译 EXE。
