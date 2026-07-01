# ローカル開発環境(Docker/Dev Container)構築の計画

Detariki Knowledge Base (DKB) のローカル開発環境構築について、以下の計画で実装を進めます。

## 構成概要
*   **Docker Compose**: `neo4j`, `ollama`, `app` (Python環境) の3つのサービスを立ち上げます。
*   **Dev Container**: `app` サービスにアタッチし、VSCode上でPython 3.12 + `uv` の環境を利用できるようにします。
*   **Python管理**: `uv` をパッケージマネージャーとして使用し、`pyproject.toml` で管理します。

## Proposed Changes

### Root Configuration (Docker & Env)

#### [NEW] [docker-compose.yml](file:///d:/Dev/DetarikiKB/docker-compose.yml)
*   `app`: Python 3.12ベースのDockerfileをビルド。`uv`をインストール。開発中は落ちないように `tail -f /dev/null` 等で維持するか、DevContainerで起動。
*   `neo4j`: `neo4j:5` (最新LTS) イメージを利用。
*   `ollama`: `ollama/ollama:latest` を利用。GPUが利用可能な環境（Docker Desktop for WindowsのWSL2バックエンドなど）を想定し、NVIDIA GPUリソースのreservation設定を記載します。

#### [NEW] [docker/Dockerfile.dev](file:///d:/Dev/DetarikiKB/docker/Dockerfile.dev)
*   Python 3.12 slim をベースに、`uv` をインストールする開発用Dockerfile。

#### [MODIFY] [.env.example](file:///d:/Dev/DetarikiKB/.env.example)
*   Neo4jの認証情報 (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
*   Ollamaのエンドポイント (OLLAMA_HOST)

### VSCode & Dev Container

#### [NEW] [.devcontainer/devcontainer.json](file:///d:/Dev/DetarikiKB/.devcontainer/devcontainer.json)
*   `docker-compose.yml` を参照して `app` サービスに接続する設定。
*   Python, Ruff, Even Better TOML 等のVSCode拡張機能を推奨。
*   コンテナ起動後の初期化コマンド（`uv sync` など）の設定。

#### [NEW] [.vscode/launch.json](file:///d:/Dev/DetarikiKB/.vscode/launch.json)
*   現在特定の実行ファイル（ParserやAIなど）がないため、現在開いているPythonファイル(`"${file}"`)を実行してデバッグできる標準的な設定を追加します。

### Python Environment (uv & tools)

#### [MODIFY] [pyproject.toml](file:///d:/Dev/DetarikiKB/pyproject.toml)
*   Python 3.12 の要件設定。
*   開発用依存関係(`[tool.uv.dev-dependencies]`)として以下を追加:
    *   `ruff`
    *   `black`
    *   `pytest`
    *   `pre-commit`
    *   `mkdocs-material`
*   Ruff, Black, Pytestの基本設定。

#### [MODIFY] [.pre-commit-config.yaml](file:///d:/Dev/DetarikiKB/.pre-commit-config.yaml)
*   Ruff, Black などのフック設定を追加。

### Documentation

#### [MODIFY] [README.md](file:///d:/Dev/DetarikiKB/README.md)
*   `docker compose up -d` だけで環境が立ち上がる旨の説明を追記。
*   VSCodeのDev Containerで開く手順を追記。
*   `.env` ファイルの準備方法を追記。

## User Review Required

> [!IMPORTANT]
> OllamaでGPUを利用するための設定(`deploy: resources: ...`)を `docker-compose.yml` に含めます。Windows11のDocker Desktop環境（WSL2）でGPUパススルーを有効にしている場合、自動的にGPUが利用されます。
> もしGPUを持たない環境で実行するとエラーになる場合は、composeファイルから該当部分をコメントアウトする必要があります。この仕様でよろしいでしょうか？

> [!NOTE]
> `docker compose up` した際にPythonコンテナが終了しないよう、`command: sleep infinity` のような設定にしておき、VSCodeからコンテナ内に入って開発を進める（あるいはコンテナ内でMkDocsなどのサーバーを立ち上げる）というDev Containerの標準的なスタイルとします。

## Verification Plan

### 自動テスト / 静的解析
*   `pre-commit run --all-files` が正常に動作するか確認。

### 手動確認
*   ファイル作成後、この環境を利用して開発を始められる準備ができていることを報告します。ユーザー自身で `docker compose up -d` および VSCode での「Reopen in Container」を試していただきます。
