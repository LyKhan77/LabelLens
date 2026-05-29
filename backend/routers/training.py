import asyncio
import json

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect

from backend.services.activity import activity_service
from backend.services.training import MissingSegmentationMasksError, training_service
from backend.services.training_events import training_event_hub
from backend.services.training_runtime import training_runtime

router = APIRouter(tags=['training'])


def _parse_json(raw: str | None, field: str, default):
    if raw in (None, ''):
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f'Invalid {field} JSON') from exc


@router.get('/training/dataset-versions')
async def list_dataset_versions():
    return training_service.list_dataset_versions()


@router.get('/training/dataset-versions/{version_id}')
async def get_dataset_version(version_id: str):
    try:
        return training_service.get_dataset_version(version_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.delete('/training/dataset-versions/{version_id}')
async def delete_dataset_version(version_id: str):
    try:
        training_service.delete_dataset_version(version_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {'ok': True}


@router.post('/training/dataset-versions/preview')
async def preview_dataset_policy(
    source_type: str = Form('live'),
    dataset_name: str = Form(''),
    split_config: str = Form('{"train": 70, "val": 20, "test": 10}'),
    preprocessing_config: str = Form('{}'),
    augmentation_config: str = Form('{"profile": "baseline"}'),
    task_type: str = Form('detect'),
    file: UploadFile | None = File(None),
):
    try:
        config = {
            'source_type': source_type,
            'dataset_name': dataset_name or None,
            'split_config': _parse_json(split_config, 'split_config', {'train': 70, 'val': 20, 'test': 10}),
            'preprocessing_config': _parse_json(preprocessing_config, 'preprocessing_config', {}),
            'augmentation_config': _parse_json(augmentation_config, 'augmentation_config', {'profile': 'baseline'}),
            'task_type': task_type,
        }
        if file is not None:
            config['zip_bytes'] = await file.read()
            config['source_name'] = file.filename or 'dataset-export.zip'
        return training_service.preview_dataset_policy(config)
    except MissingSegmentationMasksError as exc:
        raise HTTPException(400, {
            'code': 'missing_segmentation_masks',
            'message': str(exc),
            'missing': exc.missing,
        }) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post('/training/dataset-versions/live')
async def create_live_dataset_version(
    dataset_name: str = Form(...),
    version_name: str = Form(''),
    split_config: str = Form('{"train": 70, "val": 20, "test": 10}'),
    preprocessing_config: str = Form('{}'),
    augmentation_config: str = Form('{"profile": "baseline"}'),
    resize_mode: str = Form('keep'),
    task_type: str = Form('detect'),
):
    try:
        return training_service.create_dataset_version_from_live_dataset(
            dataset_name,
            {
                'version_name': version_name or None,
                'split_config': _parse_json(split_config, 'split_config', {'train': 70, 'val': 20, 'test': 10}),
                'preprocessing_config': _parse_json(preprocessing_config, 'preprocessing_config', {}),
                'augmentation_config': _parse_json(augmentation_config, 'augmentation_config', {'profile': 'baseline'}),
                'resize_mode': resize_mode,
                'task_type': task_type,
            },
        )
    except MissingSegmentationMasksError as exc:
        raise HTTPException(400, {
            'code': 'missing_segmentation_masks',
            'message': str(exc),
            'missing': exc.missing,
        }) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post('/training/dataset-versions/import')
async def import_dataset_version(
    file: UploadFile = File(...),
    version_name: str = Form(''),
    split_mode: str = Form('existing'),
    split_config: str = Form('{"train": 70, "val": 20, "test": 10}'),
    preprocessing_config: str = Form('{}'),
    augmentation_config: str = Form('{"profile": "baseline"}'),
    task_type: str = Form('detect'),
):
    try:
        return training_service.create_dataset_version_from_zip(
            await file.read(),
            file.filename or 'dataset-export.zip',
            {
                'version_name': version_name or None,
                'split_mode': split_mode,
                'split_config': _parse_json(split_config, 'split_config', {'train': 70, 'val': 20, 'test': 10}),
                'preprocessing_config': _parse_json(preprocessing_config, 'preprocessing_config', {}),
                'augmentation_config': _parse_json(augmentation_config, 'augmentation_config', {'profile': 'baseline'}),
                'task_type': task_type,
            },
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post('/training/estimate')
async def estimate_training(payload: dict = Body(...)):
    try:
        version_id = payload['dataset_version_id']
    except KeyError as exc:
        raise HTTPException(400, 'dataset_version_id is required') from exc
    try:
        return training_service.estimate_training(version_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post('/training/recommend')
async def recommend_training(payload: dict = Body(...)):
    try:
        version_id = payload['dataset_version_id']
    except KeyError as exc:
        raise HTTPException(400, 'dataset_version_id is required') from exc
    try:
        return training_service.recommend_training_settings(version_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get('/training/jobs')
async def list_training_jobs():
    return training_service.list_training_jobs()


@router.get('/training/jobs/{job_id}')
async def get_training_job(job_id: str):
    try:
        return training_service.get_training_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post('/training/jobs')
async def create_training_job(payload: dict = Body(...)):
    try:
        job = training_service.create_training_job(payload, inference_active=activity_service.inference_active())
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    training_runtime.notify_job_queued()
    return job


@router.post('/training/jobs/{job_id}/cancel')
async def cancel_training_job(job_id: str):
    try:
        training_runtime.cancel_job(job_id)
        return training_service.get_training_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post('/training/jobs/{job_id}/recompute')
async def recompute_training_job(job_id: str):
    try:
        job = training_service.recompute_training_job(job_id, inference_active=activity_service.inference_active())
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    training_runtime.notify_job_queued()
    return job


@router.post('/training/jobs/{job_id}/resume')
async def resume_training_job(job_id: str):
    try:
        job = training_service.resume_training_job(job_id, inference_active=activity_service.inference_active())
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    training_runtime.notify_job_queued()
    return job


@router.delete('/training/jobs/{job_id}')
async def delete_training_job(job_id: str):
    try:
        training_service.delete_training_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {'ok': True}


@router.get('/training/jobs/{job_id}/metrics')
async def get_training_metrics(job_id: str):
    return training_service.list_training_metrics(job_id)


@router.get('/training/models')
async def list_model_versions():
    return training_service.list_model_versions()


@router.get('/training/models/{model_id}')
async def get_model_version(model_id: str):
    try:
        return training_service.get_model_version(model_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.delete('/training/models/{model_id}')
async def delete_model_version(model_id: str):
    try:
        training_service.delete_model_version(model_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {'ok': True}


@router.websocket('/ws/training/{job_id}')
async def training_events(ws: WebSocket, job_id: str):
    await ws.accept()
    loop = asyncio.get_running_loop()
    queue = training_event_hub.subscribe(job_id, loop)
    try:
        for event in training_event_hub.history(job_id):
            await ws.send_json(event)
        while True:
            event = await queue.get()
            await ws.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        training_event_hub.unsubscribe(job_id, queue)
