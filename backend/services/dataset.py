import io
import json
import math
import os
import random
import re
import shutil
import zipfile
from datetime import datetime

import cv2
import numpy as np

DATASETS_DIR = "datasets"
DATASET_SCHEMA_VERSION = 2
DATASET_TASKS = {"detect", "segment", "classify_single", "classify_multi", "pose"}
DEFAULT_POSE_TEMPLATES = {
    "Box Corners": {
        "name": "Box Corners",
        "keypoint_names": ["top_left", "top_right", "bottom_right", "bottom_left"],
        "skeleton": [[0, 1], [1, 2], [2, 3], [3, 0]],
        "flip_idx": [1, 0, 3, 2],
        "kpt_shape": [4, 3],
    },
}
CLASS_COLOR_PALETTE = [
    "#3ECF8E",
    "#2563EB",
    "#F59E0B",
    "#EF4444",
    "#8B5CF6",
    "#14B8A6",
    "#EC4899",
    "#84CC16",
    "#06B6D4",
    "#F97316",
    "#6366F1",
    "#22C55E",
    "#EAB308",
    "#A855F7",
    "#0EA5E9",
    "#F43F5E",
]
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class DatasetService:
    def _sanitize_filename(self, filename: str | None, fallback: str) -> str:
        if not filename:
            return fallback
        base = os.path.basename(filename.strip())
        if not base:
            return fallback
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-.")
        return cleaned or fallback

    def _project_dir(self, name: str) -> str:
        return os.path.join(DATASETS_DIR, name)

    def _meta_path(self, name: str) -> str:
        return os.path.join(self._project_dir(name), "meta.json")

    def _read_meta(self, name: str) -> dict:
        with open(self._meta_path(name)) as f:
            return json.load(f)

    def _write_meta(self, name: str, meta: dict):
        with open(self._meta_path(name), "w") as f:
            json.dump(meta, f, indent=2)

    def _next_img_id(self, meta: dict) -> str:
        counter = meta.get("next_id", 1)
        return f"img_{counter:04d}"

    def _default_class_color(self, index: int) -> str:
        return CLASS_COLOR_PALETTE[index % len(CLASS_COLOR_PALETTE)]

    def _ensure_class_colors(self, meta: dict) -> bool:
        class_to_id = meta.get("class_to_id", {})
        class_colors = meta.setdefault("class_colors", {})
        changed = False
        for label, class_id in sorted(class_to_id.items(), key=lambda item: item[1]):
            if label and label not in class_colors:
                class_colors[label] = self._default_class_color(int(class_id))
                changed = True
        return changed

    def _normalize_color(self, color) -> str:
        if not isinstance(color, str) or not HEX_COLOR_RE.match(color.strip()):
            raise ValueError("color must be a #RRGGBB hex value")
        return color.strip().upper()

    def _default_task_config(self, task_type: str) -> dict:
        if task_type == "segment":
            return {"requires_masks": True}
        if task_type == "classify_single":
            return {"classification_mode": "single"}
        if task_type == "classify_multi":
            return {"classification_mode": "multi"}
        if task_type == "pose":
            return {"pose_template": DEFAULT_POSE_TEMPLATES["Box Corners"]}
        return {}

    def _validate_pose_template(self, template: dict) -> dict:
        names = template.get("keypoint_names")
        skeleton = template.get("skeleton", [])
        flip_idx = template.get("flip_idx")
        kpt_shape = template.get("kpt_shape")
        if not isinstance(names, list) or not names or not all(isinstance(n, str) and n.strip() for n in names):
            raise ValueError("pose_template.keypoint_names must be a non-empty string list")
        if kpt_shape != [len(names), 3]:
            raise ValueError("pose_template.kpt_shape must equal [len(keypoint_names), 3]")
        if not isinstance(flip_idx, list) or sorted(flip_idx) != list(range(len(names))):
            raise ValueError("pose_template.flip_idx must map every keypoint index")
        for edge in skeleton:
            if not isinstance(edge, list) or len(edge) != 2:
                raise ValueError("pose_template.skeleton edges must be [from, to]")
            if edge[0] < 0 or edge[1] < 0 or edge[0] >= len(names) or edge[1] >= len(names):
                raise ValueError("pose_template.skeleton contains an invalid keypoint index")
        return {
            "name": str(template.get("name") or "Custom"),
            "keypoint_names": [n.strip() for n in names],
            "skeleton": skeleton,
            "flip_idx": flip_idx,
            "kpt_shape": kpt_shape,
        }

    def _normalize_task_config(self, task_type: str, task_config: dict | None) -> dict:
        config = self._default_task_config(task_type)
        if task_config:
            config.update(task_config)
        if task_type == "pose":
            config["pose_template"] = self._validate_pose_template(config.get("pose_template") or {})
        return config

    def _recalc_stats(self, name: str) -> dict:
        ann_dir = os.path.join(self._project_dir(name), "annotations")
        total_images = 0
        total_annotations = 0
        accepted = 0
        rejected = 0
        classes: set[str] = set()
        class_counts: dict[str, int] = {}

        for fname in os.listdir(ann_dir):
            if not fname.endswith(".json"):
                continue
            total_images += 1
            with open(os.path.join(ann_dir, fname)) as f:
                ann = json.load(f)
            for det in ann.get("detections", []):
                total_annotations += 1
                label = det["label"]
                classes.add(label)
                class_counts[label] = class_counts.get(label, 0) + 1
                if det.get("accepted", True):
                    accepted += 1
                else:
                    rejected += 1
            for label_ann in ann.get("labels", []):
                total_annotations += 1
                label = label_ann["label"]
                classes.add(label)
                class_counts[label] = class_counts.get(label, 0) + 1
                if label_ann.get("accepted", True):
                    accepted += 1
                else:
                    rejected += 1
            for pose in ann.get("poses", []):
                total_annotations += 1
                label = pose["label"]
                classes.add(label)
                class_counts[label] = class_counts.get(label, 0) + 1
                if pose.get("accepted", True):
                    accepted += 1
                else:
                    rejected += 1

        return {
            "total_images": total_images,
            "total_annotations": total_annotations,
            "accepted": accepted,
            "rejected": rejected,
            "classes": sorted(classes),
            "class_counts": class_counts,
        }

    def list_projects(self) -> list[dict]:
        if not os.path.isdir(DATASETS_DIR):
            return []
        projects = []
        for name in sorted(os.listdir(DATASETS_DIR)):
            meta_path = os.path.join(DATASETS_DIR, name, "meta.json")
            if not os.path.isfile(meta_path):
                continue
            meta = self._read_meta(name)
            if self._ensure_class_colors(meta):
                self._write_meta(name, meta)
            stats = self._recalc_stats(name)
            projects.append({
                "name": name,
                "created": meta.get("created"),
                "schema_version": meta.get("schema_version", 1),
                "task_type": meta.get("task_type", "detect"),
                "task_config": meta.get("task_config", {}),
                "class_to_id": meta.get("class_to_id", {}),
                "class_colors": meta.get("class_colors", {}),
                "stats": stats,
            })
        return projects

    def create_project(
        self,
        name: str,
        classes: list[str] | None = None,
        task_type: str = "detect",
        task_config: dict | None = None,
    ) -> dict:
        if task_type not in DATASET_TASKS:
            raise ValueError("task_type must be one of: classify_multi, classify_single, detect, pose, segment")
        pdir = self._project_dir(name)
        if os.path.exists(pdir):
            raise FileExistsError(f"Dataset '{name}' already exists")
        os.makedirs(os.path.join(pdir, "images"))
        os.makedirs(os.path.join(pdir, "annotations"))

        classes = classes or []
        class_to_id = {c: i for i, c in enumerate(classes)}
        class_colors = {c: self._default_class_color(i) for c, i in class_to_id.items()}

        meta = {
            "schema_version": DATASET_SCHEMA_VERSION,
            "name": name,
            "created": datetime.now().isoformat(),
            "next_id": 1,
            "task_type": task_type,
            "task_config": self._normalize_task_config(task_type, task_config),
            "class_to_id": class_to_id,
            "class_colors": class_colors,
        }
        self._write_meta(name, meta)
        return meta

    def delete_project(self, name: str):
        pdir = self._project_dir(name)
        if not os.path.isdir(pdir):
            raise FileNotFoundError(f"Dataset '{name}' not found")
        shutil.rmtree(pdir)

    def _preview_detection(self, det: dict) -> dict:
        preview = {
            "id": det.get("id", 0),
            "box": det.get("box", []),
            "label": det.get("label", ""),
            "confidence": det.get("confidence", 0),
            "cls_id": det.get("cls_id", -1),
            "accepted": det.get("accepted", True),
        }
        if "mask" in det:
            preview["mask"] = det["mask"]
        if "mask_rle" in det:
            preview["mask_rle"] = det["mask_rle"]
        if "manual" in det:
            preview["manual"] = det["manual"]
        return preview

    def save_image(
        self,
        name: str,
        image_bytes: bytes,
        detections: list[dict],
        source: str = "inference",
        original_filename: str | None = None,
    ) -> dict:
        pdir = self._project_dir(name)
        if not os.path.isdir(pdir):
            raise FileNotFoundError(f"Dataset '{name}' not found")

        meta = self._read_meta(name)
        img_id = self._next_img_id(meta)

        # Decode image to get dimensions
        arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Invalid image data")
        h, w = img.shape[:2]

        # Detect extension from original bytes
        ext = ".jpg"
        if image_bytes[:4] == b"\x89PNG":
            ext = ".png"

        # Save original image
        img_filename = f"{img_id}{ext}"
        img_path = os.path.join(pdir, "images", img_filename)
        with open(img_path, "wb") as f:
            f.write(image_bytes)

        # Update class mapping with new labels
        class_to_id = meta.get("class_to_id", {})
        for det in detections:
            label = det.get("label", "")
            if label and label not in class_to_id:
                class_to_id[label] = len(class_to_id)
        meta["class_to_id"] = class_to_id
        self._ensure_class_colors(meta)

        # Add accepted flag and id to detections
        annotated_dets = []
        for i, det in enumerate(detections):
            annotated_dets.append({
                "id": i,
                "box": det.get("box", []),
                "label": det.get("label", ""),
                "confidence": det.get("confidence", 0),
                "cls_id": class_to_id.get(det.get("label", ""), -1),
                "accepted": True,
                **({"mask": det["mask"]} if "mask" in det else {}),
                **({"mask_rle": det["mask_rle"]} if "mask_rle" in det else {}),
            })

        # Save annotation
        ann = {
            "image": img_filename,
            "original_filename": self._sanitize_filename(original_filename, img_filename),
            "width": w,
            "height": h,
            "source": source,
            "created": datetime.now().isoformat(),
            "task_type": meta.get("task_type", "detect"),
            "labeled": True,
            "detections": annotated_dets,
        }
        ann_path = os.path.join(pdir, "annotations", f"{img_id}.json")
        with open(ann_path, "w") as f:
            json.dump(ann, f, indent=2)

        # Update meta
        meta["next_id"] = meta.get("next_id", 1) + 1
        self._write_meta(name, meta)

        return {
            "img_id": img_id,
            "image": img_filename,
            "detections_count": len(annotated_dets),
        }

    def upload_raw(
        self,
        name: str,
        image_bytes: bytes,
        source: str = "upload",
        original_filename: str | None = None,
    ) -> dict:
        """Upload image without inference. Creates empty annotation placeholder."""
        pdir = self._project_dir(name)
        if not os.path.isdir(pdir):
            raise FileNotFoundError(f"Dataset '{name}' not found")

        meta = self._read_meta(name)
        img_id = self._next_img_id(meta)

        arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Invalid image data")
        h, w = img.shape[:2]

        ext = ".jpg"
        if image_bytes[:4] == b"\x89PNG":
            ext = ".png"

        img_filename = f"{img_id}{ext}"
        img_path = os.path.join(pdir, "images", img_filename)
        with open(img_path, "wb") as f:
            f.write(image_bytes)

        # Save empty annotation (no detections, labeled=false)
        ann = {
            "image": img_filename,
            "original_filename": self._sanitize_filename(original_filename, img_filename),
            "width": w,
            "height": h,
            "source": source,
            "created": datetime.now().isoformat(),
            "task_type": meta.get("task_type", "detect"),
            "labeled": False,
            "detections": [],
        }
        ann_path = os.path.join(pdir, "annotations", f"{img_id}.json")
        with open(ann_path, "w") as f:
            json.dump(ann, f, indent=2)

        meta["next_id"] = meta.get("next_id", 1) + 1
        self._write_meta(name, meta)

        return {"img_id": img_id, "image": img_filename}

    def get_unlabeled_images(self, name: str) -> list[str]:
        """Return list of img_ids that have no detections (labeled=false)."""
        pdir = self._project_dir(name)
        ann_dir = os.path.join(pdir, "annotations")
        if not os.path.isdir(ann_dir):
            return []

        unlabeled = []
        for fname in sorted(os.listdir(ann_dir)):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(ann_dir, fname)) as f:
                ann = json.load(f)
            if not ann.get("labeled", True):
                img_id = os.path.splitext(fname)[0]
                unlabeled.append(img_id)
        return unlabeled

    def label_image(self, name: str, img_id: str, detections: list[dict]) -> dict | None:
        """Add detection results to an existing unlabeled image."""
        pdir = self._project_dir(name)
        ann_path = os.path.join(pdir, "annotations", f"{img_id}.json")
        if not os.path.isfile(ann_path):
            return None

        with open(ann_path) as f:
            ann = json.load(f)

        meta = self._read_meta(name)
        class_to_id = meta.get("class_to_id", {})

        annotated_dets = []
        for i, det in enumerate(detections):
            label = det.get("label", "")
            if label and label not in class_to_id:
                class_to_id[label] = len(class_to_id)
            annotated_dets.append({
                "id": i,
                "box": det.get("box", []),
                "label": label,
                "confidence": det.get("confidence", 0),
                "cls_id": class_to_id.get(label, -1),
                "accepted": True,
                **({"mask": det["mask"]} if "mask" in det else {}),
                **({"mask_rle": det["mask_rle"]} if "mask_rle" in det else {}),
            })

        ann["labeled"] = True
        ann["detections"] = annotated_dets

        meta["class_to_id"] = class_to_id
        self._ensure_class_colors(meta)
        self._write_meta(name, meta)

        with open(ann_path, "w") as f:
            json.dump(ann, f, indent=2)

        return {
            "img_id": img_id,
            "detections_count": len(annotated_dets),
        }

    def list_images(self, name: str, page: int = 1, limit: int = 20) -> dict:
        pdir = self._project_dir(name)
        if not os.path.isdir(pdir):
            raise FileNotFoundError(f"Dataset '{name}' not found")

        img_dir = os.path.join(pdir, "images")
        ann_dir = os.path.join(pdir, "annotations")

        all_images = []
        for fname in sorted(os.listdir(img_dir)):
            if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            img_id = os.path.splitext(fname)[0]
            ann_path = os.path.join(ann_dir, f"{img_id}.json")

            status = "new"
            accepted_count = 0
            rejected_count = 0
            detections_preview = []
            ann = {}
            if os.path.isfile(ann_path):
                with open(ann_path) as f:
                    ann = json.load(f)
                dets = ann.get("detections", [])
                label_anns = ann.get("labels", [])
                pose_anns = ann.get("poses", [])
                detections_preview = [self._preview_detection(det) for det in dets]
                annotation_items = [*dets, *label_anns, *pose_anns]
                if not ann.get("labeled", True) and len(annotation_items) == 0:
                    status = "unlabeled"
                else:
                    for item in annotation_items:
                        if item.get("accepted", True):
                            accepted_count += 1
                        else:
                            rejected_count += 1
                    status = "accepted" if rejected_count == 0 else "review"

            all_images.append({
                "img_id": img_id,
                "filename": fname,
                "image_url": f"/api/datasets/{name}/images/{img_id}/file",
                "status": status,
                "accepted": accepted_count,
                "rejected": rejected_count,
                "source": ann.get("source") if os.path.isfile(ann_path) else None,
                "width": ann.get("width") if os.path.isfile(ann_path) else None,
                "height": ann.get("height") if os.path.isfile(ann_path) else None,
                "detections_preview": detections_preview,
            })

        total = len(all_images)
        start = (page - 1) * limit
        page_images = all_images[start:start + limit]

        return {
            "images": page_images,
            "total": total,
            "page": page,
            "limit": limit,
        }

    def get_image(self, name: str, img_id: str) -> dict | None:
        pdir = self._project_dir(name)
        img_dir = os.path.join(pdir, "images")
        ann_dir = os.path.join(pdir, "annotations")

        # Find image file
        img_path = None
        img_filename = None
        for ext in (".jpg", ".jpeg", ".png"):
            candidate = os.path.join(img_dir, f"{img_id}{ext}")
            if os.path.isfile(candidate):
                img_path = candidate
                img_filename = f"{img_id}{ext}"
                break

        if img_path is None:
            return None

        ann_path = os.path.join(ann_dir, f"{img_id}.json")
        annotations = None
        if os.path.isfile(ann_path):
            with open(ann_path) as f:
                annotations = json.load(f)

        return {
            "img_id": img_id,
            "filename": img_filename,
            "image_path": img_path,
            "annotations": annotations,
        }

    def delete_image(self, name: str, img_id: str) -> bool:
        pdir = self._project_dir(name)
        img_dir = os.path.join(pdir, "images")
        ann_dir = os.path.join(pdir, "annotations")

        deleted = False
        for ext in (".jpg", ".jpeg", ".png"):
            img_path = os.path.join(img_dir, f"{img_id}{ext}")
            if os.path.isfile(img_path):
                os.remove(img_path)
                deleted = True

        ann_path = os.path.join(ann_dir, f"{img_id}.json")
        if os.path.isfile(ann_path):
            os.remove(ann_path)
            deleted = True

        return deleted


    def _ensure_class(self, name: str, label: str) -> int:
        meta = self._read_meta(name)
        class_to_id = meta.get("class_to_id", {})
        if label not in class_to_id:
            class_to_id[label] = len(class_to_id)
            meta["class_to_id"] = class_to_id
        self._ensure_class_colors(meta)
        self._write_meta(name, meta)
        return class_to_id[label]

    def _annotation_path(self, name: str, img_id: str) -> str:
        return os.path.join(self._project_dir(name), "annotations", f"{img_id}.json")

    def _read_annotation(self, name: str, img_id: str) -> dict | None:
        ann_path = self._annotation_path(name, img_id)
        if not os.path.isfile(ann_path):
            return None
        with open(ann_path) as f:
            return json.load(f)

    def _write_annotation(self, name: str, img_id: str, ann: dict):
        with open(self._annotation_path(name, img_id), "w") as f:
            json.dump(ann, f, indent=2)

    def _project_task_type(self, name: str) -> str:
        return self._read_meta(name).get("task_type", "detect")

    def set_image_labels(self, name: str, img_id: str, labels: list[dict]) -> dict | None:
        ann = self._read_annotation(name, img_id)
        if ann is None:
            return None
        task_type = self._project_task_type(name)
        if task_type not in {"classify_single", "classify_multi"}:
            raise ValueError("image labels are only supported for classification datasets")
        if not isinstance(labels, list) or not labels:
            raise ValueError("labels must be a non-empty list")
        if task_type == "classify_single" and len(labels) > 1:
            raise ValueError("single-label classification accepts one label per image")

        annotated_labels = []
        for idx, item in enumerate(labels):
            label = self._clean_label(item.get("label"))
            cls_id = self._ensure_class(name, label)
            confidence = item.get("confidence", 1.0)
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = 1.0
            if not math.isfinite(confidence):
                confidence = 1.0
            annotated_labels.append({
                "id": idx,
                "label": label,
                "confidence": confidence,
                "cls_id": cls_id,
                "accepted": bool(item.get("accepted", True)),
                "source": item.get("source", "manual"),
            })

        ann["task_type"] = task_type
        ann["labels"] = annotated_labels
        ann["labeled"] = any(label.get("accepted", True) for label in annotated_labels)
        self._write_annotation(name, img_id, ann)
        return ann

    def _clean_keypoints(self, keypoints, template: dict, width: int, height: int) -> list[dict]:
        if not isinstance(keypoints, list):
            raise ValueError("keypoints must be a list")
        names = template.get("keypoint_names", [])
        if len(keypoints) != len(names):
            raise ValueError("keypoints must match the dataset pose template")
        cleaned = []
        by_name = {kp.get("name"): kp for kp in keypoints if isinstance(kp, dict)}
        allowed_visibility = {"visible", "occluded", "missing"}
        for name in names:
            raw = by_name.get(name)
            if raw is None:
                raise ValueError(f"missing keypoint '{name}'")
            visibility = raw.get("visibility", "visible")
            if visibility not in allowed_visibility:
                raise ValueError("keypoint visibility must be visible, occluded, or missing")
            try:
                x = float(raw.get("x", 0))
                y = float(raw.get("y", 0))
            except (TypeError, ValueError):
                raise ValueError("keypoint coordinates must be finite numbers")
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("keypoint coordinates must be finite numbers")
            cleaned.append({
                "name": name,
                "x": min(max(x, 0.0), float(width)),
                "y": min(max(y, 0.0), float(height)),
                "visibility": visibility,
            })
        return cleaned

    def add_pose(self, name: str, img_id: str, payload: dict) -> dict | None:
        ann = self._read_annotation(name, img_id)
        if ann is None:
            return None
        meta = self._read_meta(name)
        if meta.get("task_type") != "pose":
            raise ValueError("pose annotations are only supported for pose datasets")

        label = self._clean_label(payload.get("label"))
        box = self._clean_box(payload.get("box"), ann["width"], ann["height"])
        cls_id = self._ensure_class(name, label)
        template = meta.get("task_config", {}).get("pose_template", {})
        keypoints = self._clean_keypoints(payload.get("keypoints"), template, ann["width"], ann["height"])
        poses = ann.setdefault("poses", [])
        next_id = max((int(pose.get("id", -1)) for pose in poses), default=-1) + 1
        confidence = payload.get("confidence", 1.0)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 1.0
        if not math.isfinite(confidence):
            confidence = 1.0

        poses.append({
            "id": next_id,
            "label": label,
            "box": box,
            "confidence": confidence,
            "cls_id": cls_id,
            "accepted": bool(payload.get("accepted", True)),
            "keypoints": keypoints,
        })
        ann["task_type"] = "pose"
        ann["labeled"] = True
        self._write_annotation(name, img_id, ann)
        return ann

    def update_class_color(self, name: str, label: str, color: str) -> dict:
        pdir = self._project_dir(name)
        if not os.path.isdir(pdir):
            raise FileNotFoundError(f"Dataset '{name}' not found")
        label = self._clean_label(label)
        normalized_color = self._normalize_color(color)
        meta = self._read_meta(name)
        class_to_id = meta.get("class_to_id", {})
        if label not in class_to_id:
            class_to_id[label] = len(class_to_id)
            meta["class_to_id"] = class_to_id
        self._ensure_class_colors(meta)
        meta["class_colors"][label] = normalized_color
        self._write_meta(name, meta)
        return meta

    def _annotation_label_collections(self, ann: dict) -> list[list[dict]]:
        return [
            ann.setdefault("detections", []),
            ann.setdefault("labels", []),
            ann.setdefault("poses", []),
        ]

    def _has_any_annotations(self, ann: dict) -> bool:
        for collection in self._annotation_label_collections(ann):
            if collection:
                return True
        return False

    def _update_annotation_label(self, ann: dict, old_label: str, new_label: str, cls_id: int | None = None) -> bool:
        changed = False
        for collection in self._annotation_label_collections(ann):
            for item in collection:
                if item.get("label") == old_label:
                    item["label"] = new_label
                    if cls_id is not None:
                        item["cls_id"] = cls_id
                    changed = True
        return changed

    def _remove_annotation_label(self, ann: dict, label: str) -> bool:
        changed = False
        for key in ("detections", "labels", "poses"):
            existing = ann.get(key, [])
            remaining = [item for item in existing if item.get("label") != label]
            if len(remaining) != len(existing):
                ann[key] = remaining
                changed = True
        if changed:
            ann["labeled"] = self._has_any_annotations(ann)
        return changed

    def rename_class(self, name: str, old_label: str, new_label: str) -> dict:
        """Rename a class across all annotations. Merges if new_label already exists."""
        pdir = self._project_dir(name)
        if not os.path.isdir(pdir):
            raise FileNotFoundError(f"Dataset '{name}' not found")
        old_label = self._clean_label(old_label)
        new_label = self._clean_label(new_label)
        if old_label == new_label:
            return self._read_meta(name)

        meta = self._read_meta(name)
        class_to_id = meta.get("class_to_id", {})
        class_colors = meta.get("class_colors", {})

        if old_label not in class_to_id:
            raise ValueError(f"Class '{old_label}' not found")

        ann_dir = os.path.join(pdir, "annotations")
        new_cls_id = class_to_id.get(new_label)

        # Merge case: new_label already exists
        if new_cls_id is not None:
            for fname in os.listdir(ann_dir):
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(ann_dir, fname)
                with open(fpath) as f:
                    ann = json.load(f)
                changed = self._update_annotation_label(ann, old_label, new_label, new_cls_id)
                if changed:
                    with open(fpath, "w") as f:
                        json.dump(ann, f, indent=2)
            # Remove old class from mappings
            del class_to_id[old_label]
            class_colors.pop(old_label, None)
        else:
            # Simple rename: swap key, preserve id and color
            old_id = class_to_id.pop(old_label)
            class_to_id[new_label] = old_id
            if old_label in class_colors:
                class_colors[new_label] = class_colors.pop(old_label)
            for fname in os.listdir(ann_dir):
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(ann_dir, fname)
                with open(fpath) as f:
                    ann = json.load(f)
                changed = self._update_annotation_label(ann, old_label, new_label, old_id)
                if changed:
                    with open(fpath, "w") as f:
                        json.dump(ann, f, indent=2)

        meta["class_to_id"] = class_to_id
        meta["class_colors"] = class_colors
        self._write_meta(name, meta)
        return meta

    def delete_class(self, name: str, label: str) -> dict:
        """Delete a class and all its detections across all images."""
        pdir = self._project_dir(name)
        if not os.path.isdir(pdir):
            raise FileNotFoundError(f"Dataset '{name}' not found")
        label = self._clean_label(label)

        meta = self._read_meta(name)
        class_to_id = meta.get("class_to_id", {})
        class_colors = meta.get("class_colors", {})
        if label not in class_to_id:
            raise ValueError(f"Class '{label}' not found")

        del class_to_id[label]
        class_colors.pop(label, None)

        ann_dir = os.path.join(pdir, "annotations")
        for fname in os.listdir(ann_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(ann_dir, fname)
            with open(fpath) as f:
                ann = json.load(f)
            if self._remove_annotation_label(ann, label):
                with open(fpath, "w") as f:
                    json.dump(ann, f, indent=2)

        meta["class_to_id"] = class_to_id
        meta["class_colors"] = class_colors
        self._write_meta(name, meta)
        return meta

    def _clean_label(self, label) -> str:
        if not isinstance(label, str):
            raise ValueError("label must be a string")
        clean = label.strip()
        if not clean:
            raise ValueError("label is required")
        return clean

    def _clean_box(self, box, width: int, height: int) -> list[float]:
        if not isinstance(box, list) or len(box) != 4:
            raise ValueError("box must be a list of four numbers")
        try:
            x1, y1, x2, y2 = [float(v) for v in box]
        except (TypeError, ValueError):
            raise ValueError("box must contain finite numbers")
        if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
            raise ValueError("box must contain finite numbers")

        left = min(x1, x2)
        top = min(y1, y2)
        right = max(x1, x2)
        bottom = max(y1, y2)
        left = min(max(left, 0.0), float(width))
        right = min(max(right, 0.0), float(width))
        top = min(max(top, 0.0), float(height))
        bottom = min(max(bottom, 0.0), float(height))
        if right <= left or bottom <= top:
            raise ValueError("box must have positive width and height")
        return [left, top, right, bottom]

    def add_detection(self, name: str, img_id: str, payload: dict) -> dict | None:
        pdir = self._project_dir(name)
        ann_path = os.path.join(pdir, "annotations", f"{img_id}.json")
        if not os.path.isfile(ann_path):
            return None

        with open(ann_path) as f:
            ann = json.load(f)

        label = self._clean_label(payload.get("label"))
        box = self._clean_box(payload.get("box"), ann["width"], ann["height"])
        cls_id = self._ensure_class(name, label)
        detections = ann.setdefault("detections", [])
        next_id = max((int(det.get("id", -1)) for det in detections), default=-1) + 1
        confidence = payload.get("confidence", 1.0)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 1.0
        if not math.isfinite(confidence):
            confidence = 1.0

        detection = {
            "id": next_id,
            "box": box,
            "label": label,
            "confidence": confidence,
            "cls_id": cls_id,
            "accepted": bool(payload.get("accepted", True)),
            "manual": True,
        }
        if payload.get("assisted"):
            detection["assisted"] = True
        if payload.get("source") == "visual_prompt":
            detection["source"] = "visual_prompt"
        if "mask" in payload:
            detection["mask"] = payload["mask"]
        if "mask_rle" in payload:
            detection["mask_rle"] = payload["mask_rle"]
        detections.append(detection)
        ann["labeled"] = True

        with open(ann_path, "w") as f:
            json.dump(ann, f, indent=2)
        return ann

    def update_detection(self, name: str, img_id: str, det_id: int, payload: dict) -> dict | None:
        pdir = self._project_dir(name)
        ann_path = os.path.join(pdir, "annotations", f"{img_id}.json")
        if not os.path.isfile(ann_path):
            return None

        with open(ann_path) as f:
            ann = json.load(f)

        target = None
        for det in ann.get("detections", []):
            if det.get("id") == det_id:
                target = det
                break
        if target is None:
            return None

        if "label" in payload and payload.get("label") is not None:
            label = self._clean_label(payload.get("label"))
            target["label"] = label
            target["cls_id"] = self._ensure_class(name, label)

        if "box" in payload and payload.get("box") is not None:
            target["box"] = self._clean_box(payload.get("box"), ann["width"], ann["height"])
            target.pop("mask", None)
            target.pop("mask_rle", None)

        if "accepted" in payload:
            target["accepted"] = bool(payload.get("accepted"))

        with open(ann_path, "w") as f:
            json.dump(ann, f, indent=2)
        return ann

    def delete_detection(self, name: str, img_id: str, det_id: int) -> dict | None:
        pdir = self._project_dir(name)
        ann_path = os.path.join(pdir, "annotations", f"{img_id}.json")
        if not os.path.isfile(ann_path):
            return None

        with open(ann_path) as f:
            ann = json.load(f)

        detections = ann.get("detections", [])
        remaining = [det for det in detections if det.get("id") != det_id]
        if len(remaining) == len(detections):
            return None
        ann["detections"] = remaining
        ann["labeled"] = bool(remaining)

        with open(ann_path, "w") as f:
            json.dump(ann, f, indent=2)
        return ann

    def review_image(self, name: str, img_id: str, reviews: list[dict]) -> dict | None:
        pdir = self._project_dir(name)
        ann_path = os.path.join(pdir, "annotations", f"{img_id}.json")
        if not os.path.isfile(ann_path):
            return None

        with open(ann_path) as f:
            ann = json.load(f)

        review_map = {r["id"]: r["accepted"] for r in reviews}
        for det in ann.get("detections", []):
            det_id = det.get("id")
            if det_id in review_map:
                det["accepted"] = review_map[det_id]

        with open(ann_path, "w") as f:
            json.dump(ann, f, indent=2)

        return ann

    def _labellens_manifest(self, name: str) -> str:
        pdir = self._project_dir(name)
        ann_dir = os.path.join(pdir, "annotations")
        meta = self._read_meta(name)
        annotations = []
        for fname in sorted(os.listdir(ann_dir)):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(ann_dir, fname)) as f:
                ann = json.load(f)
            annotations.append({"img_id": os.path.splitext(fname)[0], "annotations": ann})
        return json.dumps({"dataset": meta, "annotations": annotations}, indent=2)

    def _classification_entries(self, name: str) -> list[dict]:
        pdir = self._project_dir(name)
        ann_dir = os.path.join(pdir, "annotations")
        entries = []
        used_filenames: set[str] = set()
        for fname in sorted(os.listdir(ann_dir)):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(ann_dir, fname)) as f:
                ann = json.load(f)
            labels = [label for label in ann.get("labels", []) if label.get("accepted", True)]
            if not labels:
                continue
            img_filename = ann["image"]
            img_path = os.path.join(pdir, "images", img_filename)
            if not os.path.isfile(img_path):
                continue
            entries.append({
                "img_path": img_path,
                "img_filename": self._unique_export_filename(
                    ann.get("original_filename") or img_filename,
                    used_filenames,
                ),
                "labels": [label["label"] for label in labels],
            })
        return entries

    def _split_entries(self, entries: list[dict], split: float) -> tuple[list[dict], list[dict]]:
        random.seed(42)
        shuffled = list(entries)
        random.shuffle(shuffled)
        split_idx = int(len(shuffled) * split)
        return shuffled[:split_idx], shuffled[split_idx:]

    def _export_classification_single(self, name: str, split: float) -> bytes:
        entries = self._classification_entries(name)
        train_entries, val_entries = self._split_entries(entries, split)
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for subset, items in [("train", train_entries), ("val", val_entries)]:
                for entry in items:
                    label = entry["labels"][0]
                    zf.write(entry["img_path"], f"{subset}/{label}/{entry['img_filename']}")
            zf.writestr("labellens.json", self._labellens_manifest(name))
        zip_buf.seek(0)
        return zip_buf.getvalue()

    def _export_classification_multi(self, name: str, _split: float) -> bytes:
        entries = self._classification_entries(name)
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            csv_lines = ["filename,labels"]
            for entry in entries:
                path = f"images/{entry['img_filename']}"
                zf.write(entry["img_path"], path)
                csv_lines.append(f"{path},{'|'.join(entry['labels'])}")
            zf.writestr("labels.csv", "\n".join(csv_lines) + "\n")
            zf.writestr("labellens.json", self._labellens_manifest(name))
        zip_buf.seek(0)
        return zip_buf.getvalue()

    def _pose_visibility_value(self, visibility: str) -> int:
        if visibility == "missing":
            return 0
        if visibility == "occluded":
            return 1
        return 2

    def _export_pose_yolo(self, name: str, split: float) -> bytes:
        pdir = self._project_dir(name)
        ann_dir = os.path.join(pdir, "annotations")
        meta = self._read_meta(name)
        class_to_id = meta.get("class_to_id", {})
        template = meta.get("task_config", {}).get("pose_template", {})
        entries = []
        used_filenames: set[str] = set()
        for fname in sorted(os.listdir(ann_dir)):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(ann_dir, fname)) as f:
                ann = json.load(f)
            poses = [pose for pose in ann.get("poses", []) if pose.get("accepted", True)]
            if not poses:
                continue
            img_filename = ann["image"]
            img_path = os.path.join(pdir, "images", img_filename)
            if not os.path.isfile(img_path):
                continue
            w, h = ann["width"], ann["height"]
            lines = []
            for pose in poses:
                cls_id = class_to_id.get(pose["label"], -1)
                if cls_id < 0:
                    continue
                x1, y1, x2, y2 = pose["box"]
                parts = [
                    str(cls_id),
                    f"{((x1 + x2) / 2) / w:.6f}",
                    f"{((y1 + y2) / 2) / h:.6f}",
                    f"{(x2 - x1) / w:.6f}",
                    f"{(y2 - y1) / h:.6f}",
                ]
                keypoint_map = {kp["name"]: kp for kp in pose.get("keypoints", [])}
                for kp_name in template.get("keypoint_names", []):
                    kp = keypoint_map[kp_name]
                    parts.extend([
                        f"{kp['x'] / w:.6f}",
                        f"{kp['y'] / h:.6f}",
                        str(self._pose_visibility_value(kp.get("visibility", "visible"))),
                    ])
                lines.append(" ".join(parts))
            entries.append({
                "img_id": os.path.splitext(fname)[0],
                "img_path": img_path,
                "img_filename": self._unique_export_filename(
                    ann.get("original_filename") or img_filename,
                    used_filenames,
                ),
                "label_text": "\n".join(lines),
            })

        train_entries, val_entries = self._split_entries(entries, split)
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for subset, items in [("train", train_entries), ("val", val_entries)]:
                for entry in items:
                    zf.write(entry["img_path"], f"images/{subset}/{entry['img_filename']}")
                    zf.writestr(f"labels/{subset}/{entry['img_id']}.txt", entry["label_text"])
            names_yaml = {v: k for k, v in class_to_id.items()}
            yaml_lines = [
                f"path: ./datasets/{name}",
                "train: images/train",
                "val: images/val",
                f"kpt_shape: {template.get('kpt_shape')}",
                f"flip_idx: {template.get('flip_idx')}",
                "names:",
            ]
            for cid, cname in sorted(names_yaml.items()):
                yaml_lines.append(f"  {cid}: {cname}")
            yaml_lines.append("kpt_names:")
            for idx, kp_name in enumerate(template.get("keypoint_names", [])):
                yaml_lines.append(f"  {idx}: {kp_name}")
            zf.writestr("dataset.yaml", "\n".join(yaml_lines) + "\n")
            zf.writestr("labellens.json", self._labellens_manifest(name))
        zip_buf.seek(0)
        return zip_buf.getvalue()

    def export_yolo(self, name: str, split: float = 0.8) -> str:
        meta = self._read_meta(name)
        task_type = meta.get("task_type", "detect")
        if task_type == "classify_single":
            return self._export_classification_single(name, split)
        if task_type == "classify_multi":
            return self._export_classification_multi(name, split)
        if task_type == "pose":
            return self._export_pose_yolo(name, split)

        pdir = self._project_dir(name)
        ann_dir = os.path.join(pdir, "annotations")
        class_to_id = meta.get("class_to_id", {})

        # Collect accepted images with annotations
        entries = []
        used_filenames: set[str] = set()
        for fname in sorted(os.listdir(ann_dir)):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(ann_dir, fname)) as f:
                ann = json.load(f)

            accepted_dets = [d for d in ann["detections"] if d.get("accepted", True)]
            if not accepted_dets:
                continue

            img_filename = ann["image"]
            img_path = os.path.join(pdir, "images", img_filename)
            if not os.path.isfile(img_path):
                continue
            export_filename = self._unique_export_filename(
                ann.get("original_filename") or img_filename,
                used_filenames,
            )

            # Build YOLO label lines
            w, h = ann["width"], ann["height"]
            lines = []
            for det in accepted_dets:
                cls_id = class_to_id.get(det["label"], -1)
                if cls_id < 0:
                    continue
                x1, y1, x2, y2 = det["box"]
                x_center = ((x1 + x2) / 2) / w
                y_center = ((y1 + y2) / 2) / h
                bw = (x2 - x1) / w
                bh = (y2 - y1) / h
                lines.append(f"{cls_id} {x_center:.6f} {y_center:.6f} {bw:.6f} {bh:.6f}")

            img_id = os.path.splitext(fname)[0]
            entries.append({
                "img_id": img_id,
                "img_path": img_path,
                "img_filename": export_filename,
                "label_text": "\n".join(lines),
            })

        # Shuffle and split
        random.seed(42)
        random.shuffle(entries)
        split_idx = int(len(entries) * split)
        train_entries = entries[:split_idx]
        val_entries = entries[split_idx:]

        # Build zip
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for subset, items in [("train", train_entries), ("val", val_entries)]:
                for e in items:
                    zf.write(e["img_path"], f"images/{subset}/{e['img_filename']}")
                    zf.writestr(f"labels/{subset}/{e['img_id']}.txt", e["label_text"])

            names_yaml = {v: k for k, v in class_to_id.items()}
            yaml_lines = [
                f"path: ./datasets/{name}",
                "train: images/train",
                "val: images/val",
                "names:",
            ]
            for cid, cname in sorted(names_yaml.items()):
                yaml_lines.append(f"  {cid}: {cname}")
            zf.writestr("dataset.yaml", "\n".join(yaml_lines) + "\n")

        zip_buf.seek(0)
        return zip_buf.getvalue()

    def export_coco(self, name: str, split: float = 0.8) -> bytes:
        pdir = self._project_dir(name)
        ann_dir = os.path.join(pdir, "annotations")
        meta = self._read_meta(name)
        class_to_id = meta.get("class_to_id", {})
        categories = [{"id": cid, "name": cname} for cname, cid in class_to_id.items()]

        coco_images = []
        coco_annotations = []
        img_entries = []
        ann_id_counter = 1
        used_filenames: set[str] = set()

        for fname in sorted(os.listdir(ann_dir)):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(ann_dir, fname)) as f:
                ann = json.load(f)

            accepted_dets = [d for d in ann["detections"] if d.get("accepted", True)]
            if not accepted_dets:
                continue

            img_filename = ann["image"]
            img_path = os.path.join(pdir, "images", img_filename)
            if not os.path.isfile(img_path):
                continue
            export_filename = self._unique_export_filename(
                ann.get("original_filename") or img_filename,
                used_filenames,
            )

            img_id = len(coco_images) + 1
            coco_images.append({
                "id": img_id,
                "file_name": export_filename,
                "width": ann["width"],
                "height": ann["height"],
            })

            for det in accepted_dets:
                x1, y1, x2, y2 = det["box"]
                bw = x2 - x1
                bh = y2 - y1
                area = bw * bh
                segmentation = det.get("mask", [])

                coco_annotations.append({
                    "id": ann_id_counter,
                    "image_id": img_id,
                    "category_id": class_to_id.get(det["label"], -1),
                    "bbox": [x1, y1, bw, bh],
                    "area": area,
                    "iscrowd": 0,
                    **({"segmentation": [segmentation]} if segmentation else {}),
                })
                ann_id_counter += 1

            img_entries.append({"img_path": img_path, "img_filename": export_filename})

        coco_json = json.dumps({
            "images": coco_images,
            "annotations": coco_annotations,
            "categories": categories,
        }, indent=2)

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("coco.json", coco_json)
            for e in img_entries:
                zf.write(e["img_path"], f"images/{e['img_filename']}")

        zip_buf.seek(0)
        return zip_buf.getvalue()

    def _unique_export_filename(self, filename: str, used_filenames: set[str]) -> str:
        safe = self._sanitize_filename(filename, "image.jpg")
        if safe not in used_filenames:
            used_filenames.add(safe)
            return safe
        stem, ext = os.path.splitext(safe)
        index = 2
        while True:
            candidate = f"{stem}-{index}{ext}"
            if candidate not in used_filenames:
                used_filenames.add(candidate)
                return candidate
            index += 1


dataset_service = DatasetService()
