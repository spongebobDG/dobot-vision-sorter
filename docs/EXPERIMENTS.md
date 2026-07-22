# Experiment log template

정량 결과를 README로 옮기기 전에 이 문서에 원시 조건과 반복 횟수를 기록합니다.

## Environment

- Date:
- Commit SHA:
- Camera / resolution:
- GPU / CPU:
- Dobot model / firmware:
- Model weights SHA-256:
- Dataset version:
- Calibration file SHA-256:

## Vision benchmark

| Metric | Normal | Defect | Overall |
|---|---:|---:|---:|
| Precision | TBD | TBD | TBD |
| Recall | TBD | TBD | TBD |
| F1 | TBD | TBD | TBD |
| Mask mAP50 | - | - | TBD |
| Mask mAP50-95 | - | - | TBD |

- Test images:
- Test objects:
- Inference latency mean / P95:
- FPS:
- Confidence threshold:

## Calibration benchmark

- Calibration points:
- Held-out validation points:
- Mean error (mm):
- P95 error (mm):
- Maximum error (mm):

## Robot benchmark

최소 100회 이상의 독립 선별 시도를 권장합니다.

| Metric | Result |
|---|---:|
| Pick success | TBD |
| Correct class placement | TBD |
| Position error mean / P95 | TBD |
| Angle error mean / P95 | TBD |
| Cycle time mean / P95 | TBD |
| Automatic recovery success | TBD |

## Failure cases

각 실패마다 원본 프레임, 예측 결과, 로봇 상태, 원인, 개선 조치를 기록합니다.

| ID | Condition | Failure | Root cause | Action |
|---|---|---|---|---|
| F-001 | TBD | TBD | TBD | TBD |
