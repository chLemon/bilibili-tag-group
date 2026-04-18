# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库现状

- 当前仓库仍处于初始化状态，仅有 `.git/` 目录，暂无源码、README、构建脚本或测试配置。
- 在出现实际项目文件前，不要假设构建、运行、Lint、测试命令，也不要假设技术栈或目录架构。
- 需要先读取真实配置文件（如 `package.json`、`pyproject.toml`、`go.mod`、`Cargo.toml`、README）后，再补充本文件。

## 文档与注释

- 本项目的文档、说明、代码注释尽量使用中文。
- 命令、配置键、库名、协议名等技术标识保持原文。

## 更新本文件时的优先级

- 优先记录真实可执行的开发命令。
- 优先总结需要结合多个文件才能看出的高层架构。
- 不要写泛化的软件工程建议，也不要罗列从目录遍历即可直接看出的琐碎信息。
