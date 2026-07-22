# Local dataset layout

실제 이미지는 Git에서 제외됩니다. `data/dataset.yaml.example`을 `data/dataset.yaml`로 복사하고 아래 구조로 준비합니다.

```text
data/processed/
├── train/
│   ├── images/
│   └── labels/
├── val/
│   ├── images/
│   └── labels/
└── test/
    ├── images/
    └── labels/
```
