# Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: `high_request_latency`
- Severity: `high`
- Duration: `5m`
- Kênh thông báo: Slack `#llmops-alerts`
- SLI/SLO liên quan: P95 latency và SLO `fast_successful_requests`.
- Điều kiện và thời gian duy trì: `latency_p95_ms > 3000` liên tục 5 phút.
- Ảnh hưởng tới người dùng: phản hồi chậm, timeout phía client và giảm trải nghiệm hội thoại.
- Ba bước kiểm tra đầu tiên:
  1. Xác nhận P95/P99 và TTFT trên dashboard trong cùng cửa sổ 60 phút.
  2. Lọc các `response_sent` chậm nhất và lấy `correlation_id`.
  3. Mở trace cùng ID, so sánh thời gian của `retrieval` và `generation`.
- Mitigation tạm thời: tắt practice incident nếu đang bật; giảm concurrency hoặc chuyển prompt về version ổn định trong khi điều tra dependency chậm.
- Owner: `platform-oncall`

## Alert 2

- Tên: `elevated_request_errors`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#llmops-alerts`
- SLI/SLO liên quan: error rate tối đa 2% và retrieval success tối thiểu 90%.
- Điều kiện và thời gian duy trì: `error_rate_pct > 2` hoặc `retrieval_success_rate_pct < 90` liên tục 5 phút.
- Ảnh hưởng tới người dùng: request thất bại hoặc câu trả lời thiếu retrieved context.
- Ba bước kiểm tra đầu tiên:
  1. Xem error breakdown và retrieval success trên dashboard.
  2. Lọc `request_failed`, ghi lại `error_type` và `correlation_id`.
  3. Mở trace cùng ID, kiểm tra trạng thái observation `retrieval` trước `generation`.
- Mitigation tạm thời: tắt incident `tool_fail`, dùng fallback an toàn và giảm traffic tới dependency retrieval lỗi.
- Owner: `platform-oncall`

## Alert 3

- Tên: `degraded_answer_quality`
- Severity: `medium`
- Duration: `10m`
- Kênh thông báo: Slack `#llmops-alerts`
- SLI/SLO liên quan: quality proxy trung bình tối thiểu 0.75.
- Điều kiện và thời gian duy trì: `quality_score_avg < 0.75` liên tục 10 phút.
- Ảnh hưởng tới người dùng: câu trả lời kém liên quan hoặc không tận dụng context.
- Ba bước kiểm tra đầu tiên:
  1. So sánh quality proxy theo feature và prompt version.
  2. Kiểm tra retrieval success, token output và trace generation của các request điểm thấp.
  3. Đối chiếu label `production` với prompt version vừa promote.
- Mitigation tạm thời: rollback label `production` về prompt baseline đã xác minh và theo dõi lại quality trong 10 phút.
- Owner: `llm-oncall`
