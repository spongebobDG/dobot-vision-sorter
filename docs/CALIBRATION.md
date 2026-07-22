# Camera-to-robot calibration

## Why held-out validation matters

2D 호모그래피는 4개의 점 대응으로 결정할 수 있습니다. 정확히 4개 점으로 행렬을 만든 뒤 같은 4개 점에서 오차를 계산하면 거의 0이 나올 수 있지만, 작업 영역 내부의 실제 좌표 정확도를 의미하지 않습니다.

이 저장소는 최소 6개 보정점과 최소 4개 미사용 검증점을 요구합니다. 실제 실험에서는 작업 영역 전반에 분포한 12개 이상의 보정점과 8개 이상의 검증점을 권장합니다.

## Input format

`configs/correspondences.example.json`을 `calibration/correspondences.json`으로 복사한 뒤 다음 형식으로 입력합니다.

```json
{
  "camera": {
    "center_robot_mm": [241.0, 0.0],
    "height_mm": 350.0
  },
  "object_height_mm": 20.0,
  "calibration_points": [
    {"pixel": [100, 100], "robot": [300.0, 100.0]}
  ],
  "validation_points": [
    {"pixel": [200, 200], "robot": [250.0, 50.0]}
  ]
}
```

위 숫자는 형식 설명일 뿐 실제 보정값이 아닙니다.

## Fit and validate

```bash
python scripts/fit_calibration.py calibration/correspondences.json \
  --output calibration/calibration.json \
  --max-mean-error-mm 3.0 \
  --max-max-error-mm 7.0
```

출력에는 평균, P95, 최대 검증 오차가 기록됩니다. 기준을 통과하지 않은 파일은 `run_sorter.py`가 거부합니다.

## Additional checks

- 카메라 렌즈 왜곡이 크면 호모그래피 전에 intrinsic calibration을 적용합니다.
- 보정 당시와 실행 당시의 카메라 높이와 각도가 달라지면 다시 보정합니다.
- 호모그래피는 테이블 평면을 기준으로 하므로 블록 상단 중심에는 높이 보정이 필요합니다.
- 검증점은 모서리뿐 아니라 작업 영역 중앙에도 분포시킵니다.
- 로봇 TCP와 그리퍼 중심 오프셋은 별도의 반복 측정으로 기록합니다.
