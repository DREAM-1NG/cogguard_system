# Python Style Guide

- 使用 Python 3.11+ 类型语法和绝对 import。
- 一个文件只拥有一个内聚职责；仅为真实子域增加 package 层级。
- public package 与 public module 使用显式 `__all__`。
- module interface 隐藏缓存、持久化、模型加载和兼容细节。
- dependencies 由调用方注入；测试与调用方通过相同 seam。
- 不在 Product System 中使用 `sys.path.insert` 或 Reference Boundary 运行根。
- 错误状态使用现有 typed exception 或结构化状态，不静默 fallback。
