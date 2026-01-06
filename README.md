# Minecraft-Mod-Environment-Classifier

Minecraft-Mod-Environment-Classifier(python3.9) 仓库介绍

这是一个简单的自动化工具，用于智能分类 Minecraft 模组文件，通过分析模组在客户端/服务端的运行环境要求（需装/可选/无效），将模组 JAR 文件自动归类到对应目录。核心功能包括：  

1. 智能名称提取  
   • 从 JAR 文件名中剥离版本号、加载器标识（Forge/Fabric/NeoForge 等）  
   • 特殊处理 api/lib 后缀（如 ExampleAPI.jar → Example API）  
   • 支持复杂命名规则（如 [JEI] JustEnoughItems-1.20.1.jar）  

2. 模组信息抓取  
   • 自动在 http://www.mcmod.cn 搜索模组  (暂未实现多个搜索网址)
   • 解析模组详情页的运行环境要求（客户端/服务端）  

3. 输出目录  
   output/
   ├── unknown/          # 未识别的模组
   └── classified/        # 已分类模组
       ├── ClientRequired/  # 客户端必需
       ├── ClientOptional/  # 客户端可选
       ├── ClientInvalid/   # 客户端无效
       ├── ServerRequired/  # 服务端必需
       ├── ServerOptional/  # 服务端可选
       └── ServerInvalid/   # 服务端无效
   

4. 容错机制  
   • 多编码支持（UTF-8/GBK）读取文件  
   • 双模式网页抓取（Requests，而Selenium未实现）  
   • 异常状态回退到 unknown 目录  

使用场景
• 整理本地模组包（如整合包开发）  

快速开始

1. 将待分类的 .jar 文件放入 mods/ 目录  
2. 运行脚本：  
   python test.py
3. 结果输出到 output/ 目录  


