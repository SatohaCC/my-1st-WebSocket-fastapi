# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 開発コマンド

```bash
# 依存関係のインストール
poetry install

# アプリの起動（章ごと）
poetry run uvicorn 01_echo.main:app --reload
poetry run uvicorn 02_chat.main:app --reload

# パッケージの追加
poetry add "パッケージ名"   # クォートで囲む（PowerShellで [] が誤解釈されるため）
```

## リポジトリ構造

FastAPIのWebSocketドキュメントを1章ずつ実装した学習リポジトリ。章ごとにフォルダで分離し、書き換えずに残す方針。

```
NN_name/
    main.py     # FastAPIアプリ本体
    README.md   # 章の解説・起動コマンド・実装メモ
Docs/
    starlette/  # 参照用にコピーしたStarletteのソースコード
```

各 `main.py` はそれ単体で完結しており、共有モジュールはない。

## 環境

- Python 3.12、Poetry 2.x、仮想環境は `.venv/`（プロジェクト内）
- Pylint: `C0103, C0114, C0115, C0116` を無効化（学習用コードのため）
- Mypy: `ignore_missing_imports = true`

## READMEの書き方

各章の `README.md` には「起動コマンド」「確認手順」「実装の解説」を含める。実装の解説はソースコードの引用と日本語の説明をセットで書く。`Docs/` 以下の実装を読んで裏付けが取れた情報のみ書く（推測で書かない）。
