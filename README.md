# Detariki Knowledge Base

AI-powered Knowledge Base for Detariki Z.

## ローカル開発環境のセットアップ

本プロジェクトは Docker Compose および VSCode Dev Container に対応しており、簡単に開発環境を構築できます。

### 1. 環境変数の設定
`.env.example` をコピーして `.env` を作成します。
```bash
cp .env.example .env
```

### 2. Docker Compose の起動
以下のコマンドで、Python開発環境・Neo4j・Ollama がすべて起動します。
```bash
docker compose up -d
```
> **Note**: GPUが利用できる環境（Windows 11 + WSL2 + Docker Desktop）では、Ollamaが自動的にGPUを利用します。

### 3. アクセスURL
起動後、以下のURLから各サービスにアクセスできます。

*   **Neo4j Browser**: [http://localhost:7474](http://localhost:7474) (初期設定は `.env` 参照)
*   **Ollama API**: [http://localhost:11434](http://localhost:11434)
*   **MkDocs** (起動時): [http://localhost:8000](http://localhost:8000)

### 4. VSCode Dev Container での接続
VSCodeを利用している場合、Dev Container機能を使ってコンテナ内で直接開発を行えます。

1. VSCodeでプロジェクトディレクトリを開きます。
2. 左下の緑色のアイコン（Remote Window）をクリックするか、コマンドパレット(`Ctrl+Shift+P`)から `Dev Containers: Reopen in Container` を選択します。
3. 初回起動時に `uv` を用いて自動で依存関係がインストールされます。

VSCode上からは、`F5` キーを押すことで現在開いているPythonスクリプトを実行・デバッグ可能です。
