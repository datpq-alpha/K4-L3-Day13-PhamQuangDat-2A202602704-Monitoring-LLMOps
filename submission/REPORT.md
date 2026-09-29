# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Phạm Quang Đạt
- **MSSV:** 2A202602704
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/datpq-alpha/K4-L3-Day13-PhamQuangDat-2A202602704-Monitoring-LLMOps
- **Commit SHA cuối:** `bcc950a0ebf38d4f56298d72fdcda35a3fb20bf1` (commit chứa đầy đủ source và evidence; commit sau chỉ hoàn thiện report)
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202602704`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08a-trace-root-metadata.png`, `evidence/08b-generation-usage-cost.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10a-prompt-promote.png`, `evidence/10b-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` |30/100|100/100 | |
| `validate_dashboard.py` |6/6 panel|6/6 panel| Contract đủ sáu panel; dashboard runtime phục vụ tại `/dashboard` |
| `pytest` |22 passed|30 passed| Bao gồm test child observations, PII-safe trace input, dashboard runtime và CP2 config |
| Số traces hợp lệ | 0 hợp lệ / 10 trace đã xuất hiện | 12 | Tất cả trace CP2 có root, retrieval và generation |
| Số PII leak |0|0| Email, điện thoại và thẻ đã được redacted trong dữ liệu baseline |
| Latency P95 / TTFT P95 | 2548 ms / 51 ms | 2857 ms / 51 ms | CP2 tính từ 12 response |
| Retrieval success rate | 100% (10/10) | 100% (12/12) | Không có retrieval failure |
| `/health` | `ok=true; tracing_enabled=true; incidents=all false` | `ok=true; tracing_enabled=true; incidents=all false` | API hoạt động, Langfuse được bật và không có incident đang kích hoạt |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware xóa context cũ, nhận `x-request-id` hợp lệ hoặc sinh ID theo dạng `req-<8-hex>`, bind vào structlog context, truyền qua `request.state` và trả lại trong response header.
- **Các metadata được ghi vào structured log:** `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model` và `env`.
- **Cách bảo đảm PII được scrub trước khi ghi:** Processor `scrub_event` xử lý đệ quy các chuỗi và được đặt trước `JsonlFileProcessor`, bảo đảm dữ liệu được che trước khi render/ghi file.
- **Cách kiểm chứng kết quả:** Chạy load test, kiểm tra response header và structured log; `validate_logs.py` đạt 100/100, không phát hiện PII thô, pytest đạt toàn bộ test.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Lọc trace name `day13-agent-request` trong project `day13-k4-l3a-2A202602704`, đối chiếu thời gian chạy workload và `correlation_id` với structured log.
- **Cấu trúc root/retrieval/generation observations:** Root `lab-agent-run` có child `retrieval` loại `retriever` và child `generation` loại `generation`. Retrieval chỉ capture query preview đã scrub và số document; generation chỉ capture preview đã scrub, model, TTFT, token usage, cost cùng managed prompt reference.
- **Cách nối trace với log:** `CorrelationIdMiddleware` bind `correlation_id`; cùng ID được ghi vào structured log và propagate vào root cùng hai child observations.
- **Prompt name:** `day13-chat`.
- **Version/label baseline:** Version 1, labels `baseline` và `production` sau rollback.
- **Version/label candidate:** Version 2, label `candidate`.
- **Trace ID của mỗi version:** Baseline v1: `38e3d6d5a7cdf5332591acd96b38da53` (`req-ba5e0001`); Candidate v2: `f16fc3c9ef4883f9a4191fa186b46e20` (`req-ca2d0002`).
- **Cách promote và rollback `production`:** Dùng `scripts/manage_prompts.py promote` chuyển `production` sang v2, kiểm tra label, sau đó dùng `rollback` đưa `production` về v1. Trạng thái cuối: baseline=v1, candidate=v2, production=v1.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** FastAPI phục vụ dashboard HTML tại `/dashboard`, đọc `data/logs.jsonl` trong cửa sổ 60 phút gần nhất và tự refresh sau 30 giây. Sáu panel gồm latency P50/P95/P99 + TTFT P95, traffic, error rate + retrieval success, cost, input/output tokens và quality proxy; mỗi panel hiển thị đơn vị, threshold và trạng thái healthy/breached.
- **SLO và lý do chọn:** SLO `fast_successful_requests` yêu cầu 99.5% request trong 28 ngày có `response_sent` và latency không quá 3000 ms. Ngưỡng cao hơn baseline ổn định để có phần đệm cho prompt fetch/network nhưng vẫn phát hiện tail latency ảnh hưởng người dùng. Cost dashboard là tổng trong cửa sổ 60 phút; guardrail cost 2.5 USD trong `slo.yaml` là giới hạn riêng theo ngày.
- **Cách tính error budget:** `100% - 99.5% = 0.5%`; tương đương tối đa 5 bad request trên 1,000 request, hoặc 201.6 phút không đạt trong cửa sổ 28 ngày nếu quy đổi theo thời gian.
- **Ba alert và runbook tương ứng:** `high_request_latency` (P95 > 3000 ms trong 5 phút), `elevated_request_errors` (error rate > 2% hoặc retrieval success < 90% trong 5 phút), và `degraded_answer_quality` (quality trung bình < 0.75 trong 10 phút). Alert gửi Slack `#llmops-alerts`; runbook và owner nằm trong `docs/alerts.md`.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`.
- **Khoảng thời gian điều tra:** Workload có tracing chạy từ khoảng `2026-09-29T10:27:30Z` đến `2026-09-29T10:27:45Z`; dashboard dùng cửa sổ 60 phút kết thúc tại `2026-09-29T10:27:45.364820Z`.
- **Triệu chứng từ metrics:** Panel latency chuyển sang `BREACHED`: P95 và P99 đạt 3858 ms, vượt threshold 3000 ms; P50 là 2656 ms. TTFT P95 chỉ 51 ms, error rate 0% và retrieval success 100%, cho thấy request vẫn thành công nhưng thời gian bị tiêu tốn trước generation. Trạng thái traffic `BREACHED` không phải triệu chứng chính vì workload chỉ có 10 request trong cửa sổ cố định 60 phút.
- **Log line và correlation ID liên quan:** Event `response_sent` lúc `2026-09-29T10:27:40.038691Z` có `correlation_id=req-241121c9`, feature `monitoring`, model `claude-sonnet-4-5`, `latency_ms=2657`, `ttft_ms=50`, `tool_name=retrieval` và `tool_success=true`. Request không lỗi nhưng tổng latency cao trong khi TTFT vẫn bình thường.
- **Trace ID và span gây ảnh hưởng:** Trace `d55fa1de9254ddfa75271eb96c9faf32` (root observation `853ee1d5da651b07`) có cùng `correlation_id=req-241121c9`. Root `lab-agent-run` mất 2.66 giây; child `retrieval` chiếm 2.50 giây, còn `generation` chỉ mất 0.15 giây, nên retrieval là span gây ảnh hưởng.
- **Root cause:** Bước retrieval/vector store bị tăng độ trễ khoảng 2.5 giây. LLM generation và TTFT vẫn bình thường, đồng thời retrieval không thất bại, nên đây là sự cố latency của dependency retrieval chứ không phải lỗi model hay lỗi request.
- **Fix action:** Đặt timeout cho retrieval, tối ưu truy vấn/vector index, bổ sung cache cho truy vấn lặp lại và chuyển sang fallback an toàn khi dependency vượt latency budget.
- **Preventive measure:** Theo dõi riêng P95/P99 của span retrieval, cảnh báo khi retrieval latency vượt budget liên tục, thêm circuit breaker/fallback và chạy kiểm thử tải định kỳ để phát hiện suy giảm trước khi P95 toàn request vượt SLO.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Tôi đặt processor scrub PII trước bước ghi JSONL và chỉ gửi các preview đã scrub sang Langfuse. Quyết định này giúp log và trace vẫn đủ dữ liệu điều tra nhưng không lưu input/output thô có thể chứa PII.
- **Một lỗi/blocker đã gặp:** Khi chạy challenge lần đầu, API trả `tracing_enabled=false`, nên log được tạo nhưng Langfuse không nhận trace tương ứng.
- **Cách tìm nguyên nhân và xử lý:** Tôi kiểm tra `/health`, xác nhận biến Langfuse chưa được nạp vào tiến trình API, sau đó khởi động lại Uvicorn với `--env-file .env` và chạy lại workload. Lượt chạy mới tạo được log và trace có cùng correlation ID.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics cho biết latency P95/P99 vượt ngưỡng và xác định khoảng sự cố. Từ structured log, tôi chọn request `req-241121c9` có latency 2657 ms. Trace `d55fa1de9254ddfa75271eb96c9faf32` cho thấy retrieval mất 2.50 giây trong tổng 2.66 giây, qua đó xác định retrieval là nguyên nhân.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt version giúp so sánh baseline và candidate, đồng thời cho phép rollback production khi candidate gây suy giảm. Token và cost giúp phát hiện output bất thường; SLO và error budget xác định mức suy giảm có thể chấp nhận trước khi cần can thiệp.
- **Điều quan trọng nhất đã học:** Correlation ID là khóa nối metric, structured log và distributed trace để đi từ triệu chứng tổng thể tới đúng request và span gây ảnh hưởng.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Dashboard hiện đọc JSONL trong tiến trình và quality score chỉ là heuristic; hệ thống thực tế cần metrics backend, alert delivery, quality evaluation và lưu trữ tập trung. Traffic threshold cũng có thể báo breached khi workload thử nghiệm nhỏ trong cửa sổ 60 phút.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
