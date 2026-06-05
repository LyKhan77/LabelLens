# LabelLens Workflows

This document describes operator workflows from the user interface.

## Feature Mode Selection

1. Open `/`.
2. Choose Free Inference, Prompt Inference, Dataset Manager, or Train Tune.
3. Let the app load the required backend model before entering `/workspace` when needed.

## Free Inference

1. Choose Free Inference from `/`.
2. Load the prompt-free model.
3. Add image, video, or RTSP input.
4. Set confidence and overlay options.
5. Start inference.
6. Inspect detections and stats in the floating panel.
7. Stop inference and clear media before switching input type.

## Text Prompt Inference

1. Choose Prompt Inference.
2. Select Text Prompt.
3. Enter comma-separated labels such as `person, car, dog`.
4. Add target media.
5. Start inference.
6. Adjust confidence and rerun if needed.

## Visual Prompt Inference

1. Choose Prompt Inference.
2. Select Visual Prompt.
3. Upload a reference image.
4. Draw bbox prompts around example objects.
5. Assign labels/classes to prompt boxes.
6. Add target media.
7. Start inference to find visually similar objects.

## Workspace Auto-Labelling

1. Open the Dataset section in the Workspace sidebar.
2. Open Auto-Label modal.
3. Select the target dataset and sampling rate.
4. Start Auto-Label.
5. For RTSP, optionally set an `MM:SS` timer.
6. Continue inference while accepted viewer frames are saved.
7. Stop Auto-Label from the modal or stop inference.

## Dataset Manager Review

1. Open `/datasets`.
2. Create or open a dataset project. New datasets choose a task type: Detection, Segmentation, Classification Single, Classification Multi, or Pose.
3. Upload images or sample video/RTSP frames.
4. Use the paginated gallery to inspect thumbnails with overlays.
5. Use Select All Files for the current page/filter when bulk deletion is needed.
6. Open an image in modal review.
7. Zoom/pan for pixel-level inspection.
8. Review annotations with the task-specific editor.
9. Detection/Segmentation: accept/reject detections and add, edit, or delete manual bboxes.
10. Classification: assign one image label or multiple image labels depending on dataset task.
11. Pose: create a bbox-first pose instance, then drag fixed-template keypoints and set visibility.
12. Adjust per-class colors when needed.
13. Export accepted labels in the native task format.

## Rapid Inference

1. Open Dataset Manager.
2. Click Rapid Inference.
3. Choose current unlabeled dataset images or upload new images/video/folder.
4. Detection/Segmentation: choose Free, Text, or Visual prompt mode.
5. Classification/Pose: use a compatible trained model version when that model-selection phase is available.
6. Start inference.
7. Watch frame-by-frame progress.
8. Review annotations in the task-specific modal reviewer.
9. Accept, reject, correct, or delete annotations as supported by the dataset task.

## Infer Next Visual Assist

1. In Dataset Manager review, select one or more saved annotations as prompts.
2. Load the prompt model if needed.
3. Run Infer Next for the next target image.
4. Review candidate detections.
5. Accept or reject individual candidates.
6. Use Accept All & Continue when candidates are correct and propagation should continue.

## SAM2.1 Auto-mask

1. Open an image in Dataset Manager review.
2. Draw a manual bbox.
3. Save the annotation.
4. If SAM is enabled and available, the backend generates a mask from the bbox.
5. If SAM fails, continue with bbox-only annotation.

## Train Tune Dataset Version

1. Open `/train-tune`.
2. Choose Live Dataset or Export ZIP.
3. Select Detection or Segmentation task.
4. Configure train/val/test split.
5. Choose resize policy: Keep, Letterbox, or Stretch.
6. Choose Basic augmentation or Advanced augmentation steps.
7. Generate preview samples.
8. Review original, preprocessed, and augmented overlays.
9. Create immutable Dataset Version.

Segmentation Dataset Versions require masks for every accepted object.

## Train Tune Job

1. Select a Dataset Version.
2. Review locked split, preprocessing, augmentation, classes, and source.
3. Apply recommended settings or override epochs, patience, image size, batch, workers, checkpoint, and training mode.
4. Start training.
5. Monitor `/train-tune/jobs/:id` for metrics, events, checkpoint paths, logs, ETA, and config.
6. Cancel when needed.
7. Recompute failed jobs or resume failed/cancelled jobs with `last.pt`.
8. Review completed result at `/train-tune/results/:id`.
9. Test registered artifact at `/train-tune/test/:id`.

## Export and Reuse Loop

1. Auto-label or manually annotate dataset images.
2. Review and accept labels.
3. Export YOLO/COCO when external training is needed, or create a Train Tune Dataset Version directly.
4. Train a model.
5. Register the model as a Model Version.
6. Test the artifact.
7. Use the improved model for future dataset iteration.
