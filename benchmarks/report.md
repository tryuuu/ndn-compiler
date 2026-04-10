# ベンチマークレポート

## 概要

同一データ `/height/Mt.Fuji/` がローカルにある場合とリモートにある場合で、インタプリタの実行時間を比較する。

## 計測条件

| 項目 | 内容 |
|---|---|
| 実行環境 | Docker コンテナ（consumer）、同一ホスト上の NFD・producer と通信 |
| 計測対象 | インタプリタの `run()` 実行時間（Python プロセス起動コストは除外） |
| 反復回数 | 各 100 回 |
| ウォームアップ | 3 回（計測前） |
| 計測日 | 2026-04-10 |

### Local（ローカル）

```ndn
let height = interest "/height/Mt.Fuji/"
print height
```

- `/height/Mt.Fuji/` が `_local_data` にある → NDN 通信なし、即値を返す

### Remote（リモート）

```ndn
let height = interest "/height/Mt.Fuji/"
print height
```

- `/height/Mt.Fuji/` が `_local_data` にない → NFD 経由で producer に Interest を発行し `"3776m"` を取得

## 結果（p99）

| | p99 |
|---|---|
| Local  |  0.20 ms |
| Remote | 11.65 ms |
| **差分** | **+11.45 ms** |

## 考察

- ローカルは 0.20 ms 以下で安定。
- NDN 経由では p99 が **11.65 ms** に跳ね上がる。NFD の内部スケジューリングやバッファリングによるまれな遅延スパイクが原因と考えられる。
- 本計測は同一ホスト上の Docker ネットワーク内であり、実際のネットワーク越し NDN では p99 の差はより顕著になることが想定される。

## 再実行方法

```bash
# コンテナが起動していない場合
make all

# コンテナ内でベンチマークを実行
docker cp benchmarks/benchmark.py consumer:/app/benchmark.py
docker exec consumer python3 /app/benchmark.py
```
