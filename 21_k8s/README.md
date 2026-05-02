# 21 Kubernetes 導入

20章のチャットアプリを minikube にデプロイする章。
フロントとバックエンドは変更なし。
`replicas: 2` にスケールすると、異なる Pod に接続したユーザー間でメッセージが届かなくなる問題を体験する。
この問題が 22章（Redis Pub/Sub）で解決される。

## 前提

- Docker がインストール・起動済みであること
- minikube と kubectl がインストール済みであること

## 起動

### 1. minikube を起動

```bash
minikube start
```

### 2. バックエンドイメージをビルド

```bash
# 21_k8s ディレクトリで実行
minikube image build -t chat-backend:latest ./backend
```

`minikube image build` は minikube 内部の Docker にイメージを直接ビルドする。
kind の `kind load` に相当するが、ビルドと同時に完了するため1コマンドで済む。

### 3. マニフェストを適用

```bash
# 21_k8s ディレクトリで実行
kubectl apply -f k8s/
```

Pod が起動するまで待つ（30秒〜1分程度）:

```bash
kubectl get pods -w
```

すべての Pod が `Running` になったら次へ進む。

### 4. LoadBalancer を有効化

```bash
# 別ターミナルで常時起動しておく
minikube tunnel
```

`minikube tunnel` は LoadBalancer Service に外部IP（`127.0.0.1`）を割り当てるデーモン。
起動中は `http://localhost:8000` でバックエンドに直接アクセスできる。

```bash
# 確認
kubectl get service backend
# EXTERNAL-IP が 127.0.0.1 になっていれば OK
```

### 5. フロントエンドを起動

```bash
# 別ターミナル: 21_k8s/frontend ディレクトリで実行
npm run dev
```

ブラウザで http://localhost:3000 を開く。

動作確認用ユーザー（`app/core/config.py` の `USERS` に定義）:

| ユーザー名 | パスワード |
|-----------|----------|
| alice     | password1 |
| bob       | password2 |

## 確認

### 通常動作の確認（replicas: 1）

チャットが正常に動作することを確認する。DB 永続化も 20章と同様に機能する（Pod を削除・再作成してもメッセージが残る）。

### 問題の再現（replicas: 2）

```bash
kubectl scale deployment backend --replicas=2
```

ブラウザで **2つのタブ**を開き、alice と bob でそれぞれログインする。
LoadBalancer が各タブの WebSocket 接続を異なる Pod に振り分けるため、alice のメッセージが bob に届かない場合がある。

どちらの Pod に接続されているかはログで確認できる:

```bash
# Pod 名を確認
kubectl get pods -l app=backend

# それぞれのログを別ターミナルで確認
kubectl logs -f pod/<pod-A の名前>
kubectl logs -f pod/<pod-B の名前>
```

alice と bob の `[connect]` ログが別々の Pod に出ていれば問題を再現できている。

---

## ファイル構成

```text
21_k8s/
    k8s/
        postgres.yaml    # PVC + Deployment + Service（PostgreSQL）
        backend.yaml     # Deployment + Service（FastAPI）
    backend/
        Dockerfile
        requirements.txt
        app/             # 20章と同一
```

## 実装の解説

### backend.yaml — Deployment

```yaml
spec:
  replicas: 1
  template:
    spec:
      containers:
        - name: backend
          image: chat-backend:latest
          imagePullPolicy: Never
          env:
            - name: DATABASE_URL
              value: "postgresql+asyncpg://user:password@postgres:5432/chat_db"
            - name: ALLOWED_ORIGIN
              value: "http://localhost:3000"
```

`imagePullPolicy: Never` はレジストリからのプルをスキップし、minikube 内にビルド済みのローカルイメージを使う。
環境変数は `env` で直接指定。本番では Secret / ConfigMap で管理するが、ここでは最小構成とした。

### backend.yaml — Service

```yaml
spec:
  type: LoadBalancer
  selector:
    app: backend
  ports:
    - port: 8000
```

`LoadBalancer` は `minikube tunnel` 実行中に外部IP（`127.0.0.1`）が割り当たり、
`http://localhost:8000` で直接アクセスできる。
複数 Pod があれば接続を分散するため、ポートフォワードなしで本物のロードバランシングが動作する。

### postgres.yaml — PersistentVolumeClaim

```yaml
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

PostgreSQL のデータをコンテナ外に保存するためのストレージ要求。
Pod を削除・再作成してもデータが消えない（20章の Docker Volume と同じ役割）。

### なぜ replicas: 2 でチャットが壊れるか

**DB（PostgreSQL）は1つなので、データの永続化は Pod をまたいで正しく機能する。**
Bob が再接続すると、alice が送ったメッセージは DB から取得されてちゃんと届く。

壊れるのは**リアルタイムのブロードキャスト**だけ。

`ChatManager` は接続リストをメモリ上に持つ：

```python
# backend/app/websockets/manager.py
class ChatManager:
    def __init__(self) -> None:
        self.connections: list[tuple[str, WebSocket]] = []
```

Pod A と Pod B はそれぞれ独立したメモリを持つため、alice（Pod A に接続）が送ったメッセージは
Pod A の `connections` リストに対してのみブロードキャストされる。
Bob が Pod B に接続していれば、そのリストには bob が存在しないためメッセージが**接続したまま**届かない。

| | 動作 |
|---|---|
| bob が再接続する | ✅ 届く（DB から過去履歴を取得するため） |
| bob が接続したままリアルタイムで受け取る | ❌ 届かない（Pod A のメモリには bob の接続がない） |

→ **22章**: Redis Pub/Sub を仲介役に挟み、すべての Pod が同じメッセージをリアルタイムで受け取れるようにする。

## クラスターのリセット

```bash
kubectl delete -f k8s/
minikube stop
```
