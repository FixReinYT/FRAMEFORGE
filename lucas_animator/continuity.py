"""FRAMEFORGE Continuity Threads: named landmarks tracked across animation frames."""
from __future__ import annotations

import copy
import re

PALETTE = ("#42d6c4", "#ff9b71", "#82aaff", "#e5b85c", "#c69cff", "#f17eaa")


def normalize_tracks(raw, frame_count, width, height):
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("Повреждена карта непрерывности проекта.")
    result = {}
    for key, track in raw.items():
        if not isinstance(key, str) or not key.strip() or len(key) > 40 or not isinstance(track, dict):
            raise ValueError("Некорректное имя или структура нити непрерывности.")
        color = track.get("color", PALETTE[len(result) % len(PALETTE)])
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError("Некорректный цвет нити непрерывности.")
        points = track.get("points", {})
        if not isinstance(points, dict):
            raise ValueError("Некорректные точки нити непрерывности.")
        clean = {}
        for frame, point in points.items():
            try:
                frame_index = int(frame)
            except (TypeError, ValueError) as exc:
                raise ValueError("Некорректный номер кадра в карте непрерывности.") from exc
            if not 0 <= frame_index < frame_count or not isinstance(point, (list, tuple)) or len(point) != 2:
                raise ValueError("Точка карты непрерывности выходит за пределы проекта.")
            x, y = point
            if type(x) is not int or type(y) is not int or not (0 <= x < width and 0 <= y < height):
                raise ValueError("Координаты точки карты непрерывности некорректны.")
            clean[str(frame_index)] = [x, y]
        result[key] = {"name": key, "color": color.lower(), "points": clean}
    return result


def insert_frame(tracks, insert_at, duplicate_from=None):
    """Shift frame references after insertion and optionally copy the source pose."""
    result = copy.deepcopy(tracks)
    for track in result.values():
        points = track.get("points", {})
        shifted = {}
        source_point = points.get(str(duplicate_from)) if duplicate_from is not None else None
        for frame, point in points.items():
            index = int(frame)
            if index >= insert_at:
                index += 1
            shifted[str(index)] = list(point)
        if source_point is not None:
            shifted[str(insert_at)] = list(source_point)
        track["points"] = shifted
    return result


def delete_frame(tracks, deleted_at):
    result = copy.deepcopy(tracks)
    for track in result.values():
        shifted = {}
        for frame, point in track.get("points", {}).items():
            index = int(frame)
            if index == deleted_at:
                continue
            if index > deleted_at:
                index -= 1
            shifted[str(index)] = list(point)
        track["points"] = shifted
    return result
