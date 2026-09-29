"""Small labeled evaluation dataset for handwriting detection.

IMPORTANT LIMITATION: there are no real handwritten drilling documents
in this repository.  This dataset uses synthetic proxies -- script
fonts (Bradley Hand / Brush Script) rendered with per-character
rotation/position jitter -- calibrated (see tests/test_handwriting.py
module docstring) to approximate the OCR-confidence degradation real
handwriting produces.  Metrics computed here characterize the
detector's behavior on this proxy dataset, NOT its accuracy on real
handwritten documents.  Treat these numbers as a regression check,
not a claim of real-world handwriting-recognition accuracy.

Ambiguous cases (blank pages, extreme noise, very low resolution) are
deliberately excluded from the labeled set because they lack a
non-arbitrary ground-truth label -- see docs/handwriting_detection.md
"Evaluation Limitations" for the qualitative behavior on those cases
instead of fabricated ground truth.
"""

from __future__ import annotations

import io
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from .detector import detect_page
from .models import ContentClassification

_HELVETICA = "/System/Library/Fonts/Helvetica.ttc"
_SCRIPT_FONTS = [
    "/System/Library/Fonts/Supplemental/Brush Script.ttf",
    "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
]


@dataclass
class EvalSample:
    sample_id: str
    image_bytes: bytes
    true_label: ContentClassification
    description: str


@dataclass
class EvalPrediction:
    sample_id: str
    true_label: ContentClassification
    predicted_label: ContentClassification
    confidence: float


@dataclass
class ClassMetrics:
    label: str
    precision: float
    recall: float
    f1: float
    support: int


@dataclass
class EvaluationReport:
    accuracy: float
    per_class: list[ClassMetrics] = field(default_factory=list)
    confusion_matrix: dict[str, dict[str, int]] = field(default_factory=dict)
    n_samples: int = 0
    predictions: list[EvalPrediction] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _typed_page(lines: list[str], font_size: int = 24, width: int = 700) -> bytes:
    line_h = int(font_size * 1.6)
    height = line_h * len(lines) + 40
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(_HELVETICA, font_size)
    y = 20
    for line in lines:
        draw.text((20, y), line, fill="black", font=font)
        y += line_h
    return _png_bytes(img)


def _handwritten_page(
    lines: list[str], font_path: str, font_size: int = 34,
    width: int = 700, jitter: int = 6, rot_range: float = 10.0, seed: int = 0,
) -> bytes:
    rng = random.Random(seed)
    line_h = int(font_size * 2.0)
    height = line_h * len(lines) + 40
    img = Image.new("RGB", (width, height), color="white")
    font = ImageFont.truetype(font_path, font_size)
    y = 20
    for line in lines:
        x = 20 + rng.randint(-2, 8)
        for ch in line:
            char_img = Image.new("RGBA", (font_size * 2, font_size * 2), (255, 255, 255, 0))
            cd = ImageDraw.Draw(char_img)
            cd.text((font_size // 2, font_size // 2), ch, fill="black", font=font)
            angle = rng.uniform(-rot_range, rot_range)
            char_img = char_img.rotate(angle, resample=Image.BICUBIC)
            dy = rng.randint(-jitter, jitter)
            img.paste(char_img, (int(x), y + dy), char_img)
            bbox = font.getbbox(ch)
            cw = (bbox[2] - bbox[0]) if bbox else font_size // 2
            x += (cw + rng.uniform(-2, 2)) if cw else font_size * 0.5
        y += line_h + rng.randint(-6, 8)
    return _png_bytes(img)


def _mixed_page(typed_lines: list[str], hw_lines: list[str], font_path: str, seed: int = 0) -> bytes:
    rng = random.Random(seed)
    width, height = 700, 420
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    font_typed = ImageFont.truetype(_HELVETICA, 24)
    y = 20
    for line in typed_lines:
        draw.text((20, y), line, fill="black", font=font_typed)
        y += 35

    font_hw = ImageFont.truetype(font_path, 34)
    y = 180
    for line in hw_lines:
        x = 20
        for ch in line:
            char_img = Image.new("RGBA", (68, 68), (255, 255, 255, 0))
            cd = ImageDraw.Draw(char_img)
            cd.text((17, 17), ch, fill="black", font=font_hw)
            angle = rng.uniform(-10, 10)
            char_img = char_img.rotate(angle, resample=Image.BICUBIC)
            dy = rng.randint(-6, 6)
            img.paste(char_img, (int(x), y + dy), char_img)
            bbox = font_hw.getbbox(ch)
            cw = (bbox[2] - bbox[0]) if bbox else 17
            x += (cw + rng.uniform(-2, 2)) if cw else 17
        y += 70
    draw.text((20, 340), "Reviewed by: J. Smith", fill="black", font=font_typed)
    return _png_bytes(img)


def build_evaluation_dataset() -> list[EvalSample]:
    """Builds the 11-sample labeled synthetic evaluation set."""
    samples: list[EvalSample] = []

    typed_docs = [
        ["DAILY DRILLING REPORT", "Well: 15/3-1  Date: 2024-01-15", "Depth: 3200 m  Formation: Draupne"],
        ["WELLBORE COMPLETION SUMMARY", "Field: Sleipner  Operator: Equinor", "Status: Completed"],
        ["CASING RUN REPORT", "Casing size: 9-5/8 in", "Set depth: 2850 m"],
        ["MUD PROGRAM", "Mud type: WBM  Density: 1.35 sg", "Viscosity: 45 cP"],
    ]
    for i, lines in enumerate(typed_docs):
        samples.append(EvalSample(
            sample_id=f"typed_{i}", image_bytes=_typed_page(lines),
            true_label=ContentClassification.TYPED,
            description=f"Typed report page ({lines[0]})",
        ))

    hw_docs = [
        (["Losses increasing at 3215m", "mud loss noted check pit levels"], _SCRIPT_FONTS[0], 42),
        (["formation appears fractured here", "will monitor closely tomorrow"], _SCRIPT_FONTS[1], 7),
        (["stuck pipe suspected at 2900m", "working pipe free slowly"], _SCRIPT_FONTS[0], 15),
        (["torque spike observed this shift", "reduce WOB and continue"], _SCRIPT_FONTS[1], 99),
    ]
    for i, (lines, font, seed) in enumerate(hw_docs):
        samples.append(EvalSample(
            sample_id=f"handwritten_{i}",
            image_bytes=_handwritten_page(lines, font, seed=seed),
            true_label=ContentClassification.HANDWRITTEN,
            description=f"Handwritten annotation ({lines[0]})",
        ))

    mixed_docs = [
        (["DAILY DRILLING REPORT", "Well: 15/3-1   Depth: 3200 m", "Formation: Draupne"],
         ["Losses increasing here", "check mud pit levels"], _SCRIPT_FONTS[0], 3),
        (["CEMENTING REPORT", "Well: 16/2-3   Stage: 2"],
         ["top of cement uncertain", "recommend log verification"], _SCRIPT_FONTS[1], 21),
        (["DIRECTIONAL SURVEY", "MD: 2500 m   Inc: 12 deg"],
         ["survey point questioned", "resurvey next run"], _SCRIPT_FONTS[0], 55),
    ]
    for i, (typed_lines, hw_lines, font, seed) in enumerate(mixed_docs):
        samples.append(EvalSample(
            sample_id=f"mixed_{i}",
            image_bytes=_mixed_page(typed_lines, hw_lines, font, seed=seed),
            true_label=ContentClassification.MIXED,
            description=f"Mixed typed/handwritten page ({typed_lines[0]})",
        ))

    return samples


def _get_ocr_data(image_bytes: bytes) -> Optional[dict]:
    try:
        import pytesseract

        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        return pytesseract.image_to_data(img, lang="eng", output_type=pytesseract.Output.DICT)
    except Exception:
        return None


def run_evaluation(samples: Optional[list[EvalSample]] = None) -> EvaluationReport:
    """Run detection on the labeled dataset and compute classification metrics."""
    samples = samples or build_evaluation_dataset()
    predictions: list[EvalPrediction] = []

    for sample in samples:
        ocr_data = _get_ocr_data(sample.image_bytes)
        detection = detect_page(sample.image_bytes, ocr_data, page_number=1)
        predictions.append(EvalPrediction(
            sample_id=sample.sample_id,
            true_label=sample.true_label,
            predicted_label=detection.classification,
            confidence=detection.confidence,
        ))

    labels = [ContentClassification.TYPED, ContentClassification.HANDWRITTEN, ContentClassification.MIXED]
    label_names = [l.value for l in labels]

    confusion: dict[str, dict[str, int]] = {t: {p: 0 for p in label_names + ["unknown"]} for t in label_names}
    for pred in predictions:
        t = pred.true_label.value
        p = pred.predicted_label.value
        if t in confusion:
            confusion[t][p] = confusion[t].get(p, 0) + 1

    per_class = []
    for label in label_names:
        tp = confusion.get(label, {}).get(label, 0)
        fn = sum(confusion.get(label, {}).values()) - tp
        fp = sum(confusion.get(t, {}).get(label, 0) for t in label_names if t != label)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        support = sum(confusion.get(label, {}).values())
        per_class.append(ClassMetrics(label=label, precision=round(precision, 3), recall=round(recall, 3), f1=round(f1, 3), support=support))

    correct = sum(1 for p in predictions if p.predicted_label == p.true_label)
    accuracy = correct / len(predictions) if predictions else 0.0

    return EvaluationReport(
        accuracy=round(accuracy, 3),
        per_class=per_class,
        confusion_matrix=confusion,
        n_samples=len(predictions),
        predictions=predictions,
        limitations=[
            "Dataset is synthetic (script-font proxies), not real handwritten documents.",
            "Classification accuracy on this dataset does not indicate accuracy on real "
            "handwriting; real handwriting typically has more erratic strokes and lower "
            "OCR confidence than clean vector script fonts.",
            "Region-level localization is not evaluated here (no reliable pixel-level "
            "ground truth available) -- see tests/test_handwriting.py for qualitative "
            "region-detection checks.",
            "Blank, noisy, and low-resolution pages are excluded from these metrics "
            "because they lack a non-arbitrary classification ground truth.",
        ],
    )


def format_report_markdown(report: EvaluationReport) -> str:
    lines = [
        "# Handwriting Detection Evaluation Report",
        "",
        f"**Accuracy:** {report.accuracy:.1%} ({report.n_samples} samples)",
        "",
        "## Per-Class Metrics",
        "",
        "| Class | Precision | Recall | F1 | Support |",
        "|-------|-----------|--------|-----|---------|",
    ]
    for cm in report.per_class:
        lines.append(f"| {cm.label} | {cm.precision:.3f} | {cm.recall:.3f} | {cm.f1:.3f} | {cm.support} |")

    lines.extend(["", "## Confusion Matrix (rows=true, cols=predicted)", ""])
    pred_labels = sorted(next(iter(report.confusion_matrix.values())).keys()) if report.confusion_matrix else []
    lines.append("| true \\ pred | " + " | ".join(pred_labels) + " |")
    lines.append("|" + "---|" * (len(pred_labels) + 1))
    for true_label, row in report.confusion_matrix.items():
        lines.append(f"| {true_label} | " + " | ".join(str(row.get(p, 0)) for p in pred_labels) + " |")

    lines.extend(["", "## Limitations", ""])
    for lim in report.limitations:
        lines.append(f"- {lim}")

    return "\n".join(lines)


def save_report(report: EvaluationReport, out_dir: Optional[Path] = None) -> None:
    import json
    from dataclasses import asdict

    out_dir = out_dir or Path(__file__).resolve().parent.parent.parent / "data" / "evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)

    report_dict = asdict(report)
    for pred in report_dict["predictions"]:
        pred["true_label"] = pred["true_label"].value if hasattr(pred["true_label"], "value") else pred["true_label"]
        pred["predicted_label"] = pred["predicted_label"].value if hasattr(pred["predicted_label"], "value") else pred["predicted_label"]

    with open(out_dir / "handwriting_detection_report.json", "w") as f:
        json.dump(report_dict, f, indent=2, default=str)

    with open(out_dir / "handwriting_detection_report.md", "w") as f:
        f.write(format_report_markdown(report))


if __name__ == "__main__":
    report = run_evaluation()
    print(format_report_markdown(report))
    save_report(report)
