import threading


class ActivityService:
    def __init__(self):
        self._lock = threading.Lock()
        self._active_inference = 0
        self._high_speed_training = False

    def start_inference(self):
        with self._lock:
            if self._high_speed_training:
                raise RuntimeError('High-Speed training is active. New inference requests are temporarily blocked.')
            self._active_inference += 1

    def stop_inference(self):
        with self._lock:
            self._active_inference = max(0, self._active_inference - 1)

    def inference_active(self) -> bool:
        with self._lock:
            return self._active_inference > 0

    def set_high_speed_training(self, active: bool):
        with self._lock:
            self._high_speed_training = active

    def high_speed_training_active(self) -> bool:
        with self._lock:
            return self._high_speed_training


activity_service = ActivityService()
