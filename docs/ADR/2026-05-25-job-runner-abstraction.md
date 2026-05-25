# ADR: Job Runner Abstraction

Date: 2026-05-25

## Status

Accepted

## Context

シミュレーション・最適化・予測学習は CPU バウンドの重い処理であり、API プロセスをブロックするとレスポンスが遅延する。一方、ローカル開発では Redis や Celery worker などの外部インフラを立てたくない。本番環境は Docker Compose（Celery）と Azure（ACA Jobs）の二系統がある。

これらを統一した抽象で扱えなければ、実行バックエンドの切り替えのたびにツール層・API 層の変更が生じる。

## Decision

`packages/agent/runner/` に `JobRunner` Protocol を定義し、実行バックエンドをプラグイン可能にする。

### 公開インターフェース

```python
class JobRunner(Protocol):
    async def submit(self, spec: JobSpec, ctx: ToolContext) -> JobHandle: ...
    async def status(self, job_id: UUID) -> JobHandle: ...
    async def result(self, job_id: UUID, wait: bool = False) -> JobResult: ...
    async def cancel(self, job_id: UUID) -> None: ...
```

### データモデル

| モデル | 役割 |
|---|---|
| `JobSpec` | 実行内容の仕様（`kind`, `payload`, `idempotency_key`） |
| `JobHandle` | submit 後に返す参照（`job_id`, `status`, `submitted_at`） |
| `JobResult` | 実行結果（`output`, `error`, `duration_ms`） |

### kind 一覧

| kind | 処理内容 |
|---|---|
| `simulation` | 在庫シミュレーション（InventorySimulator） |
| `optimization` | 補充最適化（ReplenishmentOptimizer） |
| `train_forecast` | 需要予測モデルの学習（LinearRegression → upsert_prediction） |
| `forecast_batch` | バッチ推論（未実装） |
| `report` | レポート生成（未実装） |

### 実装クラスと環境対応

| クラス | 環境 | 動作 |
|---|---|---|
| `InProcessJobRunner` | ローカル開発・テスト | `result()` 呼び出し時に同プロセス内で同期実行。Redis 不要 |
| `CeleryJobRunner` | Docker Compose | Redis へタスクをキューイング。`bdos.run_simulation` / `bdos.run_optimization` / `bdos.train_predictor` の3タスクを定義。`train_forecast` は `training` キューへルーティング |
| `AcaJobsRunner` | Azure 本番 | Azure Container Apps Jobs の HTTP API を呼び出してコンテナを単発起動 |

### バックエンド選択

`apps/api/state.py` の `_build_runner()` が `JOB_RUNNER_BACKEND` 環境変数を見て切り替える。

```
JOB_RUNNER_BACKEND=aca      → AcaJobsRunner
JOB_RUNNER_BACKEND=celery   → CeleryJobRunner
未設定 / in_process          → InProcessJobRunner
```

### 呼び出しフロー（Agent 経由）

```
SessionOrchestrator（LLM ループ）
  │ Claude が tool_use を返す
  ▼
SimulationTool / OptimizerTool
  │ JobSpec を組み立て
  ▼
runner.submit(spec, ctx)   → JobHandle
runner.result(job_id, wait=True) → JobResult
  │
  ▼
ToolResult として Orchestrator へ返却 → SSE で UI にストリーミング
```

### InProcessJobRunner の挙動

`submit()` は `JobHandle` を返すだけで実行しない。`result()` を呼んだ瞬間に同プロセス内で関数を直接実行する。テストでは `InProcessJobRunner` を注入することで Redis なしに全種類の kind を検証できる。

### ACA Jobs との分離

`apps/simulation-worker/run_job.py` と `apps/optimization-worker/run_job.py` は ACA Jobs 専用の単独スクリプトであり、Celery タスクとは別物。コンテナが `python run_job.py` として一発起動し、`job_runs` テーブルに直接ステータスを書き込んで終了する。

## Consequences

- ツール層（`SimulationTool`, `OptimizerTool`）は `JobRunner` Protocol のみに依存し、実行バックエンドを知らない
- ローカルで `InProcessJobRunner` のまま全機能を開発・テスト可能
- 新しいバックエンドを追加する場合は `JobRunner` Protocol を満たすクラスを追加し、`_build_runner()` に分岐を加えるだけでよい
- `CeleryJobRunner` は `forecast_batch` / `report` の kind をサポートしない。追加する場合は `celery_app.py` にタスクを定義し、`task_name_map` に追記する

## Reversal Cost

低。Protocol を削除して直接実装を各ツールに書き戻すだけ。ただし Celery/ACA の切り替えロジックが各ツールに散在するトレードオフがある。
