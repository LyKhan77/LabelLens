import io
import json
import math
import os
import random
import shutil
import zipfile
from datetime import datetime

import cv2
import numpy as np

DATASETS_DIR = "datasets"


class DatasetService:
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

    def _recalc_stats(self, name: str) -> dict:
        ann_dir = os.path.join(self._project_dir(name), "annotations")
        total_images = 0
        total_annotations = 0
        accepted = 0
        rejected = 0
        classes: set[str] = set()

        for fname in os.listdir(ann_dir):
            if not fname.endswith(".json"):
                continue
            total_images += 1
            with open(os.path.join(ann_dir, fname)) as f:
                ann = json.load(f)
            for det in ann.get("detections", []):
                total_annotations += 1
                classes.add(det["label"])
                if det.get("accepted", True):
                    accepted += 1
                else:
                    rejected += 1

        return {
            "total_images": total_images,
            "total_annotations": total_annotations,
            "accepted": accepted,
            "rejected": rejected,
            "classes": sorted(classes),
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
            stats = self._recalc_stats(name)
            projects.append({
                "name": name,
                "created": meta.get("created"),
                "class_to_id": meta.get("class_to_id", {}),
                "stats": stats,
            })
        return projects

    def create_project(self, name: str, classes: list[str] | None = None) -> dict:
        pdir = self._project_dir(name)
        if os.path.exists(pdir):
            raise FileExistsError(f"Dataset '{name}' already exists")
        os.makedirs(os.path.join(pdir, "images"))
        os.makedirs(os.path.join(pdir, "annotations"))

        classes = classes or []
        class_to_id = {c: i for i, c in enumerate(classes)}

        meta = {
            "name": name,
            "created": datetime.now().isoformat(),
            "next_id": 1,
            "class_to_id": class_to_id,
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
            "width": w,
            "height": h,
            "source": source,
            "created": datetime.now().isoformat(),
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

    def upload_raw(self, name: str, image_bytes: bytes, source: str = "upload") -> dict:
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
            "width": w,
            "height": h,
            "source": source,
            "created": datetime.now().isoformat(),
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
                detections_preview = [self._preview_detection(det) for det in dets]
                if not ann.get("labeled", True) and len(dets) == 0:
                    status = "unlabeled"
                else:
                    for det in dets:
                        if det.get("accepted", True):
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
            self._write_meta(name, meta)
        return class_to_id[label]

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

    def export_yolo(self, name: str, split: float = 0.8) -> str:
        pdir = self._project_dir(name)
        ann_dir = os.path.join(pdir, "annotations")
        meta = self._read_meta(name)
        class_to_id = meta.get("class_to_id", {})

        # Collect accepted images with annotations
        entries = []
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
                "img_filename": img_filename,
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

            img_id = len(coco_images) + 1
            coco_images.append({
                "id": img_id,
                "file_name": img_filename,
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

            img_entries.append({"img_path": img_path, "img_filename": img_filename})

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


dataset_service = DatasetService()
